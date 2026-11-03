<div align="center">

# 🗂 TidyFolder

**Sort a messy folder by *what your documents are about* — not just by file extension.**
Bilingual (English / Español) · Preview every move · One-click undo · Works offline

### [⬇ Download TidyFolder.exe](https://github.com/<your-user>/TidyFolder/releases/latest/download/TidyFolder.exe)

*Portable: no installer, just run it. Windows 10/11.*

</div>

<!--
SCREENSHOTS (add real images to docs/screenshots/ and uncomment):

![Plan preview](docs/screenshots/preview.png)
![Settings](docs/screenshots/settings.png)
![Result](docs/screenshots/result.png)
-->

## Why TidyFolder?

Most sorters just look at the file extension. TidyFolder also **reads your PDFs, Word, Excel and PowerPoint files, detects the topic (finance, legal, health, travel…) and files them accordingly** — then shows you the plan *before* touching anything.

| | Typical sorters (extension / rules) | **TidyFolder** |
|---|:---:|:---:|
| Sorts photos, videos and audio into one folder each | ✅ | ✅ |
| Sorts documents by **topic from their content** | ❌ | ✅ |
| Interface and **folder names in English or Spanish** | ❌ | ✅ |
| **Preview** of every move, with per-file include/exclude | Varies | ✅ |
| Choose **Move or Copy per file** (or for all at once) | Varies | ✅ |
| **One-click undo** | Varies | ✅ |
| Works **fully offline** | Varies | ✅ |
| Optional **AI topic detection** with privacy controls | ❌ | ✅ |
| Portable single `.exe`, free and open source | Varies | ✅ |

*"Typical" describes the general category of simple extension-based sorters, not any specific product.*

## Features

- **Reads many formats**: PDF, Word (`docx`), Excel (`xlsx`), PowerPoint (`pptx`), OpenDocument (`odt/ods/odp`), RTF, EPUB, HTML, TXT, Markdown, CSV, e-mail (`eml`) and legacy Office files (`doc/xls/ppt`, best effort).
- **Topics**: Finance, Legal, Health, Education, Work, Travel, Technology, Home, Science, Shopping, or *Other documents*.
- **All photos in one folder, all videos in another, all audio in another.** Archives, software and code get their own folders.
- **Searches subfolders** of the main folder (optional).
- **Any destination folder** (default: the folder you are organizing).
- **Safe by design**: never overwrites (clashes become `name (1).ext`), refuses drive roots, your home folder and system folders, leaves alone files that are already in the right folder.
- **Built-in OCR** for scanned PDFs (English + Spanish), no extra installs.

## Quick start

