"""Pipeline orchestration — run the generator and write the SQLite database.

seed.py is the orchestrator, NOT a skew module. (The stale placeholder
called it "aha-pattern skew injectors" — corrected: the skews live in
outcomes.py, and F3's path synthesis in journeys.py. seed.py only
sequences the modules and persists the result.)

Sources: docs/data-world.md §1, §2 (schema, FK diagram §2.6); docs/
aha-patterns.md (skew-application order); src/ica/schema.py (DDL, open_db,
the insert_* helpers, PartialLead.to_lead); src/ica/taxonomy.py
(DEFAULT_SEED, TOTAL_LEADS_DEFAULT).

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (locked-doc / prior-decision, cited) or PROPOSED.

== Item 1 — module execution order ==
Runtime chain is four generator steps:
    personas -> channels -> journeys -> outcomes
content_library and copy_bank are NOT sequential steps — they are static
import banks (a content inventory and a snippet bank) that journeys.py
and outcomes.py import and call. seed.py never "runs" them. [DICTATED by
the module designs.] Concretely:
    leads = sample_personas(seed)
    assign_channels(leads, seed)
    touchpoints, form_submissions = build_journeys(leads, seed)
    outcomes, sales_notes = build_outcomes(leads, touchpoints, seed)
    rows = [lead.to_lead() for lead in leads]   # finalize PartialLead->Lead

== Item 2 — Finding 3 cross-reference comment ==
aha-patterns.md places F3's `apply_finding_3_journey_skew` in seed.py.
Per the approved journeys.py decision, F3 path-touchpoint synthesis moved
to journeys.py (single owner of the touchpoints table). seed.py will
carry a comment, where that skew would have lived, pointing to the actual
homes: F3 path selection + synthesis is journeys.py (`_select_f3_path_
lead_ids` + `build_journeys`); F3's CW lift composes in outcomes.py
(`_assign_won`). [DICTATED — the journeys.py F3-boundary decision.]
(Note: there is no function literally named `apply_f3_paths()` — F3 path
synthesis is inside `build_journeys`; the comment will name the real
call sites.)

== Item 3 — DB initialization ==
schema.py owns the DDL and `open_db()` (which runs CREATE TABLE and sets
PRAGMA foreign_keys=ON) [DICTATED — schema.py]. PROPOSED: the default DB
path is `data/ica.db` (the README's `make generate` target); a
DEFAULT_DB_PATH constant in seed.py. PROPOSED: each seed run wipes and
rebuilds — if the file exists it is removed first, then opened fresh —
so a re-run is clean and deterministic rather than colliding on primary
keys.

== Item 4 — determinism / seed propagation ==
A single integer `seed` (DEFAULT_SEED = 42) is passed to all four
generator calls. Each module independently constructs
`np.random.default_rng(seed)` (and personas.py also `Faker.seed(seed)`),
so each is a deterministic function of `seed` alone. [DICTATED — module
designs.] A deliberate property: because each module re-seeds, they do
not share one continuous RNG stream — editing one module does not ripple
the RNG into the next. The whole pipeline output is reproducible from the
one integer.

== Item 5 — output verification ==
test_aha_patterns.py and the other generator tests regenerate the dataset
fresh IN MEMORY (via the same sample_personas/.../build_outcomes calls);
they do NOT read the DB file. Since seed.py persists exactly that
generator output with the same DEFAULT_SEED, the `data/ica.db` contents
equal the test-verified dataset — the generator is the verified artifact,
seed.py is a faithful writer. No test currently reads the DB file itself;
a DB-reading smoke test (the empty test_generator.py) is a possible
follow-up, not required for v1. [PROPOSED — flag.]

== Item 6 — iteration loop ==
seed.py is a straight-through deterministic orchestrator — NO runtime
iteration. aha-patterns.md §14's "iterate until all five pass" is a
development workflow, and it was not needed this round: the stratified
(exact-count) assignment in journeys.py and outcomes.py hit every cell
target first-run, and test_aha_patterns.py passed first-run. If a future
tuning pass breaks a contract, the loop is: edit outcomes.py -> re-run
test_aha_patterns.py. [Noted per the brief.]

== Item 7 — cli.py boundary ==
PROPOSED: seed.py exposes one callable entry point —
`generate(seed=DEFAULT_SEED, db_path=DEFAULT_DB_PATH) -> dict[str, int]`
(runs the pipeline, writes the DB, returns row counts per table) — plus
an `if __name__ == "__main__"` shim. cli.py (next module) wraps
`generate()` with argparse and never reaches into seed.py internals.
FLAG: data-world.md §1 lists CLI knobs `--total-leads`, `--seed`,
`--start-date`, `--end-date`. Only `--seed` is cleanly supported today —
channels.py asserts the 2,500-lead world and the date window is taxonomy
constants, so `--total-leads` / `--start-date` / `--end-date` would need
generator changes. To resolve in the cli.py round; seed.py's v1
`generate()` takes `seed` and `db_path` only.

== Item 8 — other locked-doc items ==
- Insertion order respects the §2.6 FK diagram: leads first, then
  touchpoints, then form_submissions (FK -> touchpoints.touchpoint_id),
  then sales_notes and outcomes (FK -> leads). PRAGMA foreign_keys=ON is
  set by open_db, so order is enforced. [DICTATED §2.6.]
- seed.py finalizes every PartialLead via `to_lead()` before inserting;
  after journeys.py + outcomes.py all deferred fields are set, so
  to_lead() succeeds for all 2,500. [DICTATED — PartialLead contract.]
- Whether `data/ica.db` is committed to the repo or gitignored is a v1
  decision — likely gitignored (regenerable via `make generate`, the
  generator being the source of truth). PROPOSED — flag.
- seed.py prints a one-line per-table row-count summary on completion
  (useful for `make generate`). PROPOSED.

== What seed.py does NOT do ==
- No generation logic, no skews, no taxonomy values — it only sequences
  the generator modules and writes rows.
- No CLI parsing (cli.py).

Output: a populated `data/ica.db` with all five tables, plus a returned
row-count summary.
"""
