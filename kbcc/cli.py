"""Command line entry point for the constraint pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kbcc.errors import ConfigError, ConflictEngineError, DataError, UnitConversionError
from kbcc.output import write_json
from kbcc.pipeline import build_active_constraints


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document = build_active_constraints(
            graph_path=args.graph,
            shapes_path=args.shapes,
            qudt_path=args.qudt,
            config_path=args.config,
            zone=args.zone,
            human_present=args.human_present,
            skip_llm=args.skip_llm,
        )
    except (ConfigError, ConflictEngineError, DataError, UnitConversionError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    write_json(document, args.output)
    print(f"Wrote {args.output}")
    print(format_summary(document))
    needs_review = any(item["status"] != "active" for item in document["constraints"])
    if args.strict and (needs_review or not document["shacl"]["conforms"]):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    root = _default_root()
    parser = argparse.ArgumentParser(
        prog="kbcc",
        description="Export active robot constraints from an RDF graph to controller JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Select, validate, and write active constraints")
    build.add_argument("--graph", type=Path, default=root / "data" / "constraints.ttl")
    build.add_argument("--shapes", type=Path, default=root / "data" / "shapes.ttl")
    build.add_argument("--qudt", type=Path, default=root / "data" / "qudt_units_fixture.ttl")
    build.add_argument("--config", type=Path, default=root / "config" / "defaults.yaml")
    build.add_argument(
        "--zone",
        default=None,
        help="Zone local name (for example zoneB) or IRI. Omit to drop zone-specific constraints.",
    )
    build.add_argument(
        "--human-present",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether a person is present. Unconditional constraints are always included.",
    )
    build.add_argument(
        "--skip-llm",
        action="store_true",
        help="Do not call the LLM verifier. Deterministic passes can still be status active.",
    )
    build.add_argument(
        "--output",
        type=Path,
        default=Path("active_constraints.json"),
        help="Destination JSON path (default: active_constraints.json).",
    )
    build.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any selected constraint needs review or SHACL does not conform.",
    )
    return parser


def format_summary(document: dict) -> str:
    context = document["context"]
    lines = [
        f"context: zone={context['zone'] or '-'} human_present={str(context['human_present']).lower()}",
        f"shacl_conforms: {str(document['shacl']['conforms']).lower()}",
        f"llm: {document['llm']['mode']} ({document['llm']['reason']})",
    ]
    for item in document["constraints"]:
        lines.append(f"{item['id']}: {item['status']} ({len(item['issues'])} issues)")
    return "\n".join(lines)


def _default_root() -> Path:
    start = Path(__file__).resolve()
    for candidate in [start.parent, *start.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "data" / "constraints.ttl").is_file():
            return candidate
    return Path.cwd()


if __name__ == "__main__":
    raise SystemExit(main())
