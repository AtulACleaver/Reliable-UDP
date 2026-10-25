.PHONY: check lint test

check: lint test

lint:
	python -m ruff check .

test:
	python -m pytest tests/
