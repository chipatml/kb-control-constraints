"""Run the SHACL shapes against the constraint graph."""

from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

SH = Namespace("http://www.w3.org/ns/shacl#")


@dataclass(frozen=True)
class ShaclFinding:
    focus: str | None
    message: str


@dataclass(frozen=True)
class ShaclReport:
    conforms: bool
    findings: list[ShaclFinding]
    text: str


def validate_constraints(data_graph: Graph, shapes_graph: Graph) -> ShaclReport:
    """Validate ``data_graph`` and return one finding per result message."""
    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
        allow_warnings=True,
    )
    findings: list[ShaclFinding] = []
    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        focus_node = results_graph.value(result, SH.focusNode)
        focus = str(focus_node) if isinstance(focus_node, URIRef) else None
        messages = [str(message).strip() for message in results_graph.objects(result, SH.resultMessage)]
        if not messages:
            messages = ["SHACL validation failed"]
        for message in messages:
            findings.append(ShaclFinding(focus=focus, message=f"shacl: {message}"))
    findings.sort(key=lambda finding: (finding.focus or "", finding.message))
    return ShaclReport(conforms=bool(conforms), findings=findings, text=str(results_text))
