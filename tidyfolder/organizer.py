"""Scan folders, build a sorting plan, execute it (move/copy) and undo it."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

from .categories import all_folder_names, folder_name
from .classifier import Classifier
from .config import journal_path

Progress = Callable[[int, int], None]

IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
IGNORED_SUFFIXES = {".tmp", ".part", ".crdownload", ".lnk"}


class Cancelled(Exception):
    """Raised when the user cancels a long operation."""


@dataclass
class PlanItem:
    src: Path
    category: str
    method: str
    action: str = "move"  # "move" | "copy"
    include: bool = True


@dataclass
class ExecResult:
    moved: int = 0
    copied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def ok(self) -> int:
        return self.moved + self.copied


@dataclass
class UndoResult:
    ok: int = 0
    errors: list[str] = field(default_factory=list)


def is_dangerous(path: Path) -> bool:
    """Refuse drive roots, the home folder and operating-system folders."""
    p = path.resolve()
    if p.parent == p or p == Path.home().resolve():
        return True
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        value = os.environ.get(var)
        if value:
            protected = Path(value).resolve()
            if p == protected or protected in p.parents:
                return True
    return str(p) in {"/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr", "/var", "/System"}


def skip_dirs_for(source: Path, dest_root: Path) -> set[Path]:
    """Folders that must not be scanned: the destination and folders this app already made."""
    src, dest = source.resolve(), dest_root.resolve()
    skip = {(dest / name).resolve() for name in all_folder_names()}
    if dest != src:
        skip.add(dest)
    return skip


def scan_files(source: Path, recursive: bool = True, skip_dirs: Iterable[Path] = ()) -> Iterator[Path]:
    skip = set(skip_dirs)
    for root, dirs, files in os.walk(source):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not d.startswith(".") and (root_path / d).resolve() not in skip]
        if not recursive:
            dirs[:] = []
        for name in files:
            lower = name.lower()
            if name.startswith((".", "~$")) or lower in IGNORED_NAMES or Path(lower).suffix in IGNORED_SUFFIXES:
                continue
            yield root_path / name


def build_plan(
    source: Path,
    dest_root: Path,
    classifier: Classifier,
    recursive: bool = True,
    default_action: str = "move",
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> list[PlanItem]:
    files = list(scan_files(source, recursive, skip_dirs_for(source, dest_root)))
    total = len(files)
    if progress:
        progress(0, total)
    workers = 6 if classifier.ai is not None else 4
    items: list[PlanItem] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(classifier.classify, f): f for f in files}
        try:
            for future in as_completed(futures):
                if cancel and cancel.is_set():
                    raise Cancelled()
                path = futures[future]
                try:
                    category, method = future.result()
                except Exception:
                    category, method = "other", "error"
                items.append(PlanItem(path, category, method, default_action))
                done += 1
                if progress:
                    progress(done, total)
        except Cancelled:
            for f in futures:
                f.cancel()
            raise
    items.sort(key=lambda i: str(i.src).lower())
    return items


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def remove_empty_dirs(root: Path, keep: set[Path]) -> list[Path]:
    removed: list[Path] = []
    keep = {k.resolve() for k in keep} | {root.resolve()}
    for dirpath, _dirs, _files in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p.resolve() in keep:
            continue
        try:
            os.rmdir(p)  # only succeeds when the folder is empty
            removed.append(p)
        except OSError:
            pass
    return removed


def _write_journal(ops: list[dict], created: list[str], removed: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "operations": ops,
            "created_dirs": created, "removed_dirs": removed}
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def execute_plan(
    items: list[PlanItem],
    dest_root: Path,
    source_root: Path,
    lang: str,
    remove_empty: bool = False,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
    journal: Path | None = None,
) -> ExecResult:
    journal = journal or journal_path()
    chosen = [i for i in items if i.include]
    result = ExecResult()
    ops: list[dict] = []
    created: list[str] = []
    removed: list[str] = []
    total = len(chosen)
    try:
        for index, item in enumerate(chosen, start=1):
            if cancel and cancel.is_set():
                result.cancelled = True
                break
            target_dir = dest_root / folder_name(item.category, lang)
            try:
                if item.src.parent.resolve() == target_dir.resolve():
                    result.skipped += 1
                    continue
                if not target_dir.exists():
                    target_dir.mkdir(parents=True)
                    created.append(str(target_dir))
                target = unique_path(target_dir / item.src.name)
                if item.action == "copy":
                    shutil.copy2(item.src, target)
                    result.copied += 1
                else:
                    shutil.move(str(item.src), str(target))
                    result.moved += 1
                ops.append({"action": item.action, "src": str(item.src), "dest": str(target)})
            except Exception as exc:  # keep going; report at the end
                result.errors.append(f"{item.src.name}: {exc}")
            if progress:
                progress(index, total)
        if remove_empty and result.moved:
            removed = [str(p) for p in remove_empty_dirs(source_root, {dest_root})]
    finally:
        if ops or removed:
            try:
                _write_journal(ops, created, removed, journal)
            except OSError as exc:
                result.errors.append(f"journal: {exc}")
    return result


def journal_size(journal: Path | None = None) -> int:
    """Number of operations in the last-run journal (0 when there is none)."""
    try:
        data = json.loads((journal or journal_path()).read_text(encoding="utf-8"))
        return len(data.get("operations", []))
    except (OSError, ValueError):
        return 0


def undo_last(journal: Path | None = None, progress: Progress | None = None) -> UndoResult:
    journal = journal or journal_path()
    result = UndoResult()
    try:
        data = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    for d in sorted(data.get("removed_dirs", []), key=len):
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            result.errors.append(f"{d}: {exc}")
    ops = list(reversed(data.get("operations", [])))
    for index, op in enumerate(ops, start=1):
        src, dest = Path(op["src"]), Path(op["dest"])
        try:
            if not dest.exists():
                raise FileNotFoundError("file no longer in the destination folder")
            if op["action"] == "copy":
                dest.unlink()
            else:
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(unique_path(src)))
            result.ok += 1
        except Exception as exc:
            result.errors.append(f"{dest.name}: {exc}")
        if progress:
            progress(index, len(ops))
    for d in sorted(data.get("created_dirs", []), key=len, reverse=True):
        try:
            os.rmdir(d)
        except OSError:
            pass
    try:
        journal.unlink()
    except OSError:
        pass
    return result
