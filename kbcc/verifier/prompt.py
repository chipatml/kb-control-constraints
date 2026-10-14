"""Prompt template asking an LLM to judge one consistency card."""

from __future__ import annotations

VERIFIER_PROMPT_TEMPLATE = """You are checking one robot controller constraint before it is allowed to become active.

Return ONLY a JSON object of the form:
{{"id": "<constraint id>", "verdict": "pass" | "fail" | "unsure", "issues": ["..."]}}

Do not wrap the JSON in Markdown.

Checks:
1. Quote support. The source quote must state the same limit as the original value once the quote's number and unit are converted. A leading ± means a symmetric limit of that magnitude (180°/s supports an original value of 180 DEG-PER-SEC). 250 mm/s supports 0.25 M-PER-SEC.
2. Unit conversion. The SI value in the card must be the original value converted into the SI unit shown in the card.
3. Hardness wording. If the quote says "shall" or "must", hardness must be "hard". If the quote says "should" or "recommended", hardness must be "soft". If none of those words appear, do not fail the hardness check.
4. Captured conditions. If the quote limits the constraint to a zone or to a person being present, the condition below must record that. If the quote states an unconditional limit, the condition must be none.

Verdict "pass" only when every check holds. Use "fail" when a check is contradicted. Use "unsure" when the quote is too vague to decide.

Constraint id: {constraint_id}
Card:
{card}
Condition: {condition}
Record:
{record_json}
"""


def render_prompt(*, constraint_id: str, card: str, condition: str, record_json: str) -> str:
    """Fill the verifier template for one constraint."""
    return VERIFIER_PROMPT_TEMPLATE.format(
        constraint_id=constraint_id,
        card=card,
        condition=condition,
        record_json=record_json,
    )
