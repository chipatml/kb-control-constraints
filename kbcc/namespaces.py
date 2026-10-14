"""RDF namespaces used by the constraint graph."""

from rdflib import Namespace

EX = Namespace("http://example.org/robot#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
QK = Namespace("http://qudt.org/vocab/quantitykind/")


def local_name(uri: str) -> str:
    """Return the fragment or final path segment of an IRI."""
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]
