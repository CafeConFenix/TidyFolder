"""Persistent user settings (stored next to the .exe when portable).

The Anthropic API key is kept in the operating-system credential store through the
optional ``keyring`` package (Windows Credential Manager, macOS Keychain, Secret
Service). Only when no secure store is available is it written to the settings file.
"""
from __future__ import annotations

import json
import locale
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-5-5"
KEYRING_SERVICE = "TidyFolder"
KEYRING_USER = "anthropic_api_key"


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


# ---------------------------------------------------------------- secure secret
def _keyring():
    try:
        import keyring

        return keyring
    except Exception:
        return None


def secure_storage_available() -> bool:
    """True when a real OS credential store can be used for the API key."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        return getattr(kr.get_keyring(), "priority", 0) > 0
    except Exception:
        return False


def load_secret() -> str:
    kr = _keyring()
    if kr is None:
        return ""
    try:
        return kr.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception:
        return ""


def store_secret(value: str) -> bool:
    """Save (or delete when empty) the key in the credential store. Returns success."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        if value:
            kr.set_password(KEYRING_SERVICE, KEYRING_USER, value)
        else:
            try:
                kr.delete_password(KEYRING_SERVICE, KEYRING_USER)
            except Exception:
                pass
        return True
    except Exception:
        return False


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
    ai_consent: bool = False  # the user accepted the AI privacy notice
    ai_keep_offline: bool = True  # never send finance/health/legal documents to the AI
    ai_exclude_folders: str = ""  # comma-separated folder names never sent to the AI
    ocr: bool = True  # read scanned PDFs with the bundled Tesseract engine

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
        if not settings.api_key:
            settings.api_key = load_secret()
        return settings

    def save(self) -> None:
        data = asdict(self)
        # A key left in the file by an older version is migrated to the secure store here.
        if store_secret(self.api_key):
            data["api_key"] = ""
        try:
            path = settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass
