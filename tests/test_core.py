import zipfile
from pathlib import Path

from tidyfolder.categories import category_for_extension, folder_name
from tidyfolder.classifier import Classifier, keyword_topic
from tidyfolder.extractors import extract_text
from tidyfolder.organizer import build_plan, execute_plan, journal_size, undo_last


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
