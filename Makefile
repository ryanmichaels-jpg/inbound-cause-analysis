.PHONY: install generate dashboard insight test fmt lint clean

# v1.5: NOISE=<clean|FLOAT> selects the noise profile.
#   make generate                  -> realistic default (--noise 1.0)
#   make generate NOISE=clean      -> v1 pristine (--clean)
#   make generate NOISE=2          -> STRESS_2X (--noise 2)
NOISE ?=
ifeq ($(NOISE),clean)
NOISE_ARG := --clean
else ifeq ($(NOISE),)
NOISE_ARG :=
else
NOISE_ARG := --noise $(NOISE)
endif

install:
	pip install -e ".[dev]"

generate:
	python -m ica.cli $(NOISE_ARG)

dashboard:
	streamlit run src/ica/dashboard.py

insight:
	python -m ica.insight

test:
	pytest -v

fmt:
	ruff format src tests

lint:
	ruff check src tests

clean:
	rm -rf data/*.db .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
