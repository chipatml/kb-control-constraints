"""Errors raised by the constraint pipeline."""


class ConfigError(Exception):
    """The YAML configuration is missing or invalid."""


class DataError(Exception):
    """The knowledge graph cannot be exported as controller constraints."""


class UnknownZoneError(DataError):
    """The requested context zone is not declared in the graph."""


class UnitConversionError(Exception):
    """A constraint value could not be converted to its SI unit."""


class UnknownVariableError(UnitConversionError):
    """The variable has no SI unit mapping in the config."""

    def __init__(self, variable: str, known: list[str]) -> None:
        known_text = ", ".join(known) if known else "(none)"
        super().__init__(
            f"Unknown variable '{variable}'. Known variables: {known_text}. "
            "Add a mapping in the config to an SI unit."
        )
        self.variable = variable


class MissingUnitError(UnitConversionError):
    """The units graph has no conversion factor for a QUDT unit."""


class IncompatibleQuantityKindError(UnitConversionError):
    """The source and target units do not share a qudt:hasQuantityKind."""


class ConflictEngineError(Exception):
    """The configured conflict checker cannot run."""


class VerifierError(Exception):
    """The LLM verifier failed before producing a verdict."""
