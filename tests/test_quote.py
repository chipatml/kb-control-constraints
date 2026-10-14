"""Quote parsing: ±, mm/s versus m/s, and mismatches."""

from decimal import Decimal

import pytest

from kbcc.config import load_config
from kbcc.validate.quote import check_quote


@pytest.fixture
def config(paths):
    return load_config(paths["config"])


def _check(config, quote: str, value: str, unit_name: str) -> list[str]:
    return check_quote(
        quote=quote,
        value=Decimal(value),
        unit_name=unit_name,
        pint_unit=config.pint_units[unit_name],
        quote_units=config.quote_units,
        abs_tolerance=config.quote_abs_tolerance,
        rel_tolerance=config.quote_rel_tolerance,
    )


def test_plus_minus_degree_quote_supports_joint_limit(config):
    assert _check(config, "Max joint speed: ±180°/s", "180", "DEG-PER-SEC") == []


def test_millimetres_per_second_support_metres(config):
    quote = "Reduce TCP speed to 250 mm/s when operators are present."
    assert _check(config, quote, "0.25", "M-PER-SEC") == []


def test_degree_word_form(config):
    assert _check(config, "limit is 180 deg/s.", "180", "DEG-PER-SEC") == []


def test_mismatch_is_reported(config):
    issues = _check(config, "Reduce TCP speed to 300 mm/s.", "0.25", "M-PER-SEC")
    assert len(issues) == 1
    assert "0.25 M-PER-SEC" in issues[0]
    assert "300 mm/s" in issues[0]


def test_same_number_in_the_wrong_unit_does_not_match(config):
    issues = _check(config, "Max joint speed: ±180°/s", "180", "RAD-PER-SEC")
    assert issues
    assert "180 RAD-PER-SEC" in issues[0]


def test_quote_without_a_quantity(config):
    issues = _check(config, "operators must stay clear of the arm", "0.25", "M-PER-SEC")
    assert issues[0].startswith("quote: no numeric quantity")
