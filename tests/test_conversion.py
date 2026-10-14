"""QUDT conversion: multipliers, offsets, missing units, and quantity kinds."""

from decimal import Decimal

import pytest
from rdflib import Graph, Literal, Namespace

from kbcc.config import load_config
from kbcc.errors import IncompatibleQuantityKindError, MissingUnitError, UnknownVariableError
from kbcc.namespaces import QUDT, UNIT
from kbcc.units import convert, convert_for_variable, index_units

QK = Namespace("http://qudt.org/vocab/quantitykind/")


@pytest.fixture
def units(paths):
    graph = Graph()
    graph.parse(paths["qudt"])
    return index_units(graph)


@pytest.fixture
def config(paths):
    return load_config(paths["config"])


def test_fixture_keeps_published_degree_multiplier(units):
    record = units[str(UNIT["DEG-PER-SEC"])]
    assert record.multiplier == Decimal("0.0174532925")
    assert record.offset == Decimal("0")


def test_joint_velocity_degrees_to_radians(units, config):
    si, target = convert_for_variable(
        "joint_velocity",
        Decimal("180"),
        str(UNIT["DEG-PER-SEC"]),
        config,
        units,
    )
    assert target == str(UNIT["RAD-PER-SEC"])
    assert si == Decimal("3.14159265")


def test_tcp_speed_already_si(units, config):
    si, target = convert_for_variable("tcp_speed", Decimal("0.25"), str(UNIT["M-PER-SEC"]), config, units)
    assert target == str(UNIT["M-PER-SEC"])
    assert si == Decimal("0.25")


def test_metres_per_second_to_millimetres(units):
    converted = convert(Decimal("0.25"), str(UNIT["M-PER-SEC"]), str(UNIT["MilliM-PER-SEC"]), units)
    assert converted == Decimal("250")


def test_celsius_offset_to_kelvin(units):
    assert convert(Decimal("0"), str(UNIT["DEG_C"]), str(UNIT.K), units) == Decimal("273.15")
    assert convert(Decimal("100"), str(UNIT["DEG_C"]), str(UNIT.K), units) == Decimal("373.15")
    assert convert(Decimal("0"), str(UNIT["DEG_C"]), str(UNIT["DEG_C"]), units) == Decimal("0")


def test_missing_unit(units):
    with pytest.raises(MissingUnitError, match="FT-PER-SEC"):
        convert(Decimal("1"), str(UNIT["FT-PER-SEC"]), str(UNIT["M-PER-SEC"]), units)


def test_unknown_variable(units, config):
    with pytest.raises(UnknownVariableError, match="elbow_angle"):
        convert_for_variable("elbow_angle", Decimal("1"), str(UNIT["DEG-PER-SEC"]), config, units)


def test_incompatible_quantity_kinds(units):
    with pytest.raises(IncompatibleQuantityKindError, match="Incompatible quantity kinds"):
        convert(Decimal("180"), str(UNIT["DEG-PER-SEC"]), str(UNIT["M-PER-SEC"]), units)


def test_missing_quantity_kind_is_rejected():
    graph = Graph()
    bare = UNIT["BARE"]
    graph.add((bare, QUDT.conversionMultiplier, Literal(Decimal("1.0"))))
    graph.add((UNIT["M-PER-SEC"], QUDT.conversionMultiplier, Literal(Decimal("1.0"))))
    graph.add((UNIT["M-PER-SEC"], QUDT.hasQuantityKind, QK.Velocity))
    units = index_units(graph)
    with pytest.raises(IncompatibleQuantityKindError, match="no qudt:hasQuantityKind"):
        convert(Decimal("1"), str(bare), str(UNIT["M-PER-SEC"]), units)
