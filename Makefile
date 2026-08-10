.PHONY: all extract build run validate test install clean

PYTHON ?= python3

all: build run

extract:
	$(PYTHON) solution/extract.py

build:
	$(PYTHON) solution/build_kg.py

run:
	$(PYTHON) solution/run.py --skip-build

validate:
	$(PYTHON) solution/run.py --validate

test:
	$(PYTHON) -m pytest solution/tests -q

install:
	$(PYTHON) -m pip install -r solution/requirements.txt

clean:
	rm -rf output/*
	rm -f solution/knowledge_graph.db
	rm -f solution/extracted_data.json
	rm -f solution/sample_submission.jsonl
	rm -rf solution/__pycache__
