PYTHON ?= .venv/bin/python
VS := $(PYTHON) -m visionsentinel.cli.main

.PHONY: help install test test-fast profiles detectors e2e benchmark verifier-bundle

help:
	@echo "install     create .venv and install VisionSentinel with dev extras"
	@echo "test        run the full test suite"
	@echo "test-fast   run unit tests only"
	@echo "profiles    validate every shipped profile"
	@echo "detectors   list registered detectors and unsupported attack classes"
	@echo "e2e         run browser workflow tests (requires Playwright Chromium)"
	@echo "benchmark   write benchmarks/latest.json and benchmarks/latest.md"
	@echo "verifier-bundle  create a standalone checksummed verifier archive"

install:
	python3.12 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,torch]"

test:
	$(PYTHON) -m pytest

test-fast:
	$(PYTHON) -m pytest tests/unit -q

profiles:
	$(VS) profiles list

detectors:
	$(VS) detectors

e2e:
	cd frontend && npm run test:e2e

benchmark:
	$(VS) benchmark

verifier-bundle:
	$(PYTHON) scripts/build_verifier_bundle.py
