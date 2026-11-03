"""Decide which category (folder) every file belongs to."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable

from .ai import AIError, ClaudeClient
from .categories import COMPILED_KEYWORDS, category_for_extension, normalize
from .config import DEFAULT_MODEL
from .extractors import extract_text

MIN_SCORE = 3
_PER_KEYWORD_CAP = 5
_FILENAME_BONUS = 3
SENSITIVE_TOPICS = {"finance", "health", "legal"}


def keyword_topic(filename: str, text: str, min_score: int = MIN_SCORE) -> str:
    """Pick the topic whose keywords appear most often (file name counts extra)."""
    stem = Path(filename).stem
    name = normalize(stem.replace("_", " ").replace("-", " ").replace(".", " "))
    body = normalize(text)
    best_topic, best_score = "docs_general", 0
    for topic, patterns in COMPILED_KEYWORDS.items():
        score = 0
        for pattern in patterns:
            score += min(len(pattern.findall(body)), _PER_KEYWORD_CAP)
            if pattern.search(name):
                score += _FILENAME_BONUS
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic if best_score >= min_score else "docs_general"


def parse_folder_list(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


class Classifier:
    """Thread-safe classifier supporting offline keywords and optional Claude AI.

    Privacy controls for AI mode: documents inside *exclude_folders* are never sent,
    and with *keep_sensitive_offline* documents that the offline keywords recognise as
    finance, health or legal are classified locally instead of being sent.
    """

    def __init__(
        self,
        mode: str = "keywords",
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        keep_sensitive_offline: bool = True,
        exclude_folders: Iterable[str] = (),
        ocr: bool = False,
    ):
        self.mode = mode
        self.ai: ClaudeClient | None = ClaudeClient(api_key, model) if mode == "ai" and api_key else None
        self.ai_error: str | None = None
        self.keep_sensitive_offline = keep_sensitive_offline
        self.exclude_folders = {name.lower() for name in exclude_folders}
        self.ocr = ocr
        self._lock = threading.Lock()

    def _is_excluded(self, path: Path) -> bool:
        return any(part.lower() in self.exclude_folders for part in path.parts[:-1])

    def classify(self, path: Path) -> tuple[str, str]:
        """Return ``(category_key, method)`` where method is extension/keywords/ai."""
        category = category_for_extension(path.suffix)
        if category != "document":
            return category, "extension"
        text = extract_text(path, ocr=self.ocr)
        offline = keyword_topic(path.name, text)
        client = self.ai
        if client is None or self._is_excluded(path):
            return offline, "keywords"
        if self.keep_sensitive_offline and offline in SENSITIVE_TOPICS:
            return offline, "keywords"
        try:
            return client.classify(path.name, text), "ai"
        except AIError as exc:
            with self._lock:
                self.ai_error = str(exc)
                if exc.fatal:
                    self.ai = None
        return offline, "keywords"
