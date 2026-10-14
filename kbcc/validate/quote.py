"""Check that a source quote states the same limit as the stored value.

Numbers and units are taken from the quote (including a leading ±, which is a
symmetric magnitude). pint converts the quote unit into the constraint's unit,
and the magnitudes must agree within the configured tolerance. This is what
lets ``250 mm/s`` support a stored value of ``0.25 M-PER-SEC``.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pint

from kbcc.decimals import decimal_to_str, nearly_equal

_REGISTRY = pint.UnitRegistry()

_CANDIDATE = re.compile(
    r"(?P<raw>(?P<sign>±|\+|-)?"
    r"\s*(?P<number>\d+(?:\.\d+)?)"
    r"\s*(?P<unit>°|º|degree|deg|radian|rad|mm|cm|m)"
    r"(?:\s*/\s*(?P<per>second|sec|s))?)",
    re.IGNORECASE,
)


def check_quote(
    quote: str,
    value: Decimal,
    unit_name: str,
    pint_unit: str,
    quote_units: dict[str, str],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
) -> list[str]:
    """Return quote-support issues. An empty list means the quote agrees."""
    matches = list(_CANDIDATE.finditer(quote))
    if not matches:
        return ["quote: no numeric quantity with a unit was found in the quote"]

    parsed: list[str] = []
    incompatible: list[str] = []
    unparsed: list[str] = []
    for match in matches:
        described = " ".join(match.group("raw").split())
        try:
            quantity = _to_quantity(match, quote_units)
            converted = quantity.to(pint_unit)
        except pint.DimensionalityError:
            incompatible.append(described)
            continue
        except pint.PintError as exc:
            unparsed.append(f"{described} ({exc})")
            continue
        magnitude = converted.magnitude
        numeric = magnitude if isinstance(magnitude, Decimal) else Decimal(str(magnitude))
        if nearly_equal(numeric, value, abs_tolerance, rel_tolerance):
            return []
        parsed.append(f"{described} = {decimal_to_str(numeric)} {unit_name}")

    expected = f"{decimal_to_str(value)} {unit_name}"
    if parsed:
        found = "; ".join(parsed)
        return [f"quote: no quantity in the quote matches {expected} within tolerance; parsed {found}"]
    if incompatible:
        found = ", ".join(incompatible)
        return [f"quote: quantities [{found}] are not dimensionally compatible with {unit_name}"]
    found = "; ".join(unparsed) if unparsed else "nothing parseable"
    return [f"quote: could not parse a unit quantity from the quote ({found})"]


def _to_quantity(match: re.Match[str], quote_units: dict[str, str]) -> pint.Quantity:
    number = Decimal(match.group("number"))
    if match.group("sign") == "-":
        number = -number
    key = _unit_key(match.group("unit"), match.group("per"))
    expression = quote_units.get(key)
    if expression is not None:
        return _REGISTRY.Quantity(number, expression)
    text = match.group("raw").strip()
    text = re.sub(r"^[±+]\s*", "", text)
    if match.group("sign") == "-":
        text = "-" + text
    return _REGISTRY.Quantity(text)


def _unit_key(unit: str, per: str | None) -> str:
    token = unit.lower().replace("º", "°")
    if token in {"degree", "deg"}:
        token = "deg"
    elif token in {"radian", "rad"}:
        token = "rad"
    if per:
        return f"{token}/s"
    return token
