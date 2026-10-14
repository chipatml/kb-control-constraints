"""SHACL shapes: completeness, datatypes, operator/hardness lists, non-negative speeds."""

from rdflib import Graph

from kbcc.validate.shacl_check import validate_constraints

PREFIXES = """
@prefix ex: <http://example.org/robot#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .
"""


def _shapes(paths) -> Graph:
    graph = Graph()
    graph.parse(paths["shapes"])
    return graph


def _report(paths, body: str):
    data = Graph()
    data.parse(data=PREFIXES + body, format="turtle")
    return validate_constraints(data, _shapes(paths))


def _valid(**overrides: str) -> str:
    fields = {
        "subject": "ex:j1",
        "variable": '"joint_velocity"',
        "operator": '"<="',
        "value": '"180"^^xsd:decimal',
        "unit": "unit:DEG-PER-SEC",
        "hardness": '"hard"',
        "sourceDoc": '"UR5e_spec.pdf"',
        "page": "4",
        "quote": '"Max joint speed: ±180°/s"',
    }
    fields.update(overrides)
    triples = " ;\n    ".join(f"ex:{name} {value}" for name, value in fields.items())
    return f"""
ex:j1 a ex:Joint .
ex:c1 a ex:Constraint ;
    {triples} .
"""


def test_sample_graph_conforms(paths):
    data = Graph()
    data.parse(paths["graph"])
    report = validate_constraints(data, _shapes(paths))
    assert report.conforms, report.text
    assert report.findings == []


def test_complete_constraint_conforms(paths):
    report = _report(paths, _valid())
    assert report.conforms, report.text


def test_negative_speed_fails(paths):
    report = _report(paths, _valid(value='"-1"^^xsd:decimal'))
    assert not report.conforms
    assert any(">= 0" in finding.message for finding in report.findings)
    assert report.findings[0].focus.endswith("#c1")


def test_operator_and_hardness_lists(paths):
    report = _report(paths, _valid(operator='"approx"', hardness='"maybe"'))
    text = " ".join(finding.message for finding in report.findings)
    assert "ex:operator must be one of" in text
    assert "ex:hardness must be hard or soft" in text


def test_integer_value_is_not_decimal(paths):
    report = _report(paths, _valid(value="180"))
    assert any("xsd:decimal" in finding.message for finding in report.findings)


def test_missing_quote_fails_completeness(paths):
    report = _report(
        paths,
        """
ex:j1 a ex:Joint .
ex:c1 a ex:Constraint ;
    ex:subject ex:j1 ;
    ex:variable "joint_velocity" ;
    ex:operator "<=" ;
    ex:value "180"^^xsd:decimal ;
    ex:unit unit:DEG-PER-SEC ;
    ex:hardness "hard" ;
    ex:sourceDoc "UR5e_spec.pdf" ;
    ex:page 4 .
""",
    )
    assert not report.conforms
    assert "quote" in report.text


def test_condition_datatype(paths):
    report = _report(
        paths,
        """
ex:j1 a ex:Joint .
ex:c1 a ex:Constraint ;
    ex:subject ex:j1 ;
    ex:variable "tcp_speed" ;
    ex:operator "<=" ;
    ex:value "0.25"^^xsd:decimal ;
    ex:unit unit:M-PER-SEC ;
    ex:hardness "hard" ;
    ex:sourceDoc "Safety_manual.pdf" ;
    ex:page 12 ;
    ex:quote "Reduce TCP speed to 250 mm/s when operators are present." ;
    ex:condition [ ex:humanPresent "yes" ; ex:inZone "zoneB" ] .
""",
    )
    text = " ".join(finding.message for finding in report.findings)
    assert "xsd:boolean" in text
    assert "IRI" in text


def test_page_must_be_positive(paths):
    report = _report(paths, _valid(page="0"))
    assert any(">= 1" in finding.message for finding in report.findings)
