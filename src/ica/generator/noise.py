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

Three planted false patterns, each engineered as a "tempting wrong
finding": small N + extreme rate + a slice a real GTM team would
casually look at. Each has a `correlation_shape` — the naive
aggregation that surfaces it — so the §6.2(c) discrimination test
can confirm the pattern is genuinely findable before asserting the
pipeline rejects it. Plant mechanics differ per pattern because
Faker doesn't naturally generate .ai domains or 'urgent' form-text
at the rates we need.

  S1. Tuesday signups close at 80%.
      Shape: marginal close-rate by day-of-week.
      Plant: select 5 leads from the natural Tuesday cohort
      (~357 leads), scattered across personas, mid-band
      ICP-fit-score (50-70 so firmographics don't carry the
      signal); flip outcomes to closed_won.
      Naive cell: Tue 80% / other days ~7%. N = 5.
      Real-world echo: "concentrate campaign launches on Tuesday"
      — a routine marketing-reporting slice.

  S2. Leads from .ai domains close at 75%.
      Shape: marginal close-rate by company-domain TLD.
      Plant: select 8 leads, scatter personas, mid-band fit;
      OVERWRITE company_domain to a `.ai` TLD (preserving the
      person_email local-part so personas.py's email-derivation
      invariant holds); flip outcomes.
      Naive cell: .ai 75% / others ~7%. N = 8.
      Real-world echo: ".ai = AI-native = ICP-fit AI-tooling
      buyer" — niche TLDs genuinely correlate with industry in
      real data.

  S3. Leads with 'urgent' in form-text close at 90%.
      Shape: marginal close-rate by keyword-presence in form_text.
      Plant: select 10 leads, scatter personas, mid-band fit;
      APPEND the sentence "We need this resolved urgently — when
      can we start?" to the END of an otherwise-normal form_text
      (the rest of the buyer-language signal is preserved); flip
      outcomes.
      Naive cell: 'urgent' present 90% / absent ~7%. N = 10.
      Real-world echo: high-intent language → conversion is a
      real CRM correlation; the text angle adjoins the resonance
      layer's logic, making the spurious look like a "discovered
      theme."

Scattering across personas (rather than concentrating in one) and
mid-band ICP-fit (rather than top-band) deliberately removes the
obvious confounds — the only thing differentiating the planted
cohort from the rest is the spurious dimension itself. That's
what makes each one a clean "tempting wrong finding."

ORDERING: spurious-pattern injection runs as the LAST step of
noise application — so S3's text injection survives intact rather
than being chewed by `text_noise` (§2.2) that ran earlier.

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

§9.4 Dashboard robustness — Phase 1 spot-check.
At the end of Phase 1 (after default-noise lands and §6 tests
pass), run `make dashboard` locally against the noisy DB and
click each tab. What to look for:
  - Findings tab — F1's channel-quality chart now includes a
    Channel.UNKNOWN cohort (§2.4). Does it render or crash?
  - Persona × Theme tab — Persona dropdown now includes OUTLIER
    (§2.5). Outlier slice has N ~ 37; does the explorer render
    coherent rows or div-by-zero on a percentage calc? Null
    secondary themes already handled in v1.
  - Resonance tab — some primary themes are now null (from
    missingness on form_text, §2.1). Does the count widget
    filter or crash?
  - Actions tab — reads pre-generated artifacts (still v1 in
    Phase 1; Phase 2 regenerates). No null exposure here.
Trigger thresholds:
  - PHASE 1 FIX (blocking): any tab raises a Python exception.
    The Phase 1 contract is "default is realistic-noisy AND the
    pipeline handles it" — a crashing dashboard means the system
    isn't actually robust, so a crash blocks Phase 1 close.
  - PHASE 3 DEFER (cosmetic): everything renders without
    exception but looks rough (UNKNOWN as a stray unlabelled
    bar, OUTLIER persona unlabeled, etc.). Document and defer.

Headline metrics displayed (resonance agreement / stability) will
also shift under noise — Phase 2's job to refresh.

§9.5 Phase 2 numerics. The 94.1% agreement / 99.1% stability
quoted in README + one-pager were v1 measurements. Phase 2
re-extracts on noisy data; both numbers will drop. Honest
documentation in Phase 3. SURFACED ASSUMPTION: agreement plausibly
lands 80–88%, stability 85–93% — but those are guesses; Phase 2
measures.

