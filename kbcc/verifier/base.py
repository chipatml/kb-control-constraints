"""Pluggable verifier interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerificationRequest:
    constraint_id: str
    card: str
    prompt: str


@dataclass(frozen=True)
class VerificationResult:
    constraint_id: str
    verdict: str
    issues: tuple[str, ...]


class ConstraintVerifier(Protocol):
    """Anything that can judge one consistency card."""

    def verify(self, request: VerificationRequest) -> VerificationResult:
        """Return a pass, fail, or unsure verdict for ``request``."""