1. Download `TidyFolder.exe` from the [latest release](https://github.com/<your-user>/TidyFolder/releases/latest) and run it.
2. Choose the folder to organize and press **Analyze folder**.
3. Review the table. Click ☑ to exclude a file, or the *Action* column to switch **Move ⇄ Copy**.
4. Press **Organize files**. Changed your mind? **Undo last run**.

Settings are stored in a `TidyFolder_data` folder next to the `.exe` (your API key is *not* — see below).

## Privacy & security

**Offline by default.** In the default *Keywords* mode nothing leaves your computer.

**AI mode is opt-in** (Settings → *Claude AI*). When you enable it for the first time the app shows a privacy notice you must accept. For each **document** it then sends the file name and the first ~2,000 characters of extracted text to the Anthropic API using **your** key. Photos, videos and audio are never sent. Controls you have:

- **Finance, health and legal documents stay offline by default**: if the offline keywords recognise them, they are classified locally and never sent.
- **Excluded folders**: list folder names (e.g. `Taxes, Medical`) whose documents are never sent.
- If the AI is unavailable, the app falls back to keywords automatically.

**API key storage.** The key is kept in the operating-system credential store (Windows Credential Manager / macOS Keychain / Secret Service) through [`keyring`](https://pypi.org/project/keyring/), **not in the settings file**. If no secure store is available, Settings shows a visible warning and the key is saved in plain text. You can also use the `ANTHROPIC_API_KEY` environment variable and leave the field empty.

## OCR for scanned PDFs (built in)

The released `TidyFolder.exe` **already includes** the OCR engine ([Tesseract](https://github.com/tesseract-ocr/tesseract)) with Spanish and English models — nothing to install. Scanned PDFs (no embedded text) are read automatically; only the first 3 pages are processed so analysis stays fast. You can switch it off in **Settings**.

Because the engine is bundled, the `.exe` is larger than a plain Python build and takes a moment longer to start the first time.

Running from source? `pip install -r requirements.txt` installs the OCR Python packages; the engine itself needs `python scripts/prepare_tesseract.py` (Windows; it copies an installed Tesseract and downloads the language models into `vendor/`). Third-party licenses: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Run from source

```bash
git clone https://github.com/<your-user>/TidyFolder.git
cd TidyFolder
python -m pip install -r requirements.txt
python run.py
```

Requires Python 3.10+ (Tkinter is included in the official Windows/macOS installers).

## Build the .exe yourself

On Windows, double-click **`build.bat`**. It creates the environment, **installs Tesseract automatically if needed** (Windows may ask you to accept one permission prompt), downloads the Spanish/English OCR models and produces a single **`dist\TidyFolder.exe`** that already contains everything. That one file is all anyone needs.

On Linux/macOS use `./build.sh` (no bundled OCR).

### Publish it so anyone can download it

Without any command line: on GitHub go to **Releases → Draft a new release**, create a tag such as `v1.0.0`, drag `dist\TidyFolder.exe` into the release and press **Publish**. The button at the top of this README will then download it.

Prefer automation? Push a tag and GitHub Actions builds the `.exe` and attaches it to the release for you:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

## How it works

1. **Scan** the chosen folder (and subfolders).
2. **Classify** each file: by extension (photos, videos, audio, archives, software, code) or, for documents, by scoring extracted text against English + Spanish keyword lists (the file name counts extra) — or with Claude in AI mode.
3. **Preview** the plan in a table and edit it freely.
4. **Apply** it. A journal of the operations is saved so **Undo** can restore everything.

### Folders created

| English | Español | English | Español |
|---|---|---|---|
| Photos | Fotos | Work | Trabajo |
| Videos | Vídeos | Travel | Viajes |
| Audio | Audios | Technology | Tecnología |
| Archives | Comprimidos | Home | Hogar |
| Software | Programas | Science | Ciencia |
| Code | Código | Shopping | Compras |
| Finance | Finanzas | Legal | Legal |
| Health | Salud | Education | Educación |
| Other documents | Otros documentos | Other files | Otros archivos |

Your own folders are always analysed, even if they share a name with one of these (a `Trabajo` folder, say): their files are read and sorted like any others. Only files that already sit directly in the folder where they belong are left alone, so running the app twice is safe.

## Limitations

- OCR covers scanned **PDFs**; standalone images are never OCR'd (all photos go to the photos folder). OCR quality depends on scan quality.
- Legacy `.doc/.xls/.ppt` text recovery is approximate.
- Keyword topics are generic; tune them in `tidyfolder/categories.py`.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

```
tidyfolder/
  categories.py   file types, topic keywords, bilingual folder names
  extractors.py   text extraction for each format (+ optional OCR)
  classifier.py   keyword scoring, optional AI, privacy filters
  ai.py           minimal Anthropic Messages API client (stdlib only)
  organizer.py    scan, plan, move/copy, journal and undo
  config.py       settings + secure API-key storage
  i18n.py         English / Spanish UI strings
  gui.py          CustomTkinter interface
```

New languages only need a block in `i18n.py` and a column in `FOLDER_NAMES`. Contributions welcome.

## License

MIT — see [LICENSE](LICENSE).
