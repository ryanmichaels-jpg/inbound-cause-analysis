"""ICA insight layer — CP4 resonance extraction and the signature feature.

The signature move (PROJECT.md): auto-generated GTM action artifacts that
close the loop from insight to action — most portfolio pieces stop at a
dashboard. This module also folds in CP4, the Claude resonance-extraction
layer, per the dashboard-round (a)+(b) decision: Claude extracts themes
from the raw qualitative fields, and those feed the artifact generation.

Sources: PROJECT.md (Signature move; pipeline stages 4-5; LLM-credibility
section; the ruthless cut order — artifacts are cut item #1).
docs/data-world.md §4 (ground_truth_themes are seed labels, not gold).
taxonomy.py §3 + §14 (the disambiguation rule and anchor vocab were
written to be shared by copy_bank generation AND this extraction prompt).

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (cited spec or a prior locked decision) or PROPOSED
(a v1 design choice open to review).

== Core architectural call: the LLM layer is offline and run-once ==
PROPOSED. The Claude calls do NOT run on dashboard load. A CLI step
(`python -m ica.insight`) runs extraction + artifact generation once,
writes its output to committed files, and the dashboard merely reads
those files. This one decision resolves four problems together:
- Determinism: the generator stays byte-deterministic; the LLM output is
  a committed, dated snapshot rather than something regenerated per run.
- Secrets: only the offline step needs ANTHROPIC_API_KEY. The deployed
  Streamlit Cloud dashboard needs no key and makes no network call.
- Cost / latency: the API is hit once, not on every page view.
- Reviewability: a hiring manager sees the artifacts in the repo without
  running anything or holding a key.

== Decision 1 — CP4 resonance extraction ==
What: Claude reads the qualitative fields (form free-text answers and
sales-note text) and labels each with a primary theme, plus an optional
secondary, from the fixed taxonomy.
- DICTATED: themes are the taxonomy `Theme` enum, not free-form — the
  taxonomy already settled PROJECT.md's open "free-form vs fixed" item.
- DICTATED: the extraction prompt reuses MWR_VS_DATA_QUALITY_
  DISAMBIGUATION and THEME_ANCHOR_VOCAB from taxonomy.py — both exist to
  be shared by copy_bank (generation) and this prompt (extraction).
- PROPOSED scope: extract a stratified SAMPLE (~300 snippets across
  personas and themes), not all ~2,736 fields. The sample is enough to
  prove extraction works, to compute an extracted-vs-seed agreement
  score, and to roll up per-persona resonance. Full-corpus extraction
  (~140 batched calls) is the if-time upgrade, not v1.
- PROPOSED credibility output: report the agreement score — how often
  Claude's extracted primary theme matches the seed ground_truth_theme.
  The ground truth already exists; this is a cheap, high-signal README
  number and a partial stand-in for the deferred stability check.

== Decision 2 — prompt design ==
Two prompts, both as module constants.
- Extraction: input a batch of snippets, output JSON constrained to the
  Theme enum (snippet id, primary, secondary). PROPOSED model: Haiku 4.5
  — a cheap, high-volume classification task. JSON output so parsing is
  robust.
- Artifact generation: input one Finding (its numbers, the resonant
  theme, 2-3 real example snippets buyers actually wrote), output a
  drafted artifact. PROPOSED model: Sonnet 4.6 — few calls, needs
  quality GTM writing.

== Decision 3 — artifact selection ==
PROJECT.md names three artifact types: content briefs, ad-copy variants,
ICP refinements. PROPOSED v1 — one artifact per headline Finding, type
chosen to fit, so the insight->action loop closes on each:
- F1 channel quality   -> content brief (lean into the podcast channel)
- F2 message-persona   -> ad-copy variants (Maya x manual-work-reduction)
- F3 multi-touch path  -> a sequence / play brief
- F4 ICP vs volume     -> an ICP refinement (tighten the broad-funnel ICP)
F5 -> an optional 5th artifact if time allows. This ships all three
named types plus a journey play; 4-5 generation calls is trivial cost.

== Decision 4 — output format ==
PROPOSED: artifacts written as markdown into a committed `artifacts/`
directory — one file per artifact, plus a `resonance.md` extraction
report (the agreement score + per-persona resonance). Markdown because
it reads cleanly in the repo, on GitHub, and in Streamlit unchanged.

== Flag — new dependency and secrets ==
PROPOSED: the `anthropic` SDK goes in its own optional-dependency extra
(`[insight]`), NOT in `[dashboard]` — the dashboard reads committed
markdown and never imports anthropic. `.env` carries ANTHROPIC_API_KEY;
`.env.example` is committed, `.env` is git-ignored (portfolio rule:
never commit real keys).

== Flag — dashboard Actions-tab follow-on ==
This work includes a dashboard.py edit: the Actions tab stops being a
placeholder and renders the artifacts + resonance report from
`artifacts/`; the "seeded ground-truth" theme disclaimer is updated to
point at the now-existing extraction. PROPOSED as a second commit after
insight.py lands.

== Flag — theme-stability check ==
PROJECT.md's LLM-credibility section wants an N-run stability score; the
ruthless cut order (item 3) explicitly allows cutting it with a README
acknowledgement. PROPOSED: defer it — the extracted-vs-seed agreement
score already supplies a credibility number — and acknowledge stability
in the README as the planned next step.

== Time budget — Day 3, and the degrade path ==
Auto-generated artifacts are cut-order item #1. PROPOSED: build the real
LLM version (it is the single strongest portfolio differentiator), but
timeboxed — decision point: if extraction plus one end-to-end artifact
is not working within the agreed budget, degrade per the cut order to
1-2 hard-templated artifacts filled from the seeded themes + finding
numbers, framed honestly in the README. Ryan sets the timebox.

== Module structure ==
PROPOSED: a single module `src/ica/insight.py` (extraction, roll-up,
artifact generation, a `main()` CLI) — a run-once offline script does
not need a package. CLI: `python -m ica.insight`; a Makefile `insight`
target. Tests: the deterministic parts (prompt assembly, agreement-score
computation, markdown rendering) unit-tested with the anthropic client
stubbed, so the suite stays hermetic — no network, no key.

== What v1 does NOT do ==
- No live API calls from the dashboard or inside the test suite.
- No full-corpus extraction (sample only); no theme-stability score.
- No closed-loop measurement (PROJECT.md Phase 2 — a README sketch only).

Output: a committed set of GTM action artifacts plus a resonance report,
surfaced in the dashboard Actions tab.
"""
