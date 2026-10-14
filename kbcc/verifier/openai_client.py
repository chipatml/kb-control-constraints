"""OpenAI-compatible chat client for the consistency-card verifier.

The client is optional. It reads ``OPENAI_API_KEY``, ``OPENAI_BASE_URL``
(default ``https://api.openai.com/v1``), and ``OPENAI_MODEL`` (default
``gpt-4o-mini``). When the key is absent, ``available`` is false and the
pipeline does not call the network.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from kbcc.errors import VerifierError
from kbcc.verifier.base import VerificationRequest, VerificationResult

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class OpenAICompatibleVerifier:
    """POST one card prompt to ``{base_url}/chat/completions``."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def verify(self, request: VerificationRequest) -> VerificationResult:
        if not self.api_key:
            raise VerifierError("OPENAI_API_KEY is unset.")
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You return only a JSON object."},
                {"role": "user", "content": request.prompt},
            ],
        }
        payload = json.dumps(body).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise VerifierError(f"OpenAI-compatible endpoint returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise VerifierError(f"OpenAI-compatible endpoint request failed: {exc.reason}") from exc
        return parse_chat_completion(raw)


def parse_chat_completion(raw: str) -> VerificationResult:
    """Parse a chat-completion body into a verdict."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerifierError("Verifier response was not JSON.") from exc
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VerifierError("Verifier response did not contain a chat message.") from exc
    if not isinstance(content, str):
        raise VerifierError("Verifier message content was not a string.")
    data = _extract_json(content)
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in {"pass", "fail", "unsure"}:
        raise VerifierError(f"Verifier verdict {verdict!r} is not pass, fail, or unsure.")
    issues_raw = data.get("issues", [])
    if not isinstance(issues_raw, list):
        raise VerifierError("Verifier issues must be a list.")
    constraint_id = str(data.get("id", ""))
    return VerificationResult(
        constraint_id=constraint_id,
        verdict=verdict,
        issues=tuple(str(item) for item in issues_raw),
    )


def _extract_json(content: str) -> dict:
    text = _FENCE.sub("", content.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VerifierError("Verifier message was not a JSON object.") from exc
    if not isinstance(data, dict):
        raise VerifierError("Verifier message JSON must be an object.")
    return data
