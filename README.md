# kb-control-constraints

`kbcc` turns robot safety and operating constraints stored in an RDF Turtle knowledge graph into validated JSON a controller can consume (MPC or control barrier functions).

Each selected constraint is converted to SI with QUDT, checked deterministically, and written with the original value beside the SI value. It is marked `active` only when those checks pass and an LLM verifier agrees, or when the LLM step is explicitly skipped.

## Pipeline

1. Load the constraint graph, the SHACL shapes, and a QUDT units graph.
2. Run a SPARQL context query. Unconditional constraints are always included. A constraint with `ex:condition` is included only when every condition it states matches the requested zone and human-present flag.
3. Convert the stored value to the SI unit configured for its variable, using `qudt:conversionMultiplier` and `qudt:conversionOffset`. Units must share a `qudt:hasQuantityKind`.
4. Run deterministic checks: SHACL, quote-versus-value (pint), plausibility ranges, and bound conflicts.
5. Render a fixed consistency card and store its SHA-256.
6. Ask a pluggable verifier (OpenAI-compatible HTTP client, or a mock) to judge the card. Skip this step with `--skip-llm`.
7. Write JSON. Status is `active` or `needs_review`.

```text
Turtle constraints ──► SPARQL context ──► QUDT to SI ──► SHACL / quote / plausibility / conflicts
        │                                                              │
        └──────────── consistency card + optional LLM verifier ────────┴──► active_constraints.json
```

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m kbcc build --zone zoneB --human-present --skip-llm --output active_constraints.json
python -m pytest
```

`make test` runs pytest. `make sample` writes `examples/active_constraints.json` for zone B with a person present. `make download-qudt` downloads the full QUDT 2.1 unit vocabulary to `data/qudt/VOCAB_QUDT-UNITS-ALL.ttl`. Tests do not need that download; they use the trimmed fixture `data/qudt_units_fixture.ttl`.

Pass `--qudt data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` to convert against the full vocabulary. The fixture is enough for the sample units.

## Data model

Namespace `ex:` is `<http://example.org/robot#>`. Classes are `Robot`, `Joint`, `Zone`, `Constraint`, and `Condition`.

Each `Constraint` has:

| Property | Value |
| --- | --- |
| `ex:subject` | IRI of the joint or robot the limit applies to |
| `ex:variable` | string, such as `joint_velocity` or `tcp_speed` |
| `ex:operator` | `<=`, `>=`, `==`, `<`, or `>` |
| `ex:value` | `xsd:decimal`, the number as stated for that unit (not a binary float) |
| `ex:unit` | QUDT unit IRI, for example `unit:DEG-PER-SEC` |
| `ex:hardness` | `hard` or `soft` |
| `ex:condition` | optional blank node with `ex:inZone` and/or `ex:humanPresent` |
| `ex:sourceDoc`, `ex:page`, `ex:quote` | provenance |

Sample rows in `data/constraints.ttl`:

- `c1`: joint `j1`, `joint_velocity <= 180` `DEG-PER-SEC`, hard, from `UR5e_spec.pdf` page 4, quote `Max joint speed: ±180°/s`. Unconditional.
- `c2`: robot `arm1`, `tcp_speed <= 0.25` `M-PER-SEC`, hard, only in `zoneB` while a person is present, from `Safety_manual.pdf` page 12, quote `Reduce TCP speed to 250 mm/s when operators are present.`

SHACL shapes live in `data/shapes.ttl` (not in the data file). They require every field above, restrict operator and hardness with `sh:in`, require `xsd:decimal` for the value, and require speed and velocity values to be `>= 0`.

## Context query

```bash
python -m kbcc build --zone zoneB --human-present --skip-llm
python -m kbcc build --zone zoneA --no-human-present --skip-llm
```

`--zone` accepts a local name (`zoneB`) or a full IRI. `--human-present` / `--no-human-present` sets the person flag (default false).

A constraint with no `ex:condition` is always exported. A condition that only sets `ex:inZone` ignores the human flag, and a condition that only sets `ex:humanPresent` ignores the zone. Both fields, when present, must match. The query is `kbcc.query.ACTIVE_CONSTRAINTS_QUERY`.

## Units

The map from variable to SI unit is `config/defaults.yaml`:

- `joint_velocity` → `RAD-PER-SEC`
- `tcp_speed` → `M-PER-SEC`

