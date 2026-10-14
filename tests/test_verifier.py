"""Verifier prompt, mock verifier, and OpenAI-compatible response parsing."""

import io
import json
import urllib.error
import urllib.request
from email.message import Message

import pytest

from kbcc.errors import VerifierError
from kbcc.verifier.base import VerificationRequest
from kbcc.verifier.mock import MockVerifier
from kbcc.verifier.openai_client import OpenAICompatibleVerifier, parse_chat_completion
from kbcc.verifier.prompt import VERIFIER_PROMPT_TEMPLATE, render_prompt


def test_prompt_asks_for_the_required_checks():
    text = render_prompt(constraint_id="c1", card="CARD TEXT", condition="none", record_json="{}")
    assert "CARD TEXT" in text
    assert "Constraint id: c1" in text
    assert "Condition: none" in text
    for word in ("shall", "must", "should", "recommended", "pass", "fail", "unsure", "issues"):
        assert word in VERIFIER_PROMPT_TEMPLATE
    assert '"verdict"' in text


def test_mock_verifier_records_calls_and_overrides_by_id():
    verifier = MockVerifier(verdict="pass", by_id={"c2": ("fail", ["quote does not support the value"])})
    request = VerificationRequest("c2", "CARD", "PROMPT")
    result = verifier.verify(request)
    assert verifier.calls == [request]
    assert result.verdict == "fail"
    assert result.issues == ("quote does not support the value",)


def test_parse_fenced_json_verdict():
    raw = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"id": "c1", "verdict": "PASS", "issues": []}\n```',
                    }
                }
            ]
        }
    )
    result = parse_chat_completion(raw)
    assert result.constraint_id == "c1"
    assert result.verdict == "pass"
    assert result.issues == ()


def test_client_posts_to_chat_completions(monkeypatch):
    captured: dict = {}

    class _Response:
        def read(self) -> bytes:
            body = {"choices": [{"message": {"content": '{"id": "c1", "verdict": "fail", "issues": ["quote"]}'}}]}
            return json.dumps(body).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    verifier = OpenAICompatibleVerifier(api_key="sk-test", base_url="https://example.invalid/v1/", model="mock-model")
    result = verifier.verify(VerificationRequest("c1", "CARD", "PROMPT"))
    assert captured["url"] == "https://example.invalid/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "mock-model"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["messages"][1]["content"] == "PROMPT"
    assert result.verdict == "fail"
    assert result.issues == ("quote",)


def test_http_error_is_a_verifier_error(monkeypatch):
    def fake_urlopen(request, timeout=0):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            Message(),
            io.BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    verifier = OpenAICompatibleVerifier(api_key="sk-test", base_url="https://example.invalid/v1")
    with pytest.raises(VerifierError, match="HTTP 401"):
        verifier.verify(VerificationRequest("c1", "CARD", "PROMPT"))


def test_client_is_unavailable_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAICompatibleVerifier().available is False
    assert OpenAICompatibleVerifier(api_key="sk-test").available is True
