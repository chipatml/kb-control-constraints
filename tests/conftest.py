"""Shared paths for the sample graph, shapes, QUDT fixture, and config."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def paths() -> dict[str, Path]:
    return {
        "graph": ROOT / "data" / "constraints.ttl",
        "shapes": ROOT / "data" / "shapes.ttl",
        "qudt": ROOT / "data" / "qudt_units_fixture.ttl",
        "config": ROOT / "config" / "defaults.yaml",
    }
