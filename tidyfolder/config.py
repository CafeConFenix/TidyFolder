"""Persistent user settings (stored next to the .exe when portable)."""
from __future__ import annotations

import json
import locale
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-5-5"


def data_dir() -> Path:
    """Folder for settings and the undo journal.

    Portable build: a ``TidyFolder_data`` folder next to the executable (falls back
    to the home folder when that location is read-only). Source run: ``~/.tidyfolder``.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if os.access(exe_dir, os.W_OK):
            return exe_dir / "TidyFolder_data"
    return Path.home() / ".tidyfolder"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def journal_path() -> Path:
    return data_dir() / "last_run.json"


def detect_language() -> str:
    """Return ``"es"`` when the OS language is Spanish, otherwise ``"en"``."""
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
        return "es" if (lang_id & 0xFF) == 0x0A else "en"
    except Exception:
        pass
    try:
        code = os.environ.get("LANG") or (locale.getlocale()[0] or "")
        return "es" if code.lower().startswith("es") else "en"
    except Exception:
        return "en"


@dataclass
class Settings:
    language: str = ""
    mode: str = "keywords"  # "keywords" | "ai"
    api_key: str = ""
    model: str = DEFAULT_MODEL
    default_action: str = "move"  # "move" | "copy"
    recursive: bool = True
    remove_empty: bool = False
    last_source: str = ""
    last_dest: str = ""

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        try:
            data = json.loads(settings_path().read_text(encoding="utf-8"))
            names = {f.name for f in fields(cls)}
            for key, value in data.items():
                if key in names:
                    setattr(settings, key, value)
        except (OSError, ValueError):
            pass
        if settings.language not in ("en", "es"):
            settings.language = detect_language()
        return settings

    def save(self) -> None:
        try:
            path = settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass
