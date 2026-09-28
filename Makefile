PYTHON ?= .venv/bin/python
VS := $(PYTHON) -m visionsentinel.cli.main

.PHONY: help install test test-fast profiles detectors

help:
	@echo "install     create .venv and install VisionSentinel with dev extras"
	@echo "test        run the full test suite"
	@echo "test-fast   run unit tests only"
	@echo "profiles    validate every shipped profile"
	@echo "detectors   list registered detectors and unsupported attack classes"

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
