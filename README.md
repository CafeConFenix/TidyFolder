# 🗂 TidyFolder

A simple, good-looking desktop app that **sorts messy folders for you**. It reads your documents, detects their topic, and files everything into tidy folders — in **English or Spanish**.

## Features

- **Bilingual interface** (English / Español) that switches instantly. Folder names are created in the language you are using (`Photos` / `Fotos`, `Finance` / `Finanzas`, …).
- **Reads many formats**: PDF, Word (`docx`), Excel (`xlsx`), PowerPoint (`pptx`), OpenDocument (`odt/ods/odp`), RTF, EPUB, HTML, TXT, Markdown, CSV, e-mail (`eml`) and legacy Office files (`doc/xls/ppt`, best effort).
- **Sorts documents by topic**: Finance, Legal, Health, Education, Work, Travel, Technology, Home, Science, Shopping (or *Other documents*).
- **All photos in one folder, all videos in another, all audio in another.** Archives, software and code files get their own folders too.
- **Searches subfolders** of the main folder (optional).
- **Preview before touching anything**: review every file, uncheck what you want to skip, and choose **Move** or **Copy** per file — or for all files at once.
- **Choose any destination folder** (default: the same folder you are organizing).
- **Undo** the last run in one click.
- **Two topic-detection modes** (Settings):
  - *Keywords (offline)* — free, private, works without internet.
  - *Claude AI (online)* — more accurate; uses your own Anthropic API key.
- Safe by design: never overwrites files (name clashes become `name (1).ext`), refuses to organize drive roots, your home folder or system folders, and skips folders it already created.

## Download (portable .exe)

Go to the **Actions** tab → *Build portable .exe* → *Run workflow*, then download the `TidyFolder-portable-windows` artifact. When you publish a tag such as `v1.0.0`, the `.exe` is attached to the GitHub Release automatically.

No installation needed: just run `TidyFolder.exe`. Settings are saved in a `TidyFolder_data` folder next to the program.

## Run from source

```bash
git clone https://github.com/<your-user>/TidyFolder.git
cd TidyFolder
python -m pip install -r requirements.txt
python run.py
```

Requires Python 3.10+ (with Tkinter, included in the official Windows/macOS installers).

## Build the .exe yourself

On Windows, double-click **`build.bat`** (or run it in a terminal). The result is `dist\TidyFolder.exe`.
On Linux/macOS use `./build.sh` (PyInstaller builds for the OS it runs on).

## How it works

1. **Scan** the chosen folder (and subfolders).
2. **Classify** each file:
   - by extension → photos, videos, audio, archives, software, code;
   - documents → text is extracted and scored against English + Spanish keyword lists (the file name counts extra), or sent to Claude in AI mode.
3. **Preview** the plan in a table. Edit it freely.
4. **Apply** it: files are moved or copied into folders created inside the destination folder. A journal of the operations is saved so that **Undo** can restore everything.

### Folders created

| Key | English | Español |
|---|---|---|
| photos | Photos | Fotos |
| videos | Videos | Vídeos |
| audio | Audio | Audios |
| archives | Archives | Comprimidos |
| software | Software | Programas |
| code | Code | Código |
| finance | Finance | Finanzas |
| legal | Legal | Legal |
| health | Health | Salud |
| education | Education | Educación |
| work | Work | Trabajo |
| travel | Travel | Viajes |
| technology | Technology | Tecnología |
| home | Home | Hogar |
| science | Science | Ciencia |
| shopping | Shopping | Compras |
| docs_general | Other documents | Otros documentos |
| other | Other files | Otros archivos |

Folders that already have one of these names inside the destination are treated as "already organized" and are not scanned again.

## AI mode and privacy

In AI mode, for each **document** the app sends the file name and the first ~2,000 characters of extracted text to the Anthropic API (`https://api.anthropic.com/v1/messages`) using **your** API key. Photos, videos and audio are never sent. If the AI is unavailable the app falls back to keywords automatically. You can also provide the key through the `ANTHROPIC_API_KEY` environment variable. The default model is configurable in Settings.

> The API key is stored in plain text in the settings file. Do not share that file.

## Limitations

- Scanned PDFs and images are not OCR'd (they are classified by file name only).
- Legacy `.doc/.xls/.ppt` text recovery is approximate.
- Keyword topics are generic; edit `tidyfolder/categories.py` to tune them to your needs.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

```
tidyfolder/
  categories.py   file types, topic keywords, bilingual folder names
  extractors.py   text extraction for each document format
  classifier.py   keyword scoring + optional AI classification
  ai.py           minimal Anthropic Messages API client (stdlib only)
  organizer.py    scan, plan, move/copy, journal and undo
  config.py       persistent settings
  i18n.py         English / Spanish UI strings
  gui.py          CustomTkinter interface
```

Contributions are welcome — new languages only need a new block in `i18n.py` and a column in `FOLDER_NAMES`.

## License

MIT — see [LICENSE](LICENSE).
