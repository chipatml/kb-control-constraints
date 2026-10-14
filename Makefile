PYTHON ?= python3

.PHONY: test download-qudt sample

test:
	$(PYTHON) -m pytest

download-qudt:
	$(PYTHON) scripts/download_qudt.py --output data/qudt/VOCAB_QUDT-UNITS-ALL.ttl

sample:
	$(PYTHON) -m kbcc build --zone zoneB --human-present --skip-llm --output examples/active_constraints.json
