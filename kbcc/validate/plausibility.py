"""Reject SI values that fall outside the configured plausibility window."""

from __future__ import annotations

from decimal import Decimal

from kbcc.decimals import decimal_to_str


def check_plausibility(
    variable: str,
    si_value: Decimal,
    si_unit_name: str,
    minimum: Decimal | None,
    maximum: Decimal | None,
) -> list[str]:
    """Return issues when ``si_value`` is outside ``[minimum, maximum]``."""
    issues: list[str] = []
    if minimum is not None and si_value < minimum:
        issues.append(
            f"plausibility: {variable} value {decimal_to_str(si_value)} {si_unit_name} "
            f"is below the configured minimum {decimal_to_str(minimum)}"
        )
    if maximum is not None and si_value > maximum:
        issues.append(
            f"plausibility: {variable} value {decimal_to_str(si_value)} {si_unit_name} "
            f"is above the configured maximum {decimal_to_str(maximum)}"
        )
    return issues
