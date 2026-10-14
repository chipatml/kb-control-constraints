"""Write the controller document as deterministic JSON."""

from __future__ import annotations

import json
from pathlib import Path


def write_json(document: dict, path: Path) -> None:
    """Write ``document`` with sorted keys and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
