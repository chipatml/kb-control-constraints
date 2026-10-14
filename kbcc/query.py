"""SPARQL selection of constraints that apply in a runtime context.

Unconditional constraints (no ``ex:condition``) are always returned. A condition
matches when every bound field agrees with the context: ``ex:inZone`` with the
zone, and ``ex:humanPresent`` with the human-present flag. A condition that
sets only one of those fields does not constrain the other.
"""

from __future__ import annotations

from decimal import Decimal

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from kbcc.errors import DataError, UnknownZoneError
from kbcc.models import ConstraintRecord
from kbcc.namespaces import EX, local_name

ACTIVE_CONSTRAINTS_QUERY = """
PREFIX ex: <http://example.org/robot#>

SELECT ?constraint ?subject ?variable ?operator ?value ?unit ?hardness
       ?sourceDoc ?page ?quote ?zone ?humanPresent
WHERE {
  ?constraint a ex:Constraint ;
              ex:subject ?subject ;
              ex:variable ?variable ;
              ex:operator ?operator ;
              ex:value ?value ;
              ex:unit ?unit ;
              ex:hardness ?hardness ;
              ex:sourceDoc ?sourceDoc ;
              ex:page ?page ;
              ex:quote ?quote .
  OPTIONAL {
    ?constraint ex:condition ?cond .
    OPTIONAL { ?cond ex:inZone ?zone }
    OPTIONAL { ?cond ex:humanPresent ?humanPresent }
  }
  FILTER(
    (!BOUND(?zone) && !BOUND(?humanPresent))
    || (
      (!BOUND(?zone) || ?zone = ?ctxZone) &&
      (!BOUND(?humanPresent) || ?humanPresent = ?ctxHuman)
    )
  )
}
ORDER BY STR(?constraint)
"""


def resolve_zone(graph: Graph, zone: str) -> URIRef:
    """Resolve a zone local name or IRI to a ``ex:Zone`` in ``graph``."""
    uri = URIRef(zone) if zone.startswith(("http://", "https://")) else EX[zone]
    if (uri, RDF.type, EX.Zone) not in graph:
        known = sorted(local_name(str(item)) for item in graph.subjects(RDF.type, EX.Zone))
        known_text = ", ".join(known) if known else "(none)"
        raise UnknownZoneError(f"Unknown zone '{zone}'. Known zones: {known_text}.")
    return uri


def select_active_constraints(
    graph: Graph,
    zone: URIRef | None,
    human_present: bool,
) -> list[ConstraintRecord]:
    """Return constraints whose conditions hold in this context."""
    bindings: dict[str, URIRef | Literal] = {"ctxHuman": Literal(bool(human_present), datatype=XSD.boolean)}
    if zone is not None:
        bindings["ctxZone"] = zone
    rows = list(graph.query(ACTIVE_CONSTRAINTS_QUERY, initBindings=bindings))
    records: list[ConstraintRecord] = []
    seen: set[str] = set()
    for row in rows:
        uri = str(row.constraint)
        if uri in seen:
            raise DataError(f"Constraint {uri} was returned more than once; check for duplicate properties.")
        seen.add(uri)
        zone_uri = str(row.zone) if row.zone is not None else None
        human = None if row.humanPresent is None else bool(row.humanPresent.toPython())
        records.append(
            ConstraintRecord(
                id=local_name(uri),
                uri=uri,
                subject_uri=str(row.subject),
                subject_name=local_name(str(row.subject)),
                variable=str(row.variable),
                operator=str(row.operator),
                value=Decimal(str(row.value)),
                value_lexical=str(row.value),
                unit_uri=str(row.unit),
                unit_name=local_name(str(row.unit)),
                hardness=str(row.hardness),
                source_doc=str(row.sourceDoc),
                page=int(row.page.toPython()),
                quote=str(row.quote),
                zone_uri=zone_uri,
                zone_name=local_name(zone_uri) if zone_uri else None,
                human_present=human,
            )
        )
    return records
