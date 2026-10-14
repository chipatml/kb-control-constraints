"""Detect contradictory bounds and disagreeing duplicates.

Constraints are grouped by ``(subject, variable)`` after conversion to SI.
Two constraints with the same operator and different SI values are disagreeing
duplicates even when their intersection is non-empty (``<= 2`` and ``<= 1``).
A separate interval check (or optional z3 check) reports a group whose bounds
have an empty intersection.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from kbcc.decimals import decimal_to_str, nearly_equal
from kbcc.errors import ConflictEngineError

_OPERATORS = {"<=", ">=", "==", "<", ">"}


@dataclass(frozen=True)
class Bound:
    constraint_id: str
    subject_uri: str
    subject_name: str
    variable: str
    operator: str
    si_value: Decimal
    si_unit_name: str


@dataclass(frozen=True)
class _Side:
    value: Decimal
    closed: bool
    constraint_id: str
    operator: str


def find_conflicts(
    bounds: list[Bound],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
    engine: str = "interval",
) -> dict[str, list[str]]:
    """Map constraint id to conflict messages. Ids with no conflict are absent."""
    if engine not in {"interval", "z3"}:
        raise ConflictEngineError(f"Unknown conflict.engine '{engine}'. Use 'interval' or 'z3'.")
    grouped: dict[tuple[str, str], list[Bound]] = defaultdict(list)
    for bound in bounds:
        grouped[(bound.subject_uri, bound.variable)].append(bound)

    issues: dict[str, list[str]] = defaultdict(list)
    for group in grouped.values():
        for affected, message in _group_issues(group, abs_tolerance, rel_tolerance, engine):
            for constraint_id in sorted(affected):
                issues[constraint_id].append(message)
    return dict(issues)


def _group_issues(
    group: list[Bound],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
    engine: str,
) -> list[tuple[set[str], str]]:
    issues: list[tuple[set[str], str]] = []
    comparable: list[Bound] = []
    for bound in group:
        if bound.operator not in _OPERATORS:
            issues.append(
                (
                    {bound.constraint_id},
                    f"conflict: unsupported operator {bound.operator!r} on {bound.constraint_id}",
                )
            )
        else:
            comparable.append(bound)
    issues.extend(_duplicate_issues(comparable, abs_tolerance, rel_tolerance))
    if len(comparable) >= 2 and _unsatisfiable(comparable, abs_tolerance, rel_tolerance, engine):
        issues.append((_ids(comparable), _contradiction_message(comparable)))
    return issues


def _duplicate_issues(
    group: list[Bound],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
) -> list[tuple[set[str], str]]:
    by_operator: dict[str, list[Bound]] = defaultdict(list)
    for bound in group:
        by_operator[bound.operator].append(bound)
    issues: list[tuple[set[str], str]] = []
    for operator, items in sorted(by_operator.items()):
        if len(items) < 2:
            continue
        reference = items[0].si_value
        if all(nearly_equal(item.si_value, reference, abs_tolerance, rel_tolerance) for item in items[1:]):
            continue
        listed = ", ".join(
            f"{item.constraint_id}={decimal_to_str(item.si_value)}"
            for item in sorted(items, key=lambda item: item.constraint_id)
        )
        sample = items[0]
        message = (
            f"conflict: disagreeing duplicate operator '{operator}' on "
            f"{sample.subject_name}.{sample.variable} ({listed} SI {sample.si_unit_name})"
        )
        issues.append((_ids(items), message))
    return issues


def _unsatisfiable(
    group: list[Bound],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
    engine: str,
) -> bool:
    if engine == "z3":
        return _z3_unsatisfiable(group)
    lower, upper = _tight_bounds(group, abs_tolerance, rel_tolerance)
    if lower is None or upper is None:
        return False
    return _empty(lower, upper, abs_tolerance, rel_tolerance)


def _tight_bounds(
    group: list[Bound],
    abs_tolerance: Decimal,
    rel_tolerance: Decimal,
) -> tuple[_Side | None, _Side | None]:
    lower: _Side | None = None
    upper: _Side | None = None
    for bound in group:
        side = _Side(bound.si_value, bound.operator in {"<=", ">=", "=="}, bound.constraint_id, bound.operator)
        if bound.operator in {">=", ">", "=="}:
            lower = side if lower is None or _tighter_lower(side, lower, abs_tolerance, rel_tolerance) else lower
        if bound.operator in {"<=", "<", "=="}:
            upper = side if upper is None or _tighter_upper(side, upper, abs_tolerance, rel_tolerance) else upper
    return lower, upper


def _cmp(left: Decimal, right: Decimal, abs_tolerance: Decimal, rel_tolerance: Decimal) -> int:
    if nearly_equal(left, right, abs_tolerance, rel_tolerance):
        return 0
    return -1 if left < right else 1


def _tighter_lower(candidate: _Side, current: _Side, abs_tolerance: Decimal, rel_tolerance: Decimal) -> bool:
    compared = _cmp(candidate.value, current.value, abs_tolerance, rel_tolerance)
    if compared > 0:
        return True
    if compared < 0:
        return False
    return (not candidate.closed) and current.closed


def _tighter_upper(candidate: _Side, current: _Side, abs_tolerance: Decimal, rel_tolerance: Decimal) -> bool:
    compared = _cmp(candidate.value, current.value, abs_tolerance, rel_tolerance)
    if compared < 0:
        return True
    if compared > 0:
        return False
    return (not candidate.closed) and current.closed


def _empty(lower: _Side, upper: _Side, abs_tolerance: Decimal, rel_tolerance: Decimal) -> bool:
    compared = _cmp(lower.value, upper.value, abs_tolerance, rel_tolerance)
    if compared > 0:
        return True
    if compared < 0:
        return False
    return not (lower.closed and upper.closed)


def _z3_unsatisfiable(group: list[Bound]) -> bool:
    try:
        import z3
    except ImportError as exc:
        raise ConflictEngineError(
            "conflict.engine is 'z3' but z3-solver is not installed. "
            "Install the kbcc[z3] extra or set conflict.engine to 'interval'."
        ) from exc
    solver = z3.Solver()
    unknown = z3.Real("x")
    for bound in group:
        value = z3.RealVal(str(bound.si_value))
        if bound.operator == "<=":
            solver.add(unknown <= value)
        elif bound.operator == "<":
            solver.add(unknown < value)
        elif bound.operator == ">=":
            solver.add(unknown >= value)
        elif bound.operator == ">":
            solver.add(unknown > value)
        elif bound.operator == "==":
            solver.add(unknown == value)
    result = solver.check()
    if result == z3.unknown:
        raise ConflictEngineError("z3 could not decide whether the bounds are satisfiable.")
    return result == z3.unsat


def _contradiction_message(group: list[Bound]) -> str:
    shown = ", ".join(
        f"{bound.constraint_id} {bound.operator} {decimal_to_str(bound.si_value)}"
        for bound in sorted(group, key=lambda bound: bound.constraint_id)
    )
    sample = group[0]
    return (
        f"conflict: contradictory bounds on {sample.subject_name}.{sample.variable}; "
        f"no value satisfies {shown} (SI {sample.si_unit_name})"
    )


def _ids(group: list[Bound]) -> set[str]:
    return {bound.constraint_id for bound in group}
