# Inbound Cause Analysis (ICA)

> Jesse's RCA pipeline, flipped. Instead of identifying what to *eliminate* in support, ICA identifies what to *amplify* in GTM by analyzing why inbound leads convert and which messages, channels, and content resonate.

**Checkpoint 1 status:** synthetic data generator + schema. The full case-study README arrives in CP6.

## Quick start

```bash
make install     # installs project in editable mode with dev extras
make generate    # produces data/ica.db (== python -m ica.cli)
make test        # runs the full test suite incl. the aha-pattern contract
```

`make generate` is deterministic — the same `--seed` (default 42) reproduces the same dataset byte-for-byte. Run it first after cloning; `data/ica.db` is git-ignored and regenerable.

## Project docs

- `PROJECT.md` — scope, architecture, six-checkpoint build sequence.
- `docs/data-world.md` — Gate 1: schema, personas, channels, content library, theme taxonomy.
- `docs/aha-patterns.md` — Gate 2: statistical contracts for the five aha findings (four headline + one secondary).

## Known followups

- `test_personas.py` — dedicated unit-level coverage for the persona generator. `personas.py` is currently verified at sample level and exercised indirectly through downstream module tests (`test_channels.py`, and later journeys/outcomes); a dedicated suite is a parity gap with `taxonomy`, `schema`, and `channels`.

## Known v1 limitations

- The Finding 5 comparison cell (non-Patricia leads with a `compliance_security` primary theme) lands at **111 leads** — a uniform 6% of the actual 1,850-lead non-Patricia population, per `aha-patterns.md`'s "~6% of each non-Patricia persona" rule. `aha-patterns.md` also states "~120"; that figure was an estimate against a rounded ~2,000 population. 111 is the precise computation and clears the Finding 5 threshold (≥80) with margin — it is intentional, not drift.

- **Locked CLI knobs.** `python -m ica.cli` supports `--seed` and `--db-path`. `data-world.md` §1 also lists `--total-leads`, `--start-date`, and `--end-date`; these are **locked in v1** — the generator is built for the 2,500-lead world (`channels.py` asserts it) over the fixed 2026-01-01 .. 2026-06-30 window (taxonomy constants). Passing one produces an explanatory error, not a silent no-op. `data-world.md` keeps the knobs as the aspirational interface; this entry is the v1 reality.

## Known doc inconsistencies

These are intentional pre-skew vs post-skew distinctions, not errors — `data-world.md` §5 describes the *baseline* outcome mix, and the aha-pattern skews deliberately move it.

- **Dataset closed-won rate.** §5 states a 6% baseline closed-won share; the generated dataset shows **~7.1%**. The Finding 1 skew lifts per-channel CW to `CHANNEL_BASELINE_CW_RATE`, whose volume-weighted average is ~7.1% — the figure `aha-patterns.md` Finding 3 itself uses for the lift calculation.
- **Disqualified / nurture shares.** §5's baseline mix is 25% disqualified / 35% nurture; the generated dataset shows **~29% / ~29%**. Finding 4 deliberately rewrites the 600 `linkedin_q2_broad_funnel` leads to a disqualify/ghost-heavy distribution (the "expensive non-ICP volume" the finding catches), which post-skew lifts dataset disqualified and lowers nurture.
