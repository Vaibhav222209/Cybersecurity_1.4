PYTHON ?= python3

.PHONY: help check-python lint test up scan

help:
	@printf '%s\n' 'lint: check scaffold and documentation' 'test: run Phase 1 tests' 'up: unavailable until Phase 2' 'scan: unavailable until Phase 3'

check-python:
	@$(PYTHON) -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"'

lint: check-python
	$(PYTHON) tools/check_repository.py

test: check-python
	$(PYTHON) -m unittest discover -s tests -v

up:
	@printf '%s\n' 'Phase 2 pending: no Docker Compose application has been implemented.' >&2
	@exit 2

scan:
	@printf '%s\n' 'Phase 3 pending: security scanners have not been wired or validated.' >&2
	@exit 2
