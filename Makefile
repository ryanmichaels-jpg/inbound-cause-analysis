.PHONY: install generate dashboard test fmt lint clean

install:
	pip install -e ".[dev]"

generate:
	python -m ica.cli

dashboard:
	streamlit run src/ica/dashboard.py

test:
	pytest -v

fmt:
	ruff format src tests

lint:
	ruff check src tests

clean:
	rm -rf data/*.db .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
