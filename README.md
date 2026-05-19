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