Add another variable by naming its QUDT SI unit and, if you want a guard rail, a plausibility window in that SI unit. Windows are inclusive.

Conversion follows QUDT:

```text
si = value * conversionMultiplier + conversionOffset
target = (si - targetOffset) / targetMultiplier
```

A missing offset is 0. The source and target units must share at least one `qudt:hasQuantityKind`. The pipeline records a `needs_review` issue, and does not invent a card, when:

- the variable is not in the config
- either unit has no `qudt:conversionMultiplier` in the units graph
- the quantity kinds are disjoint, or a unit has none

JSON keeps the exact source lexical value and unit next to the SI value. `180` `DEG-PER-SEC` becomes SI `3.14159265` `RAD-PER-SEC` with QUDT's published multiplier `0.0174532925` (the card rounds that to 6 decimal places: `3.141593`).

## Deterministic checks

- **SHACL.** Violations are attached to the constraint they focus on. A violation on a different constraint does not demote a constraint that itself conforms.
- **Quote.** pint reads a number and unit out of the quote, including a leading `±` as a magnitude and `mm/s` as millimetres per second. The quote quantity is converted into the constraint's unit and compared within the configured tolerance. `250 mm/s` supports `0.25 M-PER-SEC`. `±180°/s` supports `180 DEG-PER-SEC`.
- **Plausibility.** The SI value must sit inside the variable's configured range.
- **Conflicts.** Constraints are grouped by subject and variable after SI conversion. The same operator with different values is a disagreeing duplicate. An empty intersection of lower and upper bounds (including `==`) is a contradiction. The default checker is interval arithmetic. Set `conflict.engine: z3` and install `pip install -e ".[z3]"` to use z3 instead. z3 is optional; tests skip it when it is not installed.

`--strict` exits 1 if any selected constraint needs review or the whole graph fails SHACL.

## Consistency card and verifier

The card is a fixed string. For the sample joint limit:

```text
CONSTRAINT c1: j1.joint_velocity <= 3.141593 RAD-PER-SEC (original: 180.0 DEG-PER-SEC; hardness: hard). SOURCE: UR5e_spec.pdf p.4: "Max joint speed: ±180°/s"
```

`card_sha256` in the JSON is the hex SHA-256 of that UTF-8 string. Conditions are not part of the card; they are in the JSON and in the verifier prompt.

The prompt template is `VERIFIER_PROMPT_TEMPLATE` in `kbcc/verifier/prompt.py`. It asks for JSON `{id, verdict: pass|fail|unsure, issues[]}` and tells the model to check quote support, the SI conversion, hardness wording (`shall` / `must` → hard, `should` / `recommended` → soft), and whether zone or human conditions in the quote were captured.

`OpenAICompatibleVerifier` POSTs to `{OPENAI_BASE_URL}/chat/completions` (default `https://api.openai.com/v1`) with `OPENAI_API_KEY` and `OPENAI_MODEL` (default `gpt-4o-mini`). If the key is unset, the step is not called and every selected constraint is `needs_review` unless you pass `--skip-llm`. `--skip-llm` is what allows a deterministic pass to be `active`.

`MockVerifier` returns scripted verdicts for tests. Pass any object with `verify(request) -> VerificationResult` into `build_active_constraints`.

## Output

`active_constraints.json` contains `context`, `shacl`, `llm`, and `constraints`. Each constraint has `status` (`active` or `needs_review`), `issues`, `original` (value, unit IRI, unit name), `si` (same, or null when conversion failed), `condition`, `source`, `card`, and `card_sha256`. Decimal values are strings so the lexical form is preserved.

With `--zone zoneB --human-present --skip-llm` the sample yields two active constraints: `c1` at `3.14159265 RAD-PER-SEC` and `c2` at `0.25 M-PER-SEC`.

## Tests

```bash
python -m pytest
```

GitHub Actions (`.github/workflows/tests.yml`) installs the package and runs pytest on push and pull request. Coverage includes QUDT conversion, each validator, the context query, the verifier client, and an end-to-end sample run.

## QUDT attribution

The unit fixture is a trimmed excerpt of the QUDT Units vocabulary, release 2.1.47 (`http://qudt.org/2.1/vocab/unit`). The QUDT ontologies are issued under a Creative Commons Attribution 4.0 International License (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/. Attribution: QUDT.org.
