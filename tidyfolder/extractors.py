"""Read text from many document formats (best effort, never raises)."""
from __future__ import annotations

import html
import logging
import re
import zipfile
from pathlib import Path

logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_CHARS = 20_000
_XML_LIMIT = 2_000_000  # bytes read from each XML part inside a zip

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
    for page in reader.pages[:12]:
        parts.append(page.extract_text() or "")
        if sum(len(p) for p in parts) > MAX_CHARS:
            break
    return _clean(" ".join(parts))


def _from_ole(path: Path) -> str:
    """Very rough text recovery for legacy .doc/.xls/.ppt files."""
    with open(path, "rb") as fh:
        data = fh.read(400_000)
    text = data.replace(b"\x00", b"").decode("cp1252", errors="ignore")
    runs = re.findall(r"[A-Za-zÀ-ÿ0-9 ,.;:()/\-]{8,}", text)
    return _clean(" ".join(runs))


def extract_text(path: Path | str, max_chars: int = MAX_CHARS) -> str:
    """Return the readable text of *path* (empty string when unsupported or on error)."""
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
        elif ext in OLE_EXT:
            text = _from_ole(path)
        else:
            text = ""
    except Exception:
        text = ""
    return text[:max_chars]
