"""Convert constraint values with QUDT conversionMultiplier and conversionOffset.

QUDT publishes an affine map into SI::

    si = value * conversionMultiplier + conversionOffset

A missing offset is treated as 0. Two units are compatible when their
``qudt:hasQuantityKind`` sets intersect. The inverse map produces the value
in the target unit::

    target = (si - targetOffset) / targetMultiplier
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rdflib import Graph, Literal

from kbcc.config import AppConfig
from kbcc.errors import IncompatibleQuantityKindError, MissingUnitError, UnitConversionError, UnknownVariableError
from kbcc.namespaces import QUDT, UNIT, local_name


@dataclass(frozen=True)
class UnitRecord:
    uri: str
    multiplier: Decimal
    offset: Decimal
    quantity_kinds: frozenset[str]
    symbol: str | None


def index_units(graph: Graph) -> dict[str, UnitRecord]:
    """Index every unit that publishes ``qudt:conversionMultiplier``."""
    records: dict[str, UnitRecord] = {}
    for unit in set(graph.subjects(QUDT.conversionMultiplier, None)):
        uri = str(unit)
        multipliers = list(graph.objects(unit, QUDT.conversionMultiplier))
        if len(multipliers) != 1:
            raise UnitConversionError(
                f"QUDT unit {uri} has {len(multipliers)} qudt:conversionMultiplier values; expected one."
            )
        offsets = list(graph.objects(unit, QUDT.conversionOffset))
        if len(offsets) > 1:
            raise UnitConversionError(
                f"QUDT unit {uri} has {len(offsets)} qudt:conversionOffset values; expected at most one."
            )
        symbols = [str(symbol) for symbol in graph.objects(unit, QUDT.symbol)]
        records[uri] = UnitRecord(
            uri=uri,
            multiplier=_as_decimal(multipliers[0]),
            offset=_as_decimal(offsets[0]) if offsets else Decimal("0"),
            quantity_kinds=frozenset(str(kind) for kind in graph.objects(unit, QUDT.hasQuantityKind)),
            symbol=symbols[0] if symbols else None,
        )
    return records


def convert(value: Decimal, from_unit: str, to_unit: str, units: dict[str, UnitRecord]) -> Decimal:
    """Convert ``value`` from one QUDT unit to another of a shared quantity kind."""
    source = _require(units, from_unit)
    target = _require(units, to_unit)
    if not source.quantity_kinds:
        raise IncompatibleQuantityKindError(
            f"Unit {local_name(from_unit)} has no qudt:hasQuantityKind, so compatibility cannot be checked."
        )
    if not target.quantity_kinds:
        raise IncompatibleQuantityKindError(
            f"Unit {local_name(to_unit)} has no qudt:hasQuantityKind, so compatibility cannot be checked."
        )
    if source.quantity_kinds.isdisjoint(target.quantity_kinds):
        raise IncompatibleQuantityKindError(
            "Incompatible quantity kinds for "
            f"{local_name(from_unit)} -> {local_name(to_unit)}: "
            f"{_kind_names(source.quantity_kinds)} vs {_kind_names(target.quantity_kinds)}."
        )
    if target.multiplier == 0:
        raise UnitConversionError(f"Unit {local_name(to_unit)} has qudt:conversionMultiplier 0.")
    si = value * source.multiplier + source.offset
    return (si - target.offset) / target.multiplier


def convert_for_variable(
    variable: str,
    value: Decimal,
    from_unit: str,
    config: AppConfig,
    units: dict[str, UnitRecord],
) -> tuple[Decimal, str]:
    """Convert ``value`` into the SI unit configured for ``variable``.

    Returns the SI value and the target unit IRI.
    """
    spec = config.variables.get(variable)
    if spec is None:
        raise UnknownVariableError(variable, sorted(config.variables))
    target = spec.si_unit if spec.si_unit.startswith(("http://", "https://")) else str(UNIT[spec.si_unit])
    return convert(value, from_unit, target, units), target


def _require(units: dict[str, UnitRecord], uri: str) -> UnitRecord:
    record = units.get(uri)
    if record is None:
        raise MissingUnitError(f"QUDT unit '{uri}' has no qudt:conversionMultiplier in the units graph.")
    return record


def _as_decimal(node: object) -> Decimal:
    if isinstance(node, Literal):
        return Decimal(str(node))
    return Decimal(str(node))


def _kind_names(kinds: frozenset[str]) -> str:
    names = ", ".join(sorted(local_name(kind) for kind in kinds))
    return "{" + names + "}"
