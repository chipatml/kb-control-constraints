"""Fixed-format consistency cards and their SHA-256 digests."""

from __future__ import annotations

import hashlib


def render_card(
    *,
    constraint_id: str,
    subject: str,
    variable: str,
    operator: str,
    si_value: str,
    si_unit: str,
    original_value: str,
    original_unit: str,
    hardness: str,
    source_doc: str,
    page: int,
    quote: str,
) -> str:
    """Render the LLM-readable card. The SHA-256 is taken over this exact string."""
    return (
        f"CONSTRAINT {constraint_id}: {subject}.{variable} {operator} {si_value} {si_unit} "
        f"(original: {original_value} {original_unit}; hardness: {hardness}). "
        f'SOURCE: {source_doc} p.{page}: "{quote}"'
    )


def card_sha256(card: str) -> str:
    """Hex SHA-256 of the card's UTF-8 bytes."""
    return hashlib.sha256(card.encode("utf-8")).hexdigest()
