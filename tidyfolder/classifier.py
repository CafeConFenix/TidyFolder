"""Decide which category (folder) every file belongs to."""
from __future__ import annotations

import threading
from pathlib import Path

from .ai import AIError, ClaudeClient
from .categories import COMPILED_KEYWORDS, category_for_extension, normalize
from .config import DEFAULT_MODEL
from .extractors import extract_text

MIN_SCORE = 3
_PER_KEYWORD_CAP = 5
_FILENAME_BONUS = 3


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


class Classifier:
    """Thread-safe classifier supporting offline keywords and optional Claude AI."""

    def __init__(self, mode: str = "keywords", api_key: str = "", model: str = DEFAULT_MODEL):
        self.mode = mode
        self.ai: ClaudeClient | None = ClaudeClient(api_key, model) if mode == "ai" and api_key else None
        self.ai_error: str | None = None
        self._lock = threading.Lock()

    def classify(self, path: Path) -> tuple[str, str]:
        """Return ``(category_key, method)`` where method is extension/keywords/ai."""
        category = category_for_extension(path.suffix)
        if category != "document":
            return category, "extension"
        text = extract_text(path)
        client = self.ai
        if client is not None:
            try:
                return client.classify(path.name, text), "ai"
            except AIError as exc:
                with self._lock:
                    self.ai_error = str(exc)
                    if exc.fatal:
                        self.ai = None
        return keyword_topic(path.name, text), "keywords"
