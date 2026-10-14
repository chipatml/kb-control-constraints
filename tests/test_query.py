"""Context query: unconditional constraints stay, conditional ones match the context."""

from rdflib import Graph

from kbcc.errors import UnknownZoneError
from kbcc.namespaces import EX
from kbcc.query import ACTIVE_CONSTRAINTS_QUERY, resolve_zone, select_active_constraints

EXTRA = """
@prefix ex: <http://example.org/robot#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .

ex:cZone a ex:Constraint ;
  ex:subject ex:arm1 ;
  ex:variable "tcp_speed" ;
  ex:operator "<=" ;
  ex:value "1.0"^^xsd:decimal ;
  ex:unit unit:M-PER-SEC ;
  ex:hardness "soft" ;
  ex:sourceDoc "notes.pdf" ;
  ex:page 1 ;
  ex:quote "In zone B, TCP speed should stay at or below 1 m/s." ;
  ex:condition [ ex:inZone ex:zoneB ] .

ex:cHuman a ex:Constraint ;
  ex:subject ex:arm1 ;
  ex:variable "tcp_speed" ;
  ex:operator "<=" ;
  ex:value "0.5"^^xsd:decimal ;
  ex:unit unit:M-PER-SEC ;
  ex:hardness "hard" ;
  ex:sourceDoc "notes.pdf" ;
  ex:page 2 ;
  ex:quote "When a person is present, TCP speed shall stay at or below 0.5 m/s." ;
  ex:condition [ ex:humanPresent true ] .
"""


def _graph(paths) -> Graph:
    graph = Graph()
    graph.parse(paths["graph"])
    graph.parse(data=EXTRA, format="turtle")
    return graph


def _ids(paths, zone: str | None, human: bool) -> list[str]:
    graph = _graph(paths)
    zone_uri = resolve_zone(graph, zone) if zone else None
    return [record.id for record in select_active_constraints(graph, zone_uri, human)]


def test_query_keeps_unconditional_constraints_in_the_filter():
    assert "!BOUND(?zone)" in ACTIVE_CONSTRAINTS_QUERY
    assert "!BOUND(?humanPresent)" in ACTIVE_CONSTRAINTS_QUERY


def test_zone_and_human_include_both_sample_constraints(paths):
    assert _ids(paths, "zoneB", True) == ["c1", "c2", "cHuman", "cZone"]


def test_zone_without_human_drops_human_conditions(paths):
    assert _ids(paths, "zoneB", False) == ["c1", "cZone"]


def test_other_zone_with_human_drops_zone_b(paths):
    assert _ids(paths, "zoneA", True) == ["c1", "cHuman"]


def test_missing_zone_drops_zone_conditions(paths):
    assert _ids(paths, None, True) == ["c1", "cHuman"]


def test_full_zone_iri_resolves(paths):
    graph = _graph(paths)
    assert resolve_zone(graph, str(EX.zoneB)) == EX.zoneB


def test_unknown_zone(paths):
    graph = _graph(paths)
    try:
        resolve_zone(graph, "zoneZ")
    except UnknownZoneError as exc:
        assert "zoneZ" in str(exc)
        assert "zoneA" in str(exc)
    else:
        raise AssertionError("expected UnknownZoneError")


def test_sample_values_keep_source_lexical_form(paths):
    graph = Graph()
    graph.parse(paths["graph"])
    records = {record.id: record for record in select_active_constraints(graph, EX.zoneB, True)}
    assert records["c1"].value_lexical == "180"
    assert records["c1"].zone_uri is None
    assert records["c2"].value_lexical == "0.25"
    assert records["c2"].zone_name == "zoneB"
    assert records["c2"].human_present is True
    assert records["c2"].quote.endswith("present.")
