"""Select, convert, validate, and serialize active controller constraints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from rdflib import Graph

from kbcc.card import card_sha256, render_card
from kbcc.config import AppConfig, load_config
from kbcc.decimals import decimal_to_str, format_original, format_si
from kbcc.errors import UnitConversionError, VerifierError
from kbcc.models import ConstraintRecord
from kbcc.namespaces import local_name
from kbcc.query import resolve_zone, select_active_constraints
from kbcc.units import convert_for_variable, index_units
from kbcc.validate.conflict import Bound, find_conflicts
from kbcc.validate.plausibility import check_plausibility
from kbcc.validate.quote import check_quote
from kbcc.validate.shacl_check import validate_constraints
from kbcc.verifier.base import ConstraintVerifier, VerificationRequest
from kbcc.verifier.openai_client import OpenAICompatibleVerifier
from kbcc.verifier.prompt import render_prompt


@dataclass
class _Prepared:
    record: ConstraintRecord
    si_value: Decimal | None
    si_unit_uri: str | None
    si_unit_name: str | None
    card: str | None
    card_sha256: str | None
    issues: list[str]


def build_active_constraints(
    *,
    graph_path: Path,
    shapes_path: Path,
    qudt_path: Path,
    config_path: Path,
    zone: str | None,
    human_present: bool,
    skip_llm: bool = False,
    verifier: ConstraintVerifier | None = None,
) -> dict:
    """Run the pipeline and return the controller document.

    A constraint is ``active`` only when every deterministic check passes and
    the verifier returns ``pass``, or when ``skip_llm`` is set and the
    deterministic checks pass. Anything else is ``needs_review``.
    """
    data = _parse(graph_path)
    shapes = _parse(shapes_path)
    qudt = _parse(qudt_path)
    config = load_config(config_path)
    units = index_units(qudt)
    zone_uri = resolve_zone(data, zone) if zone else None
    records = select_active_constraints(data, zone_uri, human_present)
    report = validate_constraints(data, shapes)

    shacl_by_focus: dict[str, list[str]] = {}
    for finding in report.findings:
        if finding.focus is None:
            continue
        shacl_by_focus.setdefault(finding.focus, []).append(finding.message)

    prepared = [_prepare(record, shacl_by_focus.get(record.uri, []), config, units) for record in records]
    _apply_conflicts(prepared, config)
    llm = _apply_verifier(prepared, verifier=verifier, skip_llm=skip_llm)

    constraints = [_serialize(item) for item in sorted(prepared, key=lambda item: item.record.id)]
    return {
        "constraints": constraints,
        "context": {
            "human_present": human_present,
            "zone": local_name(str(zone_uri)) if zone_uri is not None else None,
            "zone_uri": str(zone_uri) if zone_uri is not None else None,
        },
        "llm": llm,
        "shacl": {
            "conforms": report.conforms,
            "results": [{"focus": finding.focus, "message": finding.message} for finding in report.findings],
        },
    }


def _parse(path: Path) -> Graph:
    if not path.is_file():
        raise FileNotFoundError(path)
    graph = Graph()
    graph.parse(path)
    return graph


def _prepare(
    record: ConstraintRecord,
    shacl_issues: list[str],
    config: AppConfig,
    units: dict,
) -> _Prepared:
    issues = list(shacl_issues)
    si_value: Decimal | None = None
    si_unit_uri: str | None = None
    si_unit_name: str | None = None
    card: str | None = None
    digest: str | None = None
    try:
        si_value, si_unit_uri = convert_for_variable(
            record.variable, record.value, record.unit_uri, config, units
        )
    except UnitConversionError as exc:
        issues.append(f"conversion: {exc}")
    else:
        si_unit_name = local_name(si_unit_uri)
        spec = config.variables[record.variable]
        issues.extend(
            check_plausibility(
                record.variable,
                si_value,
                si_unit_name,
                spec.plausibility_min,
                spec.plausibility_max,
            )
        )
        card = render_card(
            constraint_id=record.id,
            subject=record.subject_name,
            variable=record.variable,
            operator=record.operator,
            si_value=format_si(si_value, config.si_decimal_places),
            si_unit=si_unit_name,
            original_value=format_original(record.value),
            original_unit=record.unit_name,
            hardness=record.hardness,
            source_doc=record.source_doc,
            page=record.page,
            quote=record.quote,
        )
        digest = card_sha256(card)

    pint_unit = config.pint_units.get(record.unit_name)
    if pint_unit is None:
        issues.append(
            f"quote: no pint mapping for unit {record.unit_name}. Add it under pint_units in the config."
        )
    else:
        issues.extend(
            check_quote(
                quote=record.quote,
                value=record.value,
                unit_name=record.unit_name,
                pint_unit=pint_unit,
                quote_units=config.quote_units,
                abs_tolerance=config.quote_abs_tolerance,
                rel_tolerance=config.quote_rel_tolerance,
            )
        )
    return _Prepared(
        record=record,
        si_value=si_value,
        si_unit_uri=si_unit_uri,
        si_unit_name=si_unit_name,
        card=card,
        card_sha256=digest,
        issues=issues,
    )


def _apply_conflicts(prepared: list[_Prepared], config: AppConfig) -> None:
    bounds = [
        Bound(
            constraint_id=item.record.id,
            subject_uri=item.record.subject_uri,
            subject_name=item.record.subject_name,
            variable=item.record.variable,
            operator=item.record.operator,
            si_value=item.si_value,
            si_unit_name=item.si_unit_name or "",
        )
        for item in prepared
        if item.si_value is not None and item.si_unit_name is not None
    ]
    found = find_conflicts(
        bounds,
        abs_tolerance=config.conflict_abs_tolerance,
        rel_tolerance=config.conflict_rel_tolerance,
        engine=config.conflict_engine,
    )
    for item in prepared:
        item.issues.extend(found.get(item.record.id, []))


def _apply_verifier(
    prepared: list[_Prepared],
    *,
    verifier: ConstraintVerifier | None,
    skip_llm: bool,
) -> dict[str, str]:
    if skip_llm:
        return {"mode": "skipped", "reason": "--skip-llm"}

    active = verifier
    if active is None:
        client = OpenAICompatibleVerifier()
        if not client.available:
            for item in prepared:
                item.issues.append(
                    "llm: verifier skipped because OPENAI_API_KEY is unset; "
                    "pass --skip-llm to accept deterministic checks"
                )
            return {"mode": "unavailable", "reason": "OPENAI_API_KEY is unset"}
        active = client

    for item in prepared:
        if item.card is None:
            item.issues.append("llm: consistency card was not built, so the verifier was not run")
            continue
        request = VerificationRequest(
            constraint_id=item.record.id,
            card=item.card,
            prompt=render_prompt(
                constraint_id=item.record.id,
                card=item.card,
                condition=_condition_text(item.record),
                record_json=_record_json(item),
            ),
        )
        try:
            result = active.verify(request)
        except VerifierError as exc:
            item.issues.append(f"llm: {exc}")
            continue
        if result.constraint_id != item.record.id:
            item.issues.append(
                f"llm: response id {result.constraint_id!r} does not match constraint {item.record.id}"
            )
        if result.verdict != "pass" or result.issues:
            if result.verdict != "pass":
                item.issues.append(f"llm: verdict {result.verdict}")
            else:
                item.issues.append("llm: verdict pass but issues were reported")
            item.issues.extend(f"llm: {issue}" for issue in result.issues)
    return {"mode": "verified", "reason": type(active).__name__}


def _condition_text(record: ConstraintRecord) -> str:
    parts: list[str] = []
    if record.zone_name:
        parts.append(f"inZone={record.zone_name}")
    if record.human_present is not None:
        parts.append(f"humanPresent={'true' if record.human_present else 'false'}")
    return "; ".join(parts) if parts else "none"


def _record_json(item: _Prepared) -> str:
    record = item.record
    payload = {
        "id": record.id,
        "subject": record.subject_name,
        "variable": record.variable,
        "operator": record.operator,
        "hardness": record.hardness,
        "original": {"value": record.value_lexical, "unit": record.unit_name},
        "si": {
            "value": decimal_to_str(item.si_value) if item.si_value is not None else None,
            "unit": item.si_unit_name,
        },
        "condition": _condition_text(record),
        "source": {"document": record.source_doc, "page": record.page, "quote": record.quote},
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _serialize(item: _Prepared) -> dict:
    record = item.record
    condition = None
    if record.zone_uri is not None or record.human_present is not None:
        condition = {
            "human_present": record.human_present,
            "in_zone": record.zone_name,
            "in_zone_uri": record.zone_uri,
        }
    return {
        "card": item.card,
        "card_sha256": item.card_sha256,
        "condition": condition,
        "hardness": record.hardness,
        "id": record.id,
        "issues": list(item.issues),
        "operator": record.operator,
        "original": {
            "unit": record.unit_uri,
            "unit_name": record.unit_name,
            "value": record.value_lexical,
        },
        "si": None
        if item.si_value is None
        else {
            "unit": item.si_unit_uri,
            "unit_name": item.si_unit_name,
            "value": decimal_to_str(item.si_value),
        },
        "source": {"document": record.source_doc, "page": record.page, "quote": record.quote},
        "status": "active" if not item.issues else "needs_review",
        "subject": record.subject_uri,
        "subject_name": record.subject_name,
        "uri": record.uri,
        "variable": record.variable,
    }
