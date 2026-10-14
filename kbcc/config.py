"""Load the variable, tolerance, and unit-mapping configuration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from kbcc.errors import ConfigError


@dataclass(frozen=True)
class VariableSpec:
    si_unit: str
    plausibility_min: Decimal | None
    plausibility_max: Decimal | None


@dataclass(frozen=True)
class AppConfig:
    variables: dict[str, VariableSpec]
    quote_abs_tolerance: Decimal
    quote_rel_tolerance: Decimal
    conflict_abs_tolerance: Decimal
    conflict_rel_tolerance: Decimal
    conflict_engine: str
    si_decimal_places: int
    pint_units: dict[str, str]
    quote_units: dict[str, str]


def load_config(path: Path) -> AppConfig:
    """Read ``defaults.yaml`` (or another file with the same shape)."""
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file {path} must be a mapping.")

    variables_raw = raw.get("variables")
    if not isinstance(variables_raw, dict) or not variables_raw:
        raise ConfigError("Config must define a non-empty 'variables' mapping.")
    variables: dict[str, VariableSpec] = {}
    for name, spec in variables_raw.items():
        if not isinstance(spec, dict) or "si_unit" not in spec:
            raise ConfigError(f"Variable '{name}' needs an si_unit.")
        minimum, maximum = _plausibility(spec.get("plausibility"), f"variables.{name}.plausibility")
        variables[str(name)] = VariableSpec(
            si_unit=str(spec["si_unit"]),
            plausibility_min=minimum,
            plausibility_max=maximum,
        )

    quote = _section(raw, "quote_check")
    conflict = _section(raw, "conflict")
    card = _section(raw, "card")
    engine = str(conflict.get("engine", "interval"))
    if engine not in {"interval", "z3"}:
        raise ConfigError("conflict.engine must be 'interval' or 'z3'.")
    places = card.get("si_decimal_places", 6)
    if isinstance(places, bool) or not isinstance(places, int) or places < 0:
        raise ConfigError("card.si_decimal_places must be a non-negative integer.")

    return AppConfig(
        variables=variables,
        quote_abs_tolerance=_decimal(quote.get("absolute_tolerance", "0.000001"), "quote_check.absolute_tolerance"),
        quote_rel_tolerance=_decimal(quote.get("relative_tolerance", "0.000001"), "quote_check.relative_tolerance"),
        conflict_abs_tolerance=_decimal(
            conflict.get("absolute_tolerance", "0.000001"), "conflict.absolute_tolerance"
        ),
        conflict_rel_tolerance=_decimal(
            conflict.get("relative_tolerance", "0.000001"), "conflict.relative_tolerance"
        ),
        conflict_engine=engine,
        si_decimal_places=places,
        pint_units=_string_map(raw.get("pint_units"), "pint_units"),
        quote_units=_string_map(raw.get("quote_units"), "quote_units"),
    )


def _section(raw: dict, name: str) -> dict:
    value = raw.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"Config section '{name}' must be a mapping.")
    return value


def _plausibility(raw: object, label: str) -> tuple[Decimal | None, Decimal | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be a mapping with min and/or max.")
    minimum = _decimal(raw["min"], f"{label}.min") if "min" in raw and raw["min"] is not None else None
    maximum = _decimal(raw["max"], f"{label}.max") if "max" in raw and raw["max"] is not None else None
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ConfigError(f"{label} min is greater than max.")
    return minimum, maximum


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ConfigError(f"{label} must be a quoted decimal string, not a YAML float.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ConfigError(f"{label} is not a decimal: {value!r}") from exc


def _string_map(raw: object, label: str) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"Config must define a non-empty '{label}' mapping.")
    mapping: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{label}.{key} must be a unit expression string.")
        mapping[str(key)] = value
    return mapping
