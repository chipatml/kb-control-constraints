"""Consistency card text and SHA-256."""

import hashlib

from kbcc.card import card_sha256, render_card
from tests.expected_cards import C1_CARD, C2_CARD


def test_c1_card_matches_the_fixed_format():
    card = render_card(
        constraint_id="c1",
        subject="j1",
        variable="joint_velocity",
        operator="<=",
        si_value="3.141593",
        si_unit="RAD-PER-SEC",
        original_value="180.0",
        original_unit="DEG-PER-SEC",
        hardness="hard",
        source_doc="UR5e_spec.pdf",
        page=4,
        quote="Max joint speed: ±180°/s",
    )
    assert card == C1_CARD
    assert card_sha256(card) == hashlib.sha256(C1_CARD.encode("utf-8")).hexdigest()


def test_c2_card_matches_the_fixed_format():
    card = render_card(
        constraint_id="c2",
        subject="arm1",
        variable="tcp_speed",
        operator="<=",
        si_value="0.250000",
        si_unit="M-PER-SEC",
        original_value="0.25",
        original_unit="M-PER-SEC",
        hardness="hard",
        source_doc="Safety_manual.pdf",
        page=12,
        quote="Reduce TCP speed to 250 mm/s when operators are present.",
    )
    assert card == C2_CARD