§9.6 Spurious-pattern manifest — definitions vs runtime record.
Two artifacts, separate concerns:
  - DEFINITIONS (which DOW, which TLD, which keyword, target N,
    target rate) live in spurious.py as committed code —
    reviewable, version-controlled, testable.
  - RUNTIME RECORD (which specific lead_ids got planted with
    which pattern in THIS generation run) is written to
    data/spurious_manifest.json at generation time. Regenerable
    from seed (deterministic), so gitignored — same logic as
    data/ica.db. Needs a new .gitignore line:
    `data/spurious_manifest.json` (or broaden to `data/*.json`).
The §6.2 discrimination test reads data/spurious_manifest.json
to learn (a) which lead_ids to look for in F1-F5 outputs (assert
non-overlap) and (c) which planted slices to naive-aggregate
(assert findable). Without the runtime record the test would have
to re-plant the patterns itself, doubling the surface area for
drift.

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
- Dashboard cosmetic polish for Channel.UNKNOWN / OUTLIER
  labelling (Phase 3 — but crashes block Phase 1 close, see §9.4).

═════════════════════════════════════════════════════════════════════════
§11. PHASE 2 PRE-AGREED GATE — LLM re-extraction degradation rule
═════════════════════════════════════════════════════════════════════════

Documented now so the Phase 2 methodology numbers can't get
rationalized after the fact. Mirrors the v1 → v2 rep_efficiency
decision rule from commit 05b4ad1.

