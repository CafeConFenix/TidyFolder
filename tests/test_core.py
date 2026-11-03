import zipfile
from pathlib import Path

from tidyfolder.categories import category_for_extension, folder_name
from tidyfolder.classifier import Classifier, keyword_topic
from tidyfolder.extractors import extract_text
from tidyfolder.organizer import build_plan, execute_plan, journal_size, undo_last


def _ocr_ready() -> bool:
    """OCR tests only run where Pillow, pypdfium2 and a Tesseract engine exist (not on plain CI)."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    from tidyfolder.extractors import ocr_available
    return ocr_available()


def make_docx(path: Path, text: str) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", f"<w:document><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:document>")


def test_extension_categories():
    assert category_for_extension(".JPG") == "photos"
    assert category_for_extension("mp4") == "videos"
    assert category_for_extension("flac") == "audio"
    assert category_for_extension("pdf") == "document"
    assert category_for_extension("xyz") == "other"


def test_keywords_both_languages():
    assert keyword_topic("a.txt", "Factura del banco, pago del IVA") == "finance"
    assert keyword_topic("a.txt", "Hotel booking, flight and passport") == "travel"
    assert keyword_topic("Mi_CV_2024.pdf", "") == "work"
    assert keyword_topic("a.txt", "hello world") == "docs_general"


def test_folder_names_follow_language():
    assert folder_name("photos", "en") == "Photos"
    assert folder_name("photos", "es") == "Fotos"


def test_extract_docx_and_txt(tmp_path):
    make_docx(tmp_path / "c.docx", "Contrato de alquiler con clausulas legales")
    assert "alquiler" in extract_text(tmp_path / "c.docx")
    (tmp_path / "n.txt").write_text("receta medica del doctor", encoding="utf-8")
    assert "doctor" in extract_text(tmp_path / "n.txt")


def test_plan_execute_and_undo(tmp_path):
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "sub" / "clip.mp4").write_bytes(b"x")
    (tmp_path / "sub" / "deep" / "song.mp3").write_bytes(b"x")
    (tmp_path / "bill.txt").write_text("factura banco pago iva", encoding="utf-8")
    make_docx(tmp_path / "sub" / "legal.docx", "contrato clausula abogado tribunal")
    (tmp_path / "weird.xyz").write_bytes(b"x")

    items = build_plan(tmp_path, tmp_path, Classifier("keywords"))
    cats = {i.src.name: i.category for i in items}
    assert cats == {"a.jpg": "photos", "clip.mp4": "videos", "song.mp3": "audio",
                    "bill.txt": "finance", "legal.docx": "legal", "weird.xyz": "other"}

    journal = tmp_path.parent / "journal_test.json"
    next(i for i in items if i.src.name == "a.jpg").action = "copy"
    res = execute_plan(items, tmp_path, tmp_path, "es", remove_empty=True, journal=journal)
    assert not res.errors and res.copied == 1 and res.moved == 5
    assert (tmp_path / "Fotos" / "a.jpg").exists() and (tmp_path / "a.jpg").exists()
    assert (tmp_path / "Vídeos" / "clip.mp4").exists()
    assert (tmp_path / "Audios" / "song.mp3").exists()
    assert (tmp_path / "Finanzas" / "bill.txt").exists()
    assert not (tmp_path / "sub").exists()  # emptied folders removed
    assert journal_size(journal) == 6

    # Running again must not touch already organized folders.
    again = build_plan(tmp_path, tmp_path, Classifier("keywords"))
    assert [i.src.name for i in again] == ["a.jpg"]  # only the copied original is left

    undone = undo_last(journal)
    assert not undone.errors and undone.ok == 6
    assert (tmp_path / "sub" / "deep" / "song.mp3").exists()
    assert (tmp_path / "a.jpg").exists() and not (tmp_path / "Fotos").exists()


def test_name_collisions(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "a.jpg").write_bytes(b"1")
    (tmp_path / "x" / "a.jpg").write_bytes(b"2")
    items = build_plan(tmp_path, tmp_path, Classifier("keywords"))
    res = execute_plan(items, tmp_path, tmp_path, "en", journal=tmp_path.parent / "j2.json")
    assert res.moved == 2
    assert sorted(p.name for p in (tmp_path / "Photos").iterdir()) == ["a (1).jpg", "a.jpg"]


# ------------------------------------------------------------------ privacy / secrets
class _ExplodingAI:
    """Fake AI client that records every document it is asked about."""

    def __init__(self):
        self.seen = []

    def classify(self, filename, text):
        self.seen.append(filename)
        return "science"


def _ai_classifier(**kw):
    c = Classifier("keywords", **kw)
    c.ai = _ExplodingAI()
    return c


def test_ai_never_sees_sensitive_documents(tmp_path):
    (tmp_path / "tax.txt").write_text("factura banco pago iva impuesto", encoding="utf-8")
    (tmp_path / "paper.txt").write_text("hello there", encoding="utf-8")
    c = _ai_classifier(keep_sensitive_offline=True)
    assert c.classify(tmp_path / "tax.txt") == ("finance", "keywords")
    assert c.classify(tmp_path / "paper.txt") == ("science", "ai")
    assert c.ai.seen == ["paper.txt"]


def test_ai_respects_excluded_folders(tmp_path):
    (tmp_path / "Private").mkdir()
    (tmp_path / "Private" / "diary.txt").write_text("hello there", encoding="utf-8")
    c = _ai_classifier(exclude_folders=["private"])
    assert c.classify(tmp_path / "Private" / "diary.txt")[1] == "keywords"
    assert c.ai.seen == []


def test_ai_receives_everything_when_filter_is_off(tmp_path):
    (tmp_path / "tax.txt").write_text("factura banco pago iva impuesto", encoding="utf-8")
    c = _ai_classifier(keep_sensitive_offline=False)
    assert c.classify(tmp_path / "tax.txt") == ("science", "ai")


def test_api_key_goes_to_keyring_not_to_the_file(tmp_path):
    import sys, types
    import tidyfolder.config as cfg

    store = {}
    fake = types.ModuleType("keyring")
    fake.set_password = lambda s, u, v: store.__setitem__((s, u), v)
    fake.get_password = lambda s, u: store.get((s, u))
    fake.delete_password = lambda s, u: store.pop((s, u), None)
    fake.get_keyring = lambda: types.SimpleNamespace(priority=5)
    old_mod, old_dir = sys.modules.get("keyring"), cfg.data_dir
    sys.modules["keyring"], cfg.data_dir = fake, (lambda: tmp_path / "data")
    try:
        s = cfg.Settings(api_key="sk-secret", language="en")
        s.save()
        assert "sk-secret" not in cfg.settings_path().read_text(encoding="utf-8")
        assert cfg.Settings.load().api_key == "sk-secret"
        assert cfg.secure_storage_available()
    finally:
        cfg.data_dir = old_dir
        if old_mod is None:
            sys.modules.pop("keyring", None)
        else:
            sys.modules["keyring"] = old_mod


def test_api_key_falls_back_to_file_without_keyring(tmp_path):
    import sys
    import tidyfolder.config as cfg

    old_mod, old_dir = sys.modules.get("keyring"), cfg.data_dir
    sys.modules["keyring"] = None  # makes "import keyring" fail
    cfg.data_dir = lambda: tmp_path / "data"
    try:
        cfg.Settings(api_key="sk-plain", language="en").save()
        assert cfg.Settings.load().api_key == "sk-plain"
        assert not cfg.secure_storage_available()
    finally:
        cfg.data_dir = old_dir
        if old_mod is None:
            sys.modules.pop("keyring", None)
        else:
            sys.modules["keyring"] = old_mod


def test_ocr_flag_is_harmless_without_tesseract(tmp_path):
    from tidyfolder.extractors import ocr_available
    # Minimal PDF with no text: must not crash whether or not OCR is installed.
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
    assert extract_text(tmp_path / "scan.pdf", ocr=True) == ""
    assert isinstance(ocr_available(), bool)


# ------------------------------------------------------------------ bundled OCR
def test_prepare_script_copies_only_engine_files(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "prepare_tesseract", Path(__file__).resolve().parent.parent / "scripts" / "prepare_tesseract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fake = tmp_path / "install"
    fake.mkdir()
    for name in ("tesseract.exe", "a.dll", "ambiguous_words.exe", "notes.txt"):
        (fake / name).write_bytes(b"x")
    mod.VENDOR = tmp_path / "vendor" / "tesseract"
    mod.copy_engine(fake)
    assert sorted(p.name for p in mod.VENDOR.iterdir()) == ["a.dll", "tesseract.exe"]


def test_bundled_engine_is_preferred(tmp_path):
    from tidyfolder import extractors as ex

    bundle = tmp_path / "tesseract"
    (bundle / "tessdata").mkdir(parents=True)
    (bundle / "tesseract.exe").write_bytes(b"x")
    old = ex._bundled_dir
    ex._bundled_dir = lambda: bundle
    try:
        assert ex._find_tesseract() == str(bundle / "tesseract.exe")
        assert ex._tessdata_dir() == str(bundle / "tessdata")
    finally:
        ex._bundled_dir = old


def test_scanned_pdf_is_read_with_ocr_when_available(tmp_path):
    if not _ocr_ready():
        return  # OCR packages/engine not installed on this machine
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1240, 500), "white")
    ImageDraw.Draw(img).text((60, 100), "INVOICE bank payment tax", fill="black", font=ImageFont.load_default(size=40))
    img.save(tmp_path / "scan.pdf", "PDF", resolution=150)
    assert keyword_topic("scan.pdf", extract_text(tmp_path / "scan.pdf", ocr=True)) == "finance"
    assert Classifier("keywords", ocr=False).classify(tmp_path / "scan.pdf")[0] == "docs_general"


def test_ocr_status_reports_the_reason():
    from tidyfolder import extractors as ex

    state, detail = ex.ocr_status()
    assert state in ("ok", "no_packages", "no_engine")
    old = ex._find_tesseract
    ex._find_tesseract = lambda: None
    try:
        if state != "no_packages":
            assert ex.ocr_status() == ("no_engine", "")
            assert not ex.ocr_available()
    finally:
        ex._find_tesseract = old


def test_prepare_script_installs_when_missing(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "prepare_tesseract2", Path(__file__).resolve().parent.parent / "scripts" / "prepare_tesseract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fake = tmp_path / "Tesseract-OCR"
    fake.mkdir()
    (fake / "tesseract.exe").write_bytes(b"x")
    calls = {"installed": False}
    mod.VENDOR = tmp_path / "vendor" / "tesseract"
    # Not installed at first; the "installer" makes it appear.
    mod.find_install = lambda explicit: fake if calls["installed"] else None
    mod.install_tesseract = lambda: calls.__setitem__("installed", True)
    import sys
    old = sys.argv
    sys.argv = ["prepare_tesseract.py", "--no-download"]
    try:
        mod.main()
    finally:
        sys.argv = old
    assert calls["installed"] and (mod.VENDOR / "tesseract.exe").exists()


def test_user_folders_named_like_categories_are_scanned(tmp_path):
    (tmp_path / "Trabajo" / "clientes").mkdir(parents=True)
    (tmp_path / "Otros" / "viejo").mkdir(parents=True)
    (tmp_path / "Trabajo" / "clientes" / "informe.txt").write_text("informe del cliente reunion propuesta", encoding="utf-8")
    (tmp_path / "Trabajo" / "nomina.txt").write_text("nomina salario banco pago", encoding="utf-8")
    (tmp_path / "Otros" / "viejo" / "factura.txt").write_text("factura banco iva pago", encoding="utf-8")
    found = {i.src.relative_to(tmp_path).as_posix(): i.category
             for i in build_plan(tmp_path, tmp_path, Classifier("keywords"))}
    # the work report is already where it belongs only if it sits directly in Trabajo/
    assert found == {"Trabajo/clientes/informe.txt": "work",
                     "Trabajo/nomina.txt": "finance",
                     "Otros/viejo/factura.txt": "finance"}
    assert [i.src.name for i in build_plan(tmp_path, tmp_path, Classifier("keywords"), recursive=False)] == []


def test_ocr_is_thread_safe_and_gives_same_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    if not _ocr_ready():
        return
    from PIL import Image, ImageDraw, ImageFont
    for i in range(4):
        img = Image.new("RGB", (1240, 500), "white")
        ImageDraw.Draw(img).text((60, 100), "INVOICE bank payment tax", fill="black",
                                 font=ImageFont.load_default(size=40))
        img.save(tmp_path / f"s{i}.pdf", "PDF", resolution=150)
    with ThreadPoolExecutor(4) as pool:
        texts = list(pool.map(lambda i: extract_text(tmp_path / f"s{i}.pdf", ocr=True), range(4)))
    assert all("INVOICE" in t for t in texts)


def test_huge_pdfs_are_not_read(tmp_path):
    import tidyfolder.extractors as ex
    (tmp_path / "plan.pdf").write_bytes(b"%PDF-1.4 " + b"0" * 2000)
    old_limit, old_ocr = ex.MAX_PDF_BYTES, ex._ocr_pdf
    ex.MAX_PDF_BYTES = 100
    ex._ocr_pdf = lambda path: (_ for _ in ()).throw(AssertionError("OCR must not run on huge PDFs"))
    try:
        assert extract_text(tmp_path / "plan.pdf", ocr=True) == ""
    finally:
        ex.MAX_PDF_BYTES, ex._ocr_pdf = old_limit, old_ocr


def test_child_processes_never_open_a_console_window():
    import types
    from tidyfolder.extractors import hidden_process_kwargs

    class StartupInfo:
        dwFlags = 0
        wShowWindow = 1

    fake = types.SimpleNamespace(STARTUPINFO=StartupInfo, STARTF_USESHOWWINDOW=1, SW_HIDE=0,
                                 CREATE_NO_WINDOW=0x08000000, BELOW_NORMAL_PRIORITY_CLASS=0x4000)
    kw = hidden_process_kwargs(windows=True, sp=fake)
    assert kw["creationflags"] & 0x08000000          # CREATE_NO_WINDOW
    assert kw["startupinfo"].dwFlags & 1 and kw["startupinfo"].wShowWindow == 0  # SW_HIDE
    assert hidden_process_kwargs(windows=False) == {}
