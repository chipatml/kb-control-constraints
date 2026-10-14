"""End-to-end pipeline and CLI."""

import hashlib
import json
import subprocess
import sys
from decimal import Decimal

from kbcc.namespaces import QUDT, UNIT
from kbcc.pipeline import build_active_constraints
from kbcc.verifier.mock import MockVerifier
from tests.conftest import ROOT
from tests.expected_cards import C1_CARD, C2_CARD

BAD_SPEED = """
@prefix ex: <http://example.org/robot#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .

ex:j2 a ex:Joint .
ex:cbad a ex:Constraint ;
  ex:subject ex:j2 ;
  ex:variable "joint_velocity" ;
  ex:operator "<=" ;
  ex:value "-1"^^xsd:decimal ;
  ex:unit unit:DEG-PER-SEC ;
  ex:hardness "hard" ;
  ex:sourceDoc "notes.pdf" ;
  ex:page 1 ;
  ex:quote "joint speed -1 deg/s" .
"""

BAD_KIND = """
@prefix ex: <http://example.org/robot#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .

ex:probe a ex:Robot .
ex:ctemp a ex:Constraint ;
  ex:subject ex:probe ;
  ex:variable "joint_velocity" ;
  ex:operator "<=" ;
  ex:value "10"^^xsd:decimal ;
  ex:unit unit:DEG_C ;
  ex:hardness "hard" ;
  ex:sourceDoc "notes.pdf" ;
  ex:page 1 ;
  ex:quote "temperature limit 10°C" .
"""


def _build(paths, **kwargs):
    defaults = {
        "graph_path": paths["graph"],
        "shapes_path": paths["shapes"],
        "qudt_path": paths["qudt"],
        "config_path": paths["config"],
        "zone": "zoneB",
        "human_present": True,
        "skip_llm": True,
    }
    defaults.update(kwargs)
    return build_active_constraints(**defaults)


def _with_extra(paths, tmp_path, extra: str):
    text = paths["graph"].read_text(encoding="utf-8") + "\n" + extra
    destination = tmp_path / "constraints.ttl"
    destination.write_text(text, encoding="utf-8")
    return destination


def test_sample_run_activates_both_constraints(paths):
    document = _build(paths)
    by_id = {item["id"]: item for item in document["constraints"]}
    assert list(by_id) == ["c1", "c2"]
    assert document["shacl"]["conforms"] is True
    assert document["llm"] == {"mode": "skipped", "reason": "--skip-llm"}
    assert document["context"]["zone"] == "zoneB"
    assert document["context"]["human_present"] is True

    c1 = by_id["c1"]
    assert c1["status"] == "active"
    assert c1["issues"] == []
    assert c1["card"] == C1_CARD
    assert c1["card_sha256"] == hashlib.sha256(C1_CARD.encode("utf-8")).hexdigest()
    assert c1["original"] == {
        "value": "180",
        "unit": str(UNIT["DEG-PER-SEC"]),
        "unit_name": "DEG-PER-SEC",
    }
    assert c1["si"]["unit_name"] == "RAD-PER-SEC"
    assert Decimal(c1["si"]["value"]) == Decimal("3.14159265")
    assert c1["condition"] is None

    c2 = by_id["c2"]
    assert c2["status"] == "active"
    assert c2["card"] == C2_CARD
    assert c2["card_sha256"] == hashlib.sha256(c2["card"].encode("utf-8")).hexdigest()
    assert c2["original"]["value"] == "0.25"
    assert c2["si"]["value"] == "0.25"
    assert c2["si"]["unit"] == str(UNIT["M-PER-SEC"])
    assert c2["condition"]["in_zone"] == "zoneB"
    assert c2["condition"]["human_present"] is True


def test_other_contexts_drop_the_conditional_constraint(paths):
    zone_a = _build(paths, zone="zoneA", human_present=True)
    assert [item["id"] for item in zone_a["constraints"]] == ["c1"]
    quiet = _build(paths, zone="zoneB", human_present=False)
    assert [item["id"] for item in quiet["constraints"]] == ["c1"]


def test_mock_pass_and_fail(paths):
    passing = MockVerifier()
    document = _build(paths, skip_llm=False, verifier=passing)
    assert {item["status"] for item in document["constraints"]} == {"active"}
    assert document["llm"]["mode"] == "verified"
    assert len(passing.calls) == 2
    assert "inZone=zoneB" in passing.calls[1].prompt or any("inZone=zoneB" in call.prompt for call in passing.calls)

    failing = MockVerifier(verdict="fail", issues=["quote does not state the limit"])
    reviewed = _build(paths, skip_llm=False, verifier=failing)
    assert {item["status"] for item in reviewed["constraints"]} == {"needs_review"}
    assert any("verdict fail" in issue for item in reviewed["constraints"] for issue in item["issues"])


def test_missing_api_key_needs_review(paths, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    document = _build(paths, skip_llm=False, verifier=None)
    assert document["llm"]["mode"] == "unavailable"
    assert all(item["status"] == "needs_review" for item in document["constraints"])
    assert all(any("OPENAI_API_KEY" in issue for issue in item["issues"]) for item in document["constraints"])


def test_negative_speed_does_not_demote_a_valid_constraint(paths, tmp_path):
    graph_path = _with_extra(paths, tmp_path, BAD_SPEED)
    document = _build(paths, graph_path=graph_path)
    by_id = {item["id"]: item for item in document["constraints"]}
    assert by_id["c1"]["status"] == "active"
    assert by_id["cbad"]["status"] == "needs_review"
    assert any(">= 0" in issue for issue in by_id["cbad"]["issues"])
    assert document["shacl"]["conforms"] is False


def test_incompatible_unit_is_reported_on_that_constraint(paths, tmp_path):
    graph_path = _with_extra(paths, tmp_path, BAD_KIND)
    document = _build(paths, graph_path=graph_path)
    by_id = {item["id"]: item for item in document["constraints"]}
    assert by_id["c1"]["status"] == "active"
    issues = " ".join(by_id["ctemp"]["issues"])
    assert by_id["ctemp"]["status"] == "needs_review"
    assert "Incompatible quantity kinds" in issues
    assert by_id["ctemp"]["si"] is None
    assert by_id["ctemp"]["card"] is None


def test_committed_example_matches_the_sample_run(paths):
    committed = json.loads((ROOT / "examples" / "active_constraints.json").read_text(encoding="utf-8"))
    assert _build(paths) == committed


def test_cli_writes_the_sample_document(paths, tmp_path):
    output = tmp_path / "active_constraints.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "kbcc",
            "build",
            "--zone",
            "zoneB",
            "--human-present",
            "--skip-llm",
            "--output",
            str(output),
            "--strict",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "c1: active" in result.stdout
    assert "c2: active" in result.stdout
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["constraints"][0]["card"] == C1_CARD


def test_cli_unknown_zone_exits_2():
    result = subprocess.run(
        [sys.executable, "-m", "kbcc", "build", "--zone", "zoneZ", "--skip-llm"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Unknown zone" in result.stderr


def test_qudt_property_iris_used_by_the_fixture():
    assert str(QUDT.conversionMultiplier) == "http://qudt.org/schema/qudt/conversionMultiplier"
    assert str(QUDT.conversionOffset) == "http://qudt.org/schema/qudt/conversionOffset"
    assert str(QUDT.hasQuantityKind) == "http://qudt.org/schema/qudt/hasQuantityKind"
