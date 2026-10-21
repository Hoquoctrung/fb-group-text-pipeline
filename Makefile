.PHONY: setup test lint format check demo

setup:
	python3.11 -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip
	. .venv/bin/activate && pip install -e ".[dev,crawl]"

test:
	pytest -m "not integration and not slow" -q

lint:
	ruff check .
	ruff format --check src tests

format:
	ruff check . --fix
	ruff format .

check:
	ruff check .
	ruff format --check src tests
	mypy src
	pytest -m "not integration and not slow" -q

demo:
	fbpipe demo
