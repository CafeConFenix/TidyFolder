"""Read text from many document formats (best effort, never raises)."""
from __future__ import annotations

import html
import logging
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_CHARS = 20_000
_XML_LIMIT = 2_000_000  # bytes read from each XML part inside a zip
MAX_PDF_BYTES = 80 * 1024 * 1024  # bigger PDFs (large drawings) are classified by file name only
_PDF_TIME_BUDGET = 8.0  # seconds spent reading the text of one PDF

TEXT_EXT = {"txt", "md", "csv", "tsv", "log", "tex", "eml", "rst"}
HTML_EXT = {"html", "htm"}
OLE_EXT = {"doc", "xls", "ppt", "msg"}  # legacy binary Office formats
ODF_EXT = {"odt", "ods", "odp"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_markup(markup: str) -> str:
    return _clean(html.unescape(re.sub(r"<[^>]+>", " ", markup)))


def _decode(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _read_part(zf: zipfile.ZipFile, name: str) -> str:
    with zf.open(name) as fh:
        return _decode(fh.read(_XML_LIMIT))


def _from_text(path: Path) -> str:
    with open(path, "rb") as fh:
        return _clean(_decode(fh.read(300_000)))


def _from_html(path: Path) -> str:
    with open(path, "rb") as fh:
        raw = _decode(fh.read(500_000))
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return _strip_markup(raw)


def _from_rtf(path: Path) -> str:
    with open(path, "rb") as fh:
        raw = fh.read(500_000).decode("cp1252", errors="replace")
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?|[{}]", " ", raw)
    return _clean(raw)


def _from_ooxml(path: Path, ext: str) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "docProps/core.xml" in names:
            parts.append(_strip_markup(_read_part(zf, "docProps/core.xml")))
        if ext in ("docx", "dotx", "docm"):
            targets = ["word/document.xml"]
        elif ext in ("xlsx", "xlsm"):
            targets = ["xl/sharedStrings.xml", "xl/workbook.xml"]
        else:  # pptx
            slides = [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
            targets = sorted(slides, key=lambda n: int(re.findall(r"\d+", n)[0]))[:40]
        for name in targets:
            if name in names:
                parts.append(_strip_markup(_read_part(zf, name)))
                if sum(len(p) for p in parts) > MAX_CHARS:
                    break
    return " ".join(parts)


def _from_odf(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        return _strip_markup(_read_part(zf, "content.xml")) if "content.xml" in zf.namelist() else ""


def _from_epub(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        pages = [n for n in zf.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        for name in pages[:15]:
            parts.append(_strip_markup(_read_part(zf, name)))
            if sum(len(p) for p in parts) > MAX_CHARS:
                break
    return " ".join(parts)


def _from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    if path.stat().st_size > MAX_PDF_BYTES:
        return ""
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ""
    parts: list[str] = []
    meta = reader.metadata
    if meta:
        parts.extend(str(v) for v in (meta.title, meta.subject, meta.keywords) if v)
    started = time.monotonic()
    for page in reader.pages[:8]:
        parts.append(page.extract_text() or "")
        if sum(len(p) for p in parts) > MAX_CHARS or time.monotonic() - started > _PDF_TIME_BUDGET:
            break
    return _clean(" ".join(parts))


# ---------------------------------------------------------------- optional OCR
_SYSTEM_TESSERACT = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _bundled_dir() -> Path | None:
    """Tesseract shipped with the app: inside the .exe, or in ``vendor/tesseract`` from source."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "tesseract"
    else:
        base = Path(__file__).resolve().parent.parent / "vendor" / "tesseract"
    for name in ("tesseract.exe", "tesseract"):
        if (base / name).exists():
            return base
    return None


def _find_tesseract() -> str | None:
    bundled = _bundled_dir()
    if bundled is not None:
        return str(bundled / ("tesseract.exe" if (bundled / "tesseract.exe").exists() else "tesseract"))
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in _SYSTEM_TESSERACT:
        if Path(candidate).exists():
            return candidate
    return None


def _tessdata_dir() -> str | None:
    """Folder with the bundled language models, when we ship them."""
    bundled = _bundled_dir()
    if bundled is not None and (bundled / "tessdata").is_dir():
        return str(bundled / "tessdata")
    return None


def ocr_status() -> tuple[str, str]:
    """Explain the OCR state: ("ok", ""), ("no_packages", "<missing modules>") or ("no_engine", "")."""
    missing = []
    for module in ("pypdfium2", "PIL"):
        try:
            __import__(module)
        except Exception:  # ImportError, or a broken native library
            missing.append("Pillow" if module == "PIL" else module)
    if missing:
        return "no_packages", ", ".join(missing)
    if _find_tesseract() is None:
        return "no_engine", ""
    return "ok", ""


def ocr_available() -> bool:
    """True when the OCR Python packages and a Tesseract engine (bundled or installed) exist."""
    return ocr_status()[0] == "ok"


# PDFium is not thread-safe and Tesseract is CPU-hungry: only one OCR job runs at a time so the
# app and the rest of the computer stay responsive while many files are analysed.
_OCR_LOCK = threading.Lock()
_OCR_MAX_PAGES = 3
_OCR_TARGET_PIXELS = 2400  # longest side of the rendered page


def hidden_process_kwargs(windows: bool | None = None, sp=subprocess) -> dict:
    """``subprocess`` options that stop Windows from opening a console window (and lower priority)."""
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return {}
    info = sp.STARTUPINFO()
    info.dwFlags |= sp.STARTF_USESHOWWINDOW
    info.wShowWindow = sp.SW_HIDE
    return {
        "startupinfo": info,
        "creationflags": getattr(sp, "CREATE_NO_WINDOW", 0x08000000)
        | getattr(sp, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000),
    }


def _run_tesseract(command: list[str], timeout: int) -> subprocess.CompletedProcess:
    env = dict(os.environ, OMP_THREAD_LIMIT="1")  # one thread per Tesseract process
    return subprocess.run(command, capture_output=True, timeout=timeout, env=env,
                          stdin=subprocess.DEVNULL, **hidden_process_kwargs())


@functools.lru_cache(maxsize=1)
def _ocr_languages() -> str | None:
    """"spa+eng" (or whichever of the two is installed), cached after the first call."""
    exe, data = _find_tesseract(), _tessdata_dir()
    if exe is None:
        return None
    command = [exe, "--list-langs"] + (["--tessdata-dir", data] if data else [])
    try:
        result = _run_tesseract(command, 30)
    except (OSError, subprocess.SubprocessError):
        return None
    installed = (result.stdout + result.stderr).decode("utf-8", errors="replace").split()
    wanted = [code for code in ("spa", "eng") if code in installed]
    return "+".join(wanted) or None


def _ocr_pdf(path: Path, max_pages: int = _OCR_MAX_PAGES) -> str:
    """OCR the first pages of a scanned PDF (English + Spanish when available)."""
    import pypdfium2 as pdfium

    exe, data = _find_tesseract(), _tessdata_dir()
    if exe is None:
        return ""
    parts: list[str] = []
    with _OCR_LOCK:
        lang = _ocr_languages()
        pdf = pdfium.PdfDocument(str(path))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                for index in range(min(len(pdf), max_pages)):
                    page = pdf[index]
                    width, height = page.get_size()
                    # Large-format drawings are scaled down so the bitmap never gets huge.
                    scale = max(0.5, min(3.0, _OCR_TARGET_PIXELS / max(width, height, 1)))
                    image_path = Path(tmp) / f"page{index}.png"
                    page.render(scale=scale).to_pil().convert("L").save(image_path)
                    command = [exe, str(image_path), "stdout"]
                    if lang:
                        command += ["-l", lang]
                    if data:
                        command += ["--tessdata-dir", data]
                    try:
                        parts.append(_run_tesseract(command, 120).stdout.decode("utf-8", errors="replace"))
                    except subprocess.TimeoutExpired:
                        break
        finally:
            pdf.close()
    return _clean(" ".join(parts))


def _from_ole(path: Path) -> str:
    """Very rough text recovery for legacy .doc/.xls/.ppt files."""
    with open(path, "rb") as fh:
        data = fh.read(400_000)
    text = data.replace(b"\x00", b"").decode("cp1252", errors="ignore")
    runs = re.findall(r"[A-Za-zÀ-ÿ0-9 ,.;:()/\-]{8,}", text)
    return _clean(" ".join(runs))


def extract_text(path: Path | str, max_chars: int = MAX_CHARS, ocr: bool = False) -> str:
    """Return the readable text of *path* (empty string when unsupported or on error).

    With ``ocr=True`` scanned PDFs (no embedded text) are read with Tesseract when available.
    """
    path = Path(path)
    ext = path.suffix.lower().lstrip(".")
    try:
        if ext in TEXT_EXT:
            text = _from_text(path)
        elif ext in HTML_EXT:
            text = _from_html(path)
        elif ext == "rtf":
            text = _from_rtf(path)
        elif ext in ("docx", "dotx", "docm", "xlsx", "xlsm", "pptx"):
            text = _from_ooxml(path, ext)
        elif ext in ODF_EXT:
            text = _from_odf(path)
        elif ext == "epub":
            text = _from_epub(path)
        elif ext == "pdf":
            text = _from_pdf(path)
            if ocr and len(text) < 40 and path.stat().st_size <= MAX_PDF_BYTES and ocr_available():
                text = _ocr_pdf(path)
        elif ext in OLE_EXT:
            text = _from_ole(path)
        else:
            text = ""
    except Exception:
        text = ""
    return text[:max_chars]
