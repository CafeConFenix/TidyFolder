"""Optional topic detection through the Anthropic Messages API (standard library only)."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from .categories import TOPIC_IDS

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
SNIPPET_CHARS = 2000


class AIError(Exception):
    """Raised when the AI request fails. ``fatal`` errors (bad key) should not be retried."""

    def __init__(self, message: str, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal


SYSTEM_PROMPT = (
    "You classify documents by topic. Reply with ONLY a JSON object like "
    '{"topic": "<id>"}. Valid ids: ' + ", ".join(TOPIC_IDS) + ", general. "
    "Use 'general' when no topic clearly fits. The document may be in any language."
)


class ClaudeClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key.strip()
        self.model = model.strip()

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
        }
        last_error = "unknown error"
        for attempt in range(3):
            request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
                except Exception:
                    pass
                last_error = f"HTTP {exc.code}: {detail or exc.reason}"
                if exc.code in (400, 401, 403, 404):
                    raise AIError(last_error, fatal=True) from exc
                if exc.code in (429, 500, 502, 503, 529):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise AIError(last_error) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"Network error: {getattr(exc, 'reason', exc)}"
                time.sleep(1.0)
        raise AIError(last_error)

    def classify(self, filename: str, text: str) -> str:
        snippet = re.sub(r"\s+", " ", text)[:SNIPPET_CHARS]
        content = f"File name: {filename}\n\nText excerpt:\n{snippet or '(no readable text)'}"
        data = self._post(
            {
                "model": self.model,
                "max_tokens": 30,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": content}],
            }
        )
        reply = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        match = re.search(r'"topic"\s*:\s*"([a-z_]+)"', reply)
        topic = match.group(1) if match else reply.strip().lower()
        return topic if topic in TOPIC_IDS else "docs_general"

    def test(self) -> None:
        self._post(
            {
                "model": self.model,
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Reply with OK."}],
            }
        )
