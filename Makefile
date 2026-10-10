.PHONY: install test lint run fixtures
install:
	python -m pip install -e ".[dev]"
test:
	pytest
lint:
	ruff check .
run:
	uvicorn app.main:app --reload
fixtures:
	python scripts/generate_fixtures.py
