"""In-memory constraint records selected from the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ConstraintRecord:
    """One constraint row, with the decimal kept separate from its lexical form."""

    id: str
    uri: str
    subject_uri: str
    subject_name: str
    variable: str
    operator: str
    value: Decimal
    value_lexical: str
    unit_uri: str
    unit_name: str
    hardness: str
    source_doc: str
    page: int
    quote: str
    zone_uri: str | None
    zone_name: str | None
    human_present: bool | None
