.PHONY: install generate test fmt lint clean

install:
	pip install -e ".[dev]"

generate:
	python -m ica.cli generate --out data/ica.db --seed 42

test:
	pytest -v

fmt:
	ruff format src tests

lint:
	ruff check src tests

clean:
	rm -rf data/*.db .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
