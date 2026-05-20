# Inbound Cause Analysis (ICA)

> Jesse's RCA pipeline, flipped. Instead of identifying what to *eliminate* in support, ICA identifies what to *amplify* in GTM by analyzing why inbound leads convert and which messages, channels, and content resonate.

**Checkpoint 1 status:** synthetic data generator + schema. The full case-study README arrives in CP6.

## Quick start

```bash
make install     # installs project in editable mode with dev extras
make generate    # produces data/ica.db from synthetic generator
make test        # runs schema and aha-pattern smoke tests
```

## Project docs

- `PROJECT.md` — scope, architecture, six-checkpoint build sequence.
- `docs/data-world.md` — Gate 1: schema, personas, channels, content library, theme taxonomy.
- `docs/aha-patterns.md` — Gate 2: statistical contracts for the five aha findings (four headline + one secondary).

## Known followups

- `test_personas.py` — dedicated unit-level coverage for the persona generator. `personas.py` is currently verified at sample level and exercised indirectly through downstream module tests (`test_channels.py`, and later journeys/outcomes); a dedicated suite is a parity gap with `taxonomy`, `schema`, and `channels`.

## Known v1 limitations

- The Finding 5 comparison cell (non-Patricia leads with a `compliance_security` primary theme) lands at **111 leads** — a uniform 6% of the actual 1,850-lead non-Patricia population, per `aha-patterns.md`'s "~6% of each non-Patricia persona" rule. `aha-patterns.md` also states "~120"; that figure was an estimate against a rounded ~2,000 population. 111 is the precise computation and clears the Finding 5 threshold (≥80) with margin — it is intentional, not drift.
