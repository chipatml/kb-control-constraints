"""Plausibility windows are inclusive and reported in SI."""

from decimal import Decimal

from kbcc.validate.plausibility import check_plausibility


def test_value_inside_the_window():
    assert check_plausibility("joint_velocity", Decimal("3.14"), "RAD-PER-SEC", Decimal("0"), Decimal("10")) == []


def test_bounds_are_inclusive():
    assert check_plausibility("tcp_speed", Decimal("0"), "M-PER-SEC", Decimal("0"), Decimal("5")) == []
    assert check_plausibility("tcp_speed", Decimal("5"), "M-PER-SEC", Decimal("0"), Decimal("5")) == []


def test_below_minimum():
    issues = check_plausibility("joint_velocity", Decimal("-0.1"), "RAD-PER-SEC", Decimal("0"), Decimal("10"))
    assert "below" in issues[0]
    assert "joint_velocity" in issues[0]


def test_above_maximum():
    issues = check_plausibility("tcp_speed", Decimal("5.1"), "M-PER-SEC", Decimal("0"), Decimal("5"))
    assert "above" in issues[0]
    assert "5" in issues[0]


def test_missing_window_is_not_an_issue():
    assert check_plausibility("tcp_speed", Decimal("100"), "M-PER-SEC", None, None) == []
