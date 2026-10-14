#!/usr/bin/env python3
"""Download the QUDT unit vocabulary as Turtle.

The full graph is large. Tests use the trimmed fixture at
``data/qudt_units_fixture.ttl`` and do not need this download.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

QUDT_UNITS_URL = "https://qudt.org/2.1/vocab/unit"


def download(url: str, dest: Path, timeout: float = 120.0) -> None:
    """Fetch ``url`` and write the bytes to ``dest``.

    Raises ``RuntimeError`` when the body does not look like Turtle.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "kbcc-qudt-download"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if b"@prefix" not in data and b"qudt:" not in data:
        raise RuntimeError(f"Response from {url} does not look like a Turtle document.")
    dest.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the QUDT units Turtle graph.")
    parser.add_argument("--url", default=QUDT_UNITS_URL, help=f"Source URL (default: {QUDT_UNITS_URL})")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination path, for example data/qudt/VOCAB_QUDT-UNITS-ALL.ttl",
    )
    args = parser.parse_args(argv)
    download(args.url, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
