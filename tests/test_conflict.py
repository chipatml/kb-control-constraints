"""Interval conflicts: contradictory bounds and disagreeing duplicates."""

import importlib.util
from decimal import Decimal

import pytest

from kbcc.errors import ConflictEngineError
from kbcc.validate.conflict import Bound, find_conflicts

ABS = Decimal("0.000001")
REL = Decimal("0.000001")
Z3_MISSING = importlib.util.find_spec("z3") is None


def _bound(constraint_id: str, operator: str, value: str, subject: str = "http://example.org/robot#j1") -> Bound:
    return Bound(
        constraint_id=constraint_id,
        subject_uri=subject,
        subject_name=subject.rsplit("#", 1)[-1],
        variable="joint_velocity",
        operator=operator,
        si_value=Decimal(value),
        si_unit_name="RAD-PER-SEC",
    )


def _messages(bounds: list[Bound], engine: str = "interval") -> dict[str, list[str]]:
    return find_conflicts(bounds, ABS, REL, engine=engine)


def test_lower_above_upper_is_contradictory():
    found = _messages([_bound("cA", ">=", "2"), _bound("cB", "<=", "1")])
    assert "contradictory" in found["cA"][0]
    assert "contradictory" in found["cB"][0]


def test_disagreeing_upper_bounds_are_duplicates_but_still_feasible():
    found = _messages([_bound("cA", "<=", "2"), _bound("cB", "<=", "1")])
    assert len(found["cA"]) == 1
    assert "disagreeing duplicate" in found["cA"][0]
    assert "contradictory" not in found["cA"][0]


def test_open_lower_equal_to_closed_upper_is_empty():
    found = _messages([_bound("cA", ">", "1"), _bound("cB", "<=", "1")])
    assert "contradictory" in found["cA"][0]


def test_closed_point_is_feasible():
    assert _messages([_bound("cA", ">=", "1"), _bound("cB", "<=", "1")]) == {}


def test_open_interval_is_feasible():
    assert _messages([_bound("cA", ">", "0"), _bound("cB", "<", "1")]) == {}


def test_equal_values_that_differ_conflict():
    found = _messages([_bound("cA", "==", "1"), _bound("cB", "==", "2")])
    text = " ".join(found["cA"])
    assert "disagreeing duplicate" in text
    assert "contradictory" in text


def test_equality_outside_an_upper_bound_conflicts():
    found = _messages([_bound("cA", "==", "1"), _bound("cB", "<=", "0")])
    assert "contradictory" in found["cA"][0]


def test_different_subjects_do_not_conflict():
    other = "http://example.org/robot#j2"
    found = _messages([_bound("cA", ">=", "5"), _bound("cB", "<=", "1", subject=other)])
    assert found == {}


def test_same_operator_and_equivalent_si_values_agree():
    found = _messages([_bound("cA", "<=", "3.14159265"), _bound("cB", "<=", "3.141592653589793")])
    assert found == {}


def test_unsupported_operator():
    found = _messages([_bound("cA", "approx", "1")])
    assert "unsupported operator" in found["cA"][0]


def test_unknown_engine():
    with pytest.raises(ConflictEngineError, match="interval"):
        _messages([_bound("cA", "<=", "1")], engine="smt")


@pytest.mark.skipif(not Z3_MISSING, reason="z3 is installed")
def test_z3_engine_without_solver_is_explicit():
    with pytest.raises(ConflictEngineError, match="z3-solver"):
        _messages([_bound("cA", ">=", "2"), _bound("cB", "<=", "1")], engine="z3")


@pytest.mark.skipif(Z3_MISSING, reason="z3-solver not installed")
def test_z3_detects_empty_bounds():
    found = _messages([_bound("cA", ">=", "2"), _bound("cB", "<=", "1")], engine="z3")
    assert "contradictory" in found["cA"][0]


@pytest.mark.skipif(Z3_MISSING, reason="z3-solver not installed")
def test_z3_accepts_a_closed_point():
    assert _messages([_bound("cA", ">=", "1"), _bound("cB", "<=", "1")], engine="z3") == {}
