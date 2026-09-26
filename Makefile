.PHONY: install test lint format demo clean

install:
	uv venv && uv pip install -e '.[dev]'

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

demo:
	bash examples/run_demo.sh

clean:
	rm -rf results/*.png results/*.html results/*.md .mutmut-cache
