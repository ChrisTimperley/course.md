.PHONY: test lint fix type

test:
	uv run pytest

lint:
	uv run ruff check .

fix:
	uv run ruff check --fix .

type:
	uv run mypy .
