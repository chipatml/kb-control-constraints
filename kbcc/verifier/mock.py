"""Deterministic verifier used by tests and offline runs."""

from __future__ import annotations

from kbcc.verifier.base import VerificationRequest, VerificationResult


class MockVerifier:
    """Return scripted verdicts without calling a model.

    ``by_id`` overrides the default verdict for specific constraint ids.
    Each entry is ``(verdict, issues)``.
    """

    def __init__(
        self,
        verdict: str = "pass",
        issues: list[str] | None = None,
        by_id: dict[str, tuple[str, list[str]]] | None = None,
    ) -> None:
        self.verdict = verdict
        self.issues = list(issues or [])
        self.by_id = by_id or {}
        self.calls: list[VerificationRequest] = []

    def verify(self, request: VerificationRequest) -> VerificationResult:
        self.calls.append(request)
        if request.constraint_id in self.by_id:
            verdict, issues = self.by_id[request.constraint_id]
            return VerificationResult(request.constraint_id, verdict, tuple(issues))
        return VerificationResult(request.constraint_id, self.verdict, tuple(self.issues))