When Phase 2 measures overall extraction agreement on the noisy
dataset (the equivalent of v1's 94.1%):
  - agreement > 80%    → accept; proceed normally. Methodology
                         section quotes the new number plainly.
  - agreement 75–80%   → proceed but flag explicitly in the
                         methodology section. The README earns
                         the "honest degradation under noise"
                         frame rather than burying it.
  - agreement < 75%    → pause and surface. Two diagnoses:
                           (i)  noise overwhelms signal — re-tune
                                in Phase 1 territory: dial back
                                text_noise or missingness on text;
                           (ii) extraction prompt needs hardening
                                — v2 → v3 disambiguation iteration.
                         One shot per remediation path, no spiral.

The 75 / 80 thresholds are deliberate — v1 ran 94.1% on pristine
text; the §9.5 surfaced range (80–88%) brackets the > 80%
"accept" zone. 75–80% is the "honest but still useful" middle.
< 75% is where the LLM stops being a credible signal extractor
and the spend doesn't earn the dashboard's claim.

═════════════════════════════════════════════════════════════════════════
END PHASE 1 PLANNING HEADER. Implementation follows.

═════════════════════════════════════════════════════════════════════════
IMPLEMENTATION NOTES — deviations from the planning header

§2.4 / §2.5 / §5: the planning header proposed adding `Channel.UNKNOWN`
and `Persona.OUTLIER` as new enum members. Implementation chose a less
invasive path: `Lead.created_via_channel: Channel | None` (nullable) for
the mis-attribution-null tail, and a new `Lead.is_outlier: bool` flag
for outlier leads. The enum-expansion approach would have rippled into
~20 parametrized tests in test_taxonomy.py with dict-key accesses
(PERSONA_INDUSTRY_WEIGHTS[OUTLIER], CHANNEL_TARGET_VOLUME[UNKNOWN], …)
that have no sensible zero/empty value. The schema-side approach is
strictly more localized — two dataclass field changes + two DDL
changes — for the same semantic outcome (mis-attributed leads are
excluded from channel cohorts as None is excluded just as UNKNOWN
would have been; outliers are taggable via the bool flag without an
enum tag). Surfaced and documented in the Commit 1 message.

§2.1: planning header described missingness as a two-rate dim (0.25 on
qualitative text + 0.075 on demographics). Phase 1 implements text
missingness only — demographic missingness would require either DDL
nullability on company_industry / employee_count / revenue_band (more
invasive) or sentinel values ("Unknown" / 0) that look broken in the
dashboard. NoiseProfile.missingness is a single rate (text only) in
Phase 1; demographic missingness is a Phase 2+ polish item.
═════════════════════════════════════════════════════════════════════════
"""

import re
import string
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta

import numpy as np

from ica.generator.spurious import inject_spurious_patterns
from ica.schema import FormSubmission, Lead, OutcomeRow, SalesNote
from ica.taxonomy import (
    CHANNEL_TARGET_VOLUME,
    DEFAULT_SEED,
    REALISTIC,
    Channel,
    NoiseProfile,
    Outcome,
    Persona,
    Seniority,
    Theme,
)

__all__ = ["apply_noise"]

# Fixed namespace so noise-generated lead_ids are reproducible across runs.
_NOISE_LEAD_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "ica.v1_5_noise")

# Order-stable sub-stream names — appending here doesn't reshuffle existing
# streams (see §3 of the planning header).
_NOISE_STREAMS: tuple[str, ...] = (
    "missingness",
    "text",
    "duplicate",
    "misattr",
    "outlier",
    "spurious",
)


def _spawn_streams(seed: int) -> dict[str, np.random.Generator]:
    """Six independent RNGs, one per noise dimension. Tuning one dim does
    NOT re-roll the others — same root seed, distinct child SeedSequences."""
    ss = np.random.SeedSequence(seed)
    children = ss.spawn(len(_NOISE_STREAMS))
    return {
        name: np.random.default_rng(s)
        for name, s in zip(_NOISE_STREAMS, children, strict=True)
    }


# -----------------------------------------------------------------------------
# §2.1 Missingness — null out qualitative free-text fields (text only in
# Phase 1; see deviation note above).
# -----------------------------------------------------------------------------


def _apply_missingness(
    form_submissions: list[FormSubmission],
    sales_notes: list[SalesNote],
    rate: float,
    rng: np.random.Generator,
) -> None:
    """Per-row Bernoulli null on free-text fields. Mutates in place.

    We use empty string "" as the null sentinel rather than changing the
    DDL: the resonance layer reads these fields and treats empty as
    no-signal, which is the meaningful realism here."""
    if rate <= 0:
        return
    fs_mask = rng.random(len(form_submissions)) < rate
    for fs, drop in zip(form_submissions, fs_mask, strict=True):
        if drop:
            fs.free_text_answer = ""
    sn_mask = rng.random(len(sales_notes)) < rate
    for sn, drop in zip(sales_notes, sn_mask, strict=True):
        if drop:
            sn.text = ""


# -----------------------------------------------------------------------------
# §2.2 Text noise — per-token mutation on free-text fields.
# -----------------------------------------------------------------------------

# Common-word abbreviation pool. Lookup is lower-case; replacement preserves
# nothing of the original case (intentional — SMS-style chat noise).
_ABBREVIATIONS: dict[str, str] = {
    "you": "u",
    "your": "ur",
    "you're": "ur",
    "are": "r",
    "for": "4",
    "to": "2",
    "too": "2",
    "be": "b",
    "before": "b4",
    "great": "gr8",
    "later": "l8r",
    "people": "ppl",
    "thanks": "thx",
    "with": "w/",
    "without": "w/o",
    "because": "bc",
    "really": "rly",
    "probably": "prob",
    "okay": "ok",
    "though": "tho",
}
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
# Per-op probabilities, normalized to sum=1. Order matches §2.2 of the header.
_TEXT_OPS = ("swap", "drop", "abbrev", "strip", "case")
_TEXT_OP_WEIGHTS = np.array([0.40, 0.20, 0.20, 0.10, 0.10])


def _mutate_token(token: str, rng: np.random.Generator) -> str:
    """Apply one of the five §2.2 ops to a single token."""
    op = _TEXT_OPS[int(rng.choice(len(_TEXT_OPS), p=_TEXT_OP_WEIGHTS))]
    if op == "swap" and len(token) >= 2:
        i = int(rng.integers(0, len(token) - 1))
        return token[:i] + token[i + 1] + token[i] + token[i + 2 :]
    if op == "drop" and len(token) >= 2:
        i = int(rng.integers(0, len(token)))
        return token[:i] + token[i + 1 :]
    if op == "abbrev":
        return _ABBREVIATIONS.get(token.lower(), token)
    if op == "strip":
        return _PUNCT_RE.sub("", token)
    if op == "case":
        return token.upper() if rng.random() < 0.5 else token.lower()
    return token  # ops that no-op on too-short tokens


def _perturb_text(text: str, rate: float, rng: np.random.Generator) -> str:
    """Per-token mutation with probability `rate` per token."""
    if not text or rate <= 0:
        return text
    tokens = text.split(" ")
    touched = rng.random(len(tokens)) < rate
    return " ".join(
        _mutate_token(tok, rng) if hit else tok
        for tok, hit in zip(tokens, touched, strict=True)
    )


def _apply_text_noise(
    form_submissions: list[FormSubmission],
    sales_notes: list[SalesNote],
    rate: float,
    rng: np.random.Generator,
) -> None:
    if rate <= 0:
        return
    for fs in form_submissions:
        fs.free_text_answer = _perturb_text(fs.free_text_answer, rate, rng)
    for sn in sales_notes:
        sn.text = _perturb_text(sn.text, rate, rng)


# -----------------------------------------------------------------------------
# §2.4 Mis-attribution — flip / null the channel attribution.
# -----------------------------------------------------------------------------


def _channel_mix_excluding(current: Channel | None) -> tuple[list[Channel], np.ndarray]:
    """Channel choices + normalized probability vector for sampling a
    replacement channel, excluding `current`."""
    items = [(c, v) for c, v in CHANNEL_TARGET_VOLUME.items() if c != current]
    channels = [c for c, _ in items]
    weights = np.array([v for _, v in items], dtype=float)
    weights /= weights.sum()
    return channels, weights


def _apply_mis_attribution(
    leads: list[Lead], rate: float, rng: np.random.Generator
) -> None:
    """For each lead, with probability `rate`: 40% null the channel
    (and clear the campaign), 60% flip to another channel drawn from the
    overall mix. first_touch_utm_campaign is cleared in both cases — when
    attribution is wrong, the campaign signal is wrong too."""
    if rate <= 0:
        return
    hits = rng.random(len(leads)) < rate
    flip_rolls = rng.random(len(leads))
    for lead, hit, roll in zip(leads, hits, flip_rolls, strict=True):
        if not hit:
            continue
        if roll < 0.40:
            # null tail
            lead.created_via_channel = None
            lead.first_touch_utm_campaign = None
        else:
            # flip — sample replacement excluding current
            channels, weights = _channel_mix_excluding(lead.created_via_channel)
            idx = int(rng.choice(len(channels), p=weights))
            lead.created_via_channel = channels[idx]
            lead.first_touch_utm_campaign = None


# -----------------------------------------------------------------------------
# §2.3 Duplicates — inject near-duplicate leads.
# -----------------------------------------------------------------------------

_EMAIL_FORMAT_VARIANTS = ("flast", "f.last", "f_last", "lastf", "first_last", "last.first")


def _alt_email(first: str, last: str, domain: str, variant: str) -> str:
    """Return a near-duplicate email format. Helpers strip non-alnum the
    way personas._person_email does."""
    first_slug = re.sub(r"[^a-z0-9]", "", first.lower())
    last_slug = re.sub(r"[^a-z0-9]", "", last.lower())
    if variant == "flast":
        local = first_slug[:1] + last_slug
    elif variant == "f.last":
        local = f"{first_slug[:1]}.{last_slug}"
    elif variant == "f_last":
        local = f"{first_slug[:1]}_{last_slug}"
    elif variant == "lastf":
        local = last_slug + first_slug[:1]
    elif variant == "first_last":
        local = f"{first_slug}_{last_slug}"
    elif variant == "last.first":
        local = f"{last_slug}.{first_slug}"
    else:
        local = f"{first_slug}.{last_slug}"
    return f"{local}@{domain}"


def _inject_duplicates(
    leads: list[Lead],
    outcomes: list[OutcomeRow],
    rate: float,
    seed: int,
    rng: np.random.Generator,
) -> None:
    """Add round(rate * base_count) duplicates. Each carries a new lead_id
    + outcome row, varied email format, slightly perturbed created_at, but
    inherits everything else (channel, theme, outcome) from a parent.

    Inheriting the parent's outcome preserves F1-F5 close-rate ratios
    under duplicate dilution — duplicates don't shift the win-rate
    aggregates, only the cohort sizes."""
    base_count = len(leads)
    n_dup = round(rate * base_count)
    if n_dup <= 0:
        return
    outcome_by_lead = {o.lead_id: o for o in outcomes}
    parent_indices = rng.integers(0, base_count, size=n_dup)
    variant_indices = rng.integers(0, len(_EMAIL_FORMAT_VARIANTS), size=n_dup)
    # Created-at jitter: -7..+7 days from the parent (seconds-resolution).
    jitter_seconds = rng.integers(-7 * 86400, 7 * 86400 + 1, size=n_dup)

    for i in range(n_dup):
        parent = leads[parent_indices[i]]
        variant = _EMAIL_FORMAT_VARIANTS[variant_indices[i]]
        new_lead_id = str(uuid.uuid5(_NOISE_LEAD_NAMESPACE, f"dup:{seed}:{i}"))
        new_email = _alt_email(parent.person_first_name, parent.person_last_name,
                                parent.company_domain, variant)
        new_created_at = parent.created_at + timedelta(seconds=int(jitter_seconds[i]))
        new_lead = replace(parent, lead_id=new_lead_id, person_email=new_email,
                            created_at=new_created_at)
        leads.append(new_lead)
        parent_outcome = outcome_by_lead.get(parent.lead_id)
        if parent_outcome is not None:
            new_outcome = replace(parent_outcome, lead_id=new_lead_id)
            outcomes.append(new_outcome)


# -----------------------------------------------------------------------------
# §2.5 Outliers — junk leads (competitors / internal / spam).
# -----------------------------------------------------------------------------

_COMPETITOR_DOMAINS = (
    "salesforce.com",
    "hubspot.com",
    "marketo.com",
    "gong.io",
    "outreach.io",
    "clari.com",
)
_INTERNAL_DOMAINS = ("ica-corp.com", "ica-test.local")
_JUNK_FIRST_NAMES = ("Test", "Asdf", "Qwerty", "Noreply", "Admin", "Spam")
_JUNK_LAST_NAMES = ("User", "Bot", "Tester", "Account", "Sample", "Dummy")
_JUNK_TITLES = (
    "Competitive Intelligence Lead",
    "Account Executive (Competitor)",
    "Researcher",
    "QA",
    "Test Account",
    "Student",
)
_JUNK_INDUSTRIES = ("SaaS", "Other", "Consumer")
_THEME_POOL = list(Theme)
_PERSONA_POOL = (Persona.MAYA, Persona.DAVID, Persona.PATRICIA, Persona.CARLOS)
_CHANNEL_POOL = tuple(CHANNEL_TARGET_VOLUME.keys())
_SENIORITY_POOL = tuple(Seniority)


def _inject_outliers(
    leads: list[Lead],
    outcomes: list[OutcomeRow],
    rate: float,
    seed: int,
    rng: np.random.Generator,
) -> None:
    """Add round(rate * base_count) junk leads. Each carries is_outlier=True,
    a competitor or internal email domain, a low icp_fit_score, and a
    DISQUALIFIED outcome. No touchpoints / form_submissions are emitted in
    Phase 1 — outliers exist in the leads + outcomes tables and the
    pipeline must handle them. The discrimination test (Commit 2) reads
    the manifest to find them; an outlier-aware downstream LLM step is
    a Phase 2 concern."""
    base_count = len(leads)
    n = round(rate * base_count)
    if n <= 0:
        return
    # Sample arrays (faster than per-row .integers() calls).
    is_competitor = rng.random(n) < 0.6  # 60% competitor, 40% internal
    first_idx = rng.integers(0, len(_JUNK_FIRST_NAMES), size=n)
    last_idx = rng.integers(0, len(_JUNK_LAST_NAMES), size=n)
    title_idx = rng.integers(0, len(_JUNK_TITLES), size=n)
    industry_idx = rng.integers(0, len(_JUNK_INDUSTRIES), size=n)
    persona_idx = rng.integers(0, len(_PERSONA_POOL), size=n)
    channel_idx = rng.integers(0, len(_CHANNEL_POOL), size=n)
    seniority_idx = rng.integers(0, len(_SENIORITY_POOL), size=n)
    theme_idx = rng.integers(0, len(_THEME_POOL), size=n)
    competitor_d_idx = rng.integers(0, len(_COMPETITOR_DOMAINS), size=n)
    internal_d_idx = rng.integers(0, len(_INTERNAL_DOMAINS), size=n)
    icp_scores = rng.integers(5, 26, size=n)  # 5-25 inclusive
    employee_counts = rng.integers(10, 5001, size=n)

    # Anchor outlier created_at within the base time window — pull from
    # the existing leads' min/max so they sit in the same envelope.
    times = [lead.created_at for lead in leads]
    t_min, t_max = min(times), max(times)
    span = (t_max - t_min).total_seconds()
    time_offsets = rng.random(n) * span

    for i in range(n):
        domain = (_COMPETITOR_DOMAINS[competitor_d_idx[i]] if is_competitor[i]
                  else _INTERNAL_DOMAINS[internal_d_idx[i]])
        first = _JUNK_FIRST_NAMES[first_idx[i]]
        last = _JUNK_LAST_NAMES[last_idx[i]]
        company_name = domain.split(".")[0].title()
        new_lead_id = str(uuid.uuid5(_NOISE_LEAD_NAMESPACE, f"outlier:{seed}:{i}"))
        new_lead = Lead(
            lead_id=new_lead_id,
            created_at=t_min + timedelta(seconds=float(time_offsets[i])),
            person_first_name=first,
            person_last_name=last,
            person_email=f"{first.lower()}.{last.lower()}@{domain}",
            person_title=_JUNK_TITLES[title_idx[i]],
            person_seniority=_SENIORITY_POOL[seniority_idx[i]],
            company_name=company_name,
            company_domain=domain,
            company_industry=_JUNK_INDUSTRIES[industry_idx[i]],
            company_employee_count=int(employee_counts[i]),
            company_revenue_band="<$10M",
            persona=_PERSONA_POOL[persona_idx[i]],
            icp_fit_score=int(icp_scores[i]),
            created_via_channel=_CHANNEL_POOL[channel_idx[i]],
            seed_label_theme_primary=_THEME_POOL[theme_idx[i]],
            seed_label_theme_secondary=None,
            first_touch_utm_campaign=None,
            is_outlier=True,
        )
        leads.append(new_lead)
        # Disqualified outcome — student_or_competitor matches the
        # taxonomy.DISQUALIFIED_SUB_REASONS tail real CRMs use for junk.
        outcomes.append(OutcomeRow(
            lead_id=new_lead_id,
            outcome=Outcome.DISQUALIFIED,
            resolved_at=new_lead.created_at + timedelta(days=1),
            days_to_outcome=1,
            sub_reason="student_or_competitor",
            pipeline_value_usd=None,
        ))


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def apply_noise(
    leads: Sequence[Lead],
    touchpoints,
    form_submissions: Sequence[FormSubmission],
    sales_notes: Sequence[SalesNote],
    outcomes: Sequence[OutcomeRow],
    *,
    profile: NoiseProfile = REALISTIC,
    seed: int = DEFAULT_SEED,
) -> tuple[list[Lead], list, list[FormSubmission], list[SalesNote], list[OutcomeRow], dict]:
    """Apply the v1.5 noise profile to the pristine v1 dataset.

    Returns mutated copies of all five table-equivalents plus the
    spurious-pattern manifest. Phase 1 manifest is always empty (spurious
    injection lands in Commit 2). The function does not mutate its
    arguments — caller-owned copies are returned.

    Order of application (per §3 of the planning header):
        missingness → text_noise → mis_attribution → duplicate → outlier
        → spurious (Commit 2)
    Duplicates inherit already-noisy parent data (CRM-realistic). Outliers
    carry their own pre-degraded payload — noise is not re-applied to
    them.
    """
    streams = _spawn_streams(seed)

    # Defensive copies — callers can keep their pristine lists if they want.
    leads_l = list(leads)
    touchpoints_l = list(touchpoints)
    form_submissions_l = list(form_submissions)
    sales_notes_l = list(sales_notes)
    outcomes_l = list(outcomes)

    # §2.1 missingness — text fields only.
    _apply_missingness(form_submissions_l, sales_notes_l, profile.missingness,
                       streams["missingness"])

    # §2.2 text noise — runs after missingness so wasted ops are minimal
    # (empty strings short-circuit in _perturb_text).
    _apply_text_noise(form_submissions_l, sales_notes_l, profile.text_noise,
                      streams["text"])

    # §2.4 mis-attribution — flip/null created_via_channel.
    _apply_mis_attribution(leads_l, profile.mis_attribution, streams["misattr"])

    # §2.3 duplicates — inherit (already-noisy) parent state.
    _inject_duplicates(leads_l, outcomes_l, profile.duplicate_rate, seed,
                       streams["duplicate"])

    # §2.5 outliers — own pre-degraded payload, appended last among the
    # non-spurious dims so duplicate sampling can't pick them up as parents.
    _inject_outliers(leads_l, outcomes_l, profile.outlier_rate, seed,
                     streams["outlier"])

    # §4 spurious patterns — LAST step per the planning header ORDERING
    # note so S3's keyword injection survives any earlier text_noise pass.
    patterns = inject_spurious_patterns(
        leads_l, form_submissions_l, outcomes_l,
        profile=profile, rng=streams["spurious"],
    )
    manifest: dict = {"patterns": patterns}

    return leads_l, touchpoints_l, form_submissions_l, sales_notes_l, outcomes_l, manifest
