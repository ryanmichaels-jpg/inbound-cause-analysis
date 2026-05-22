"""noise.py — v1.5 realistic-noise layer for the synthetic generator.

PHASE 1 PLANNING HEADER — read first. Per the v1.5 cadence, this file
ships as the planning header for review; implementation lands in the
next commit only after sign-off. Companion module spurious.py (also
new) and the modifications to seed.py / cli.py / taxonomy.py + the
three test files listed in §5 are part of the same Phase 1 plan.

Goal (v1.5): instead of v1's pristine dataset, the generator produces
realistic-messy data that the pipeline must work through to recover
the five findings — addressing the "patterns were too easy" critique
without sacrificing reproducibility or the F1–F5 contract.

═════════════════════════════════════════════════════════════════════════
§1. CONTRACT (DICTATED — don't reopen)
═════════════════════════════════════════════════════════════════════════

D1. Default behavior is noisy. v1's pristine behavior is preserved
    behind `--clean` (equivalent to `--noise 0`).
D2. All five findings F1–F5 must still recover at default noise. That
    is the Phase 1 contract test (tests/test_aha_patterns.py).
D3. The pipeline MUST NOT surface the planted spurious patterns as
    findings (new tests/test_noise_discrimination.py).
D4. Re-extract resonance + regenerate the five artifacts from the
    noisy dataset — Phase 2's job. Phase 1 ships the noisy generator
    + the test contracts only; no LLM calls in Phase 1.
D5. README methodology section (Phase 3) documents the v1 → v1.5
    journey and the new agreement/stability numbers — which WILL be
    lower than v1's 94.1% / 99.1%, honestly so.

═════════════════════════════════════════════════════════════════════════
§2. NOISE MODEL — SIX DIMENSIONS (PROPOSED rates from the prompt; §8
    is the empirical tuning step that validates / refines each one
    against the F1–F5 contract before Phase 1 closes.)
═════════════════════════════════════════════════════════════════════════

  | dim              | proposed     | applies to                                  | rng stream    |
  | missingness      | 0.25 / 0.075 | qualitative text 25%, demographics 7.5%     | "missingness" |
  | text_noise       | 0.15         | per-token mutation prob on free-text        | "text"        |
  | duplicate_rate   | 0.08         | extra leads injected as near-duplicates     | "duplicate"   |
  | mis_attribution  | 0.12         | flip/null `created_via_channel`             | "misattr"     |
  | outlier_rate     | 0.015        | junk leads (competitors / internal / spam)  | "outlier"     |
  | spurious_count   | 3            | planted false correlations (see §4)         | "spurious"    |

§2.1 Missingness. Per-row, per-field Bernoulli mask. Qualitative
text fields (form_text, sales_notes_text, how_heard) at the 25%
rate; firmographic enrichment fields (industry, employee_count,
revenue_band) at the 7.5% rate. Identity fields (lead_id,
person_email, persona) are NEVER masked — the pipeline still needs
joinable identity. Null is represented as Python None, persisted
as SQL NULL.

§2.2 Text noise. Per-token mutation on free-text fields only.
Mutation ops, each with sub-probability among touched tokens:
  - character-swap (adjacent typos)                0.40
  - character-drop                                 0.20
  - common-word abbreviation (e.g. "you" → "u")    0.20
  - punctuation strip                              0.10
  - case mangling (random ALLCAPS / lowercase)     0.10
Rate is the per-token probability of being touched; one op is
sampled per touched token. Buyer-language SIGNAL (the resonance
content) is preserved on average — the resonance layer must work
harder, but the themes remain extractable.

§2.3 Duplicate rate. Inject N = round(0.08 × total_leads) extra
leads as near-duplicates of existing ones: same person, same
company, but new lead_id, different email format
(first.last vs flast vs f.last), slight first-name variant from
Faker's pool, and a re-drawn created_at. They preserve persona /
channel / journey ratios — F1–F5 should be robust to duplicate
dilution. (See §9.7 on identity-pair uniqueness.)

§2.4 Mis-attribution. 12% of leads have `created_via_channel`
either flipped (60% of hits) to another channel sampled from the
overall channel mix, or nulled (40%) — set to a new sentinel
`Channel.UNKNOWN` to mirror real CRMs' "unknown source" tail. F1
is the most exposed finding (§9.1); §8 validates the rate.

§2.5 Outlier rate. ~37 junk leads (1.5% of 2,500) injected with
telltale signals: competitor email domains, internal-team emails,
garbage form-text ("asdfasdf"). They sit OUTSIDE the persona
schema and are tagged with a new `Persona.OUTLIER` value — see
§9.2 for the persona-test implication.

§2.6 Spurious patterns. Three planted false correlations — §4.

═════════════════════════════════════════════════════════════════════════
§3. RNG ARCHITECTURE
═════════════════════════════════════════════════════════════════════════

One root seed (DEFAULT_SEED) drives a NumPy SeedSequence. Six
independent sub-streams spawned via `ss.spawn(6)`, one per noise
dimension. Effect: tuning `text_noise` re-rolls ONLY the text stream;
channel mis-attribution, duplicate injection, etc. stay byte-stable
across runs. Critical for debugging — when a contract test breaks
under a noise tweak, the delta is local.

Sub-streams: "missingness", "text", "duplicate", "misattr",
"outlier", "spurious" — keyed by name (not order) for readability.
Order-stable: a stable name → SeedSequence-spawn-index mapping is
fixed in noise.py so a future stream addition doesn't reshuffle
existing ones.

═════════════════════════════════════════════════════════════════════════
§4. SPURIOUS-PATTERN ENGINEERING — spurious.py
═════════════════════════════════════════════════════════════════════════

Three planted false patterns, each with extreme rate × small N —
the "tempting wrong finding" shape. They surface in naive
aggregations; the pipeline's findings layer (which enforces an N
threshold — see §4 discriminator) must NOT surface them.

  S1. "Tuesday signups close at 80%"
      Pick 5 leads created on Tuesdays; flip outcomes to closed_won.
      Naive by-day-of-week aggregation: 80% / Tuesday vs ~7%
      baseline. Real N = 5.

  S2. "Leads from .ai domains close at 75%"
      8 leads with .ai-suffixed company domains; flip outcomes.
      Naive by-tld aggregation: 75% / .ai vs ~7% baseline. N = 8.

  S3. "Leads with 'urgent' in form-text close at 90%"
      10 leads where form_text contains 'urgent'; flip outcomes.
      Naive keyword-correlation: 90% / urgent vs ~7% baseline.
      N = 10.

Public API (spurious.py):
  inject_spurious_patterns(leads, outcomes, *, rng)
      -> tuple[outcomes', manifest]
manifest is a list[dict] of {description, planted_lead_ids,
surface_signal}, also persisted to data/spurious_manifest.json for
the discrimination test (§6.2) to consult.

Discriminator (PROPOSED — validate in §8): the findings layer's
N-threshold floor is 30. Any finding whose cohort N is below that
is discarded before emission. All three S-patterns sit below; all
five F-patterns sit above (smallest is F3 at ~50). The floor is a
new constant in taxonomy.py: `FINDING_N_FLOOR = 30`.

═════════════════════════════════════════════════════════════════════════
§5. MODULE LAYOUT — NEW / MODIFIED IN PHASE 1
═════════════════════════════════════════════════════════════════════════

NEW
  src/ica/generator/noise.py    — this file. Public API:
                                    apply_noise(leads, touchpoints,
                                       form_submissions, sales_notes,
                                       outcomes, *, profile, seed)
                                  Returns mutated lists + the
                                  spurious-pattern manifest.
  src/ica/generator/spurious.py — §4 implementation.

MODIFIED
  src/ica/generator/seed.py     — call apply_noise() after the
                                  existing clean generation step,
                                  before persist. Add --noise (float,
                                  default 1.0) and --clean (sugar for
                                  --noise 0) flags.
  src/ica/cli.py                — surface --noise / --clean.
  src/ica/taxonomy.py           — add NoiseProfile dataclass (the 6
                                  rates), CLEAN / REALISTIC /
                                  STRESS_2X / STRESS_4X named
                                  profiles. Add Channel.UNKNOWN. Add
                                  Persona.OUTLIER. Add
                                  FINDING_N_FLOOR = 30.
  Makefile                      — `make generate NOISE=clean` etc.
                                  (see §7).
  tests/test_aha_patterns.py    — see §6.1.
  .gitignore                    — add `data/spurious_manifest.json`.

NEW TESTS
  tests/test_noise_discrimination.py — §6.2
  tests/test_noise_tolerance.py      — §6.3

═════════════════════════════════════════════════════════════════════════
§6. TEST ARCHITECTURE
═════════════════════════════════════════════════════════════════════════

§6.1 test_aha_patterns.py (modify). The existing five contract
assertions must still pass at default noise. Headline thresholds
will need to loosen — v1's pristine margins are tight. Proposed
loosened thresholds (validated empirically in §8):
    F1 channel-quality lift ratio:    > 9.0  →  > 5.0
    F2 persona-message lift:          > 8.0  →  > 5.0
    F3 journey-path lift:             > 6.0  →  > 3.5
    F4 ICP-mismatch share:            > 0.75 →  > 0.60
    F5 secondary-resonance lift:      > 5.0  →  > 3.0
Each loosening is documented inline with the v1 → v1.5 delta and
the under-noise measured value at default. Tests still pin to
specific numerics — no "approximately"-style assertions that hide
regressions.

§6.2 test_noise_discrimination.py (new). Loads
data/spurious_manifest.json (written by the most recent generation
run), runs the findings layer over the noisy DB, asserts:
    (a) No F1–F5 finding output overlaps any planted lead_id set.
    (b) Every F1–F5 finding cohort N > FINDING_N_FLOOR (= 30).
    (c) A naive baseline aggregation DOES surface each S-pattern —
        so the test fails informatively if spurious injection
        silently breaks (rather than passing vacuously).

§6.3 test_noise_tolerance.py (new). Parametrized over noise
multiplier {1.0, 2.0, 4.0}, regenerates the dataset (fast —
generation is ~3s), runs the findings layer, asserts:
    1.0× → all 5 findings recover (the §6.1 contract)
    2.0× → ≥ 3 findings recover
    4.0× → ≥ 1 finding recovers
The 2× / 4× thresholds define the degradation curve the README
publishes in Phase 3. The test_ scope is Phase 1; Phase 3 only
re-runs and tabulates.

§6.4 No change required to test_personas.py or test_channels.py —
both load pre-noise outputs (sample_personas() /
assign_channels(sample_personas())). noise.py applies AFTER the
channels.py / journeys.py layers, so the persona / channel unit
suites continue testing exactly what they tested before. Verified
in §9.3.

═════════════════════════════════════════════════════════════════════════
§7. CLI / MAKEFILE SURFACE (PROPOSED — the prompt's
    `NOISE=stress NOISE_MULT=2` phrasing was casual; unified here.)
═════════════════════════════════════════════════════════════════════════

  make generate                   # default — REALISTIC profile (1×)
  make generate NOISE=clean       # v1 pristine (0×)
  make generate NOISE=2           # STRESS_2X (rates × 2)
  make generate NOISE=4           # STRESS_4X (rates × 4)

argparse-level: `--noise FLOAT` (default 1.0) and `--clean` (sugar
for `--noise 0`). `--clean` and a non-default `--noise` are
mutually exclusive — argparse raises.

═════════════════════════════════════════════════════════════════════════
§8. DEFAULT-TUNING — empirical pre-finalization step
═════════════════════════════════════════════════════════════════════════

The §2 defaults are PROPOSED; before Phase 1 closes, generate at
those rates and run the §6.1 contract. The most exposed findings
are F1 (mis-attribution-sensitive) and F3 (cohort ~50 — combined
duplicate + mis-attribution erosion squeezes it from both sides,
§9.1).

If a finding falls below its loosened threshold:
  Option A — re-tune the dominant noise dim down (e.g.
             mis_attribution 0.12 → 0.10).
  Option B — boost the at-risk cohort's generated size on the
             data-world side so the noise-eroded version clears
             the floor.
  Option C — loosen the §6.1 threshold further, documenting the
             v1 → v1.5 delta honestly.
Preference: A > B > C. Tuning happens inside Phase 1 — Phase 1
ships defaults that pass.

═════════════════════════════════════════════════════════════════════════
§9. RISKS / OPEN QUESTIONS / SURFACED ASSUMPTIONS
═════════════════════════════════════════════════════════════════════════

§9.1 F3 cohort-size risk. F3's cohort is the smallest (~50).
Combined duplicate (8%) + mis-attribution (12%) erosion can drop
it to ~40 clean-signature leads; the lift ratio's denominator
(dataset-wide close rate) also goes UP under outlier + spurious
injection — squeezing F3 from both sides. §8 must verify before
Phase 1 closes; if it falls below the loosened > 3.5 floor,
Option B (boost the F3 cohort generated size) is the cleanest fix.

§9.2 Outlier leads break Persona enum closure. Outliers don't fit
Maya / David / Patricia / Carlos — they need a label. Adding
`Persona.OUTLIER` to taxonomy.py is a one-line addition but
cascades into test_personas.test_persona_population_share (which
iterates Persona). Resolution: outliers carry persona =
Persona.OUTLIER, and the existing persona-share tests scope to
`[p for p in Persona if p is not Persona.OUTLIER]`. Documented at
the test-edit site.

§9.3 test_personas / test_channels pre-noise scope. Both currently
load sample_personas() / assign_channels(sample_personas()) — the
pre-noise outputs. noise.py applies AFTER channels.py /
journeys.py, so those unit tests test what they already tested.
No change needed.

§9.4 Dashboard robustness. The dashboard reads data/ica.db (noisy
by default). Two implications: (a) headline metrics displayed will
shift — most visibly resonance agreement / stability (Phase 2's
job to refresh). (b) Is dashboard logic robust to nulls /
Channel.UNKNOWN? Spot-check in Phase 3; if a widget crashes, fix
in Phase 3.

§9.5 Phase 2 numerics. The 94.1% agreement / 99.1% stability
quoted in README + one-pager were v1 measurements. Phase 2
re-extracts on noisy data; both numbers will drop. Honest
documentation in Phase 3. SURFACED ASSUMPTION: agreement plausibly
lands 80–88%, stability 85–93% — but those are guesses; Phase 2
measures.

§9.6 Spurious-pattern manifest persistence. Written to
data/spurious_manifest.json — needs a new line in .gitignore
(currently only `data/*.db|sqlite|csv|parquet` are listed). Add
`data/spurious_manifest.json` (or broaden to `data/*.json`).
Discrimination test reads it; without it the test is vacuous.

§9.7 Duplicate semantics. Near-duplicates carry new lead_ids
(uniqueness preserved, §6.4). But identity-pair joins on
(person_email, company_domain) are no longer unique. seed.py and
the findings layer do not currently assume that uniqueness;
re-verify at implementation time and flag if anything downstream
breaks.

═════════════════════════════════════════════════════════════════════════
§10. OUT OF SCOPE FOR PHASE 1
═════════════════════════════════════════════════════════════════════════

- LLM re-extraction on the noisy dataset (Phase 2).
- Regeneration of the five GTM artifacts (Phase 2).
- README methodology update + the v1 → v1.5 journey writeup
  (Phase 3).
- One-pager numeric refresh (Phase 3, if Phase 2 results are
  material).
- Dashboard null / Channel.UNKNOWN handling (Phase 3, only if §9.4
  spot-check shows a crash).

═════════════════════════════════════════════════════════════════════════
END PHASE 1 PLANNING HEADER — paused for review per the v1.5 stop
points. Implementation lands in the next commit after sign-off.
"""
