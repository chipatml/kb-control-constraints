"""Exact decimal formatting shared by cards, JSON, and comparisons."""

from decimal import ROUND_HALF_UP, Decimal


def decimal_to_str(value: Decimal) -> str:
    """Render a decimal without scientific notation or trailing zeros."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_original(value: Decimal) -> str:
    """Render a source value with at least one fractional digit (180 -> 180.0)."""
    text = decimal_to_str(value)
    if "." not in text:
        return text + ".0"
    return text


def format_si(value: Decimal, places: int) -> str:
    """Round half up to a fixed number of decimal places for the consistency card."""
    quantum = Decimal(1).scaleb(-places)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return format(rounded, "f")


def nearly_equal(left: Decimal, right: Decimal, absolute: Decimal, relative: Decimal) -> bool:
    """Compare two decimals within an absolute plus relative tolerance."""
    return abs(left - right) <= absolute + relative * max(abs(left), abs(right))
