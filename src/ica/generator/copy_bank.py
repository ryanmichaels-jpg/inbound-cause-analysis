"""Synthetic qualitative-text bank — form free-text answers and sales notes.

copy_bank.py is the voice-of-customer text generator. Its output is the
qualitative signal the CP4 Claude resonance layer extracts themes from —
per PROJECT.md the strongest portfolio differentiator — so voice realism
and theme legibility are the priorities. It is a library (shape like
content_library.py): a static snippet bank plus selection helpers that
journeys.py (form_submissions rows) and outcomes.py / seed.py (sales_notes
rows) draw from. No engineered skews.

Sources: docs/data-world.md §2.3 (form_submissions), §2.4 (sales_notes),
§4 (theme taxonomy — mwr/data_quality disambiguation + ground-truth
tagging), §6 (persona language tics); src/ica/taxonomy.py §3
(MWR_VS_DATA_QUALITY_DISAMBIGUATION) and the FormType enum;
docs/aha-patterns.md (Taxonomy SSOT section).

TODO (planning header — review before any implementation). Each decision
below is tagged DICTATED (locked-doc, cited) or PROPOSED (a v1 design
choice needing approval).

== What copy_bank produces (DICTATED) ==
- form_submissions.free_text_answer — keyed by (persona, channel, theme)
  [data-world §2.3; aha-patterns SSOT section]. Note: the answer is keyed
  by (persona, channel, theme), NOT by form_type — form_type drives the
  question, not the answer.
- sales_notes.text [data-world §2.4].
- Every emitted row carries ground_truth_themes — a JSON array, primary
  theme first, optional secondary [data-world §2.3, §4].
copy_bank is a library: it returns text + labels. It does NOT build table
rows, and does NOT decide which leads get sales_notes — that is
downstream (journeys.py / outcomes.py / seed.py). [Boundary follows the
content_library precedent and the build sequence — PROPOSED.]

== Fork 1 — snippet generation approach ==
PROPOSED: a hand-written snippet bank, not compositional slot-filling.
This text is the LLM resonance eval's input; composed persona-voice ×
theme-vocab templates read mechanically, and Fork 2 needs tight hand
control of theme vocabulary. Form answers are short (1-3 sentences), so
hand-authoring is tractable and buys the realism.
Bank organized by (persona, theme); channel is a light flavor only (see
Fork 6), not a third bank axis. Rough volume: ~20 active (persona × theme)
cells (4 personas × ~5 affinity themes each, per §6), 5-8 snippets per
cell -> ~120-150 form-answer snippets, plus a smaller sales-notes set and
the form questions. ~30% of the bank are bridge snippets (Fork 3).
Rejected alternative: compositional templating — cheaper coverage, worse
voice.

== Fork 2 — mwr vs data_quality vocabulary discipline ==
The disambiguation RULE is DICTATED [data-world §4; taxonomy
MWR_VS_DATA_QUALITY_DISAMBIGUATION] — copy_bank imports that constant and
never redefines it. The ENFORCEMENT mechanism is PROPOSED:
- Add a structured anchor-vocabulary constant to taxonomy.py — SSOT,
  shared by copy_bank generation, the enforcement test, and (CP4) the
  extraction prompt. Per-theme machine-checkable tokens (exact substrings
  / simple regex, not prose), e.g. mwr: "copy-paste", "list-building",
  "by hand", "hours a week", "ops backlog", "rep time on admin";
  data_quality: "dupes", "blank fields", "stale contacts", "bad data",
  "enrichment gaps", "the CRM is a mess" (from §4). [Small taxonomy
  addition — PROPOSED.]
- Every PURE (single-theme) snippet must contain >=1 of its own theme's
  anchors and ZERO anchors of any other theme. Bridge snippets are the
  only entries allowed to carry two themes' vocabulary.
- A pytest test scans every pure snippet and FAILS if it carries a
  foreign theme's anchor. This automated lexical-separation check is the
  cheap mechanical proxy for the LLM eval — if it passes, the mwr and
  data_quality cells are provably separable at the vocabulary level.

== Fork 3 — ground_truth_themes labeling ==
DICTATED [data-world §4]: every row carries ground_truth_themes; primary
= the theme the snippet was keyed by; a secondary is set on ~30% of rows
that legitimately bridge two themes; the array is primary-first. For the
mwr/data_quality bridge specifically, primary = the goal (data_quality),
secondary = the symptom (mwr) [§4, verbatim].
PROPOSED:
- The label travels WITH the snippet — each bank entry is a Snippet
  record (text, primary_theme, secondary_theme | None), not a parallel
  lookup. ground_truth_themes = [primary] or [primary, secondary].
- Bridge snippets are HAND-AUTHORED as bridges (a snippet that genuinely
  says both "hours every week" and "dupes" is intrinsically a
  data_quality+mwr bridge) — the secondary is an authored property, not a
  random post-hoc assignment. The ~30% emerges from composing each cell's
  pool as ~70% pure / ~30% bridge; uniform selection yields ~30% of
  emitted rows with a secondary.
- Bridge pairs follow thematic adjacency, not arbitrary pairing. The
  mwr<->data_quality direction is DICTATED (§4); other adjacency pairs
  (e.g. mwr<->rep_efficiency, pipeline_attribution<->forecasting_accuracy,
  tool_sprawl_consolidation<->data_quality) are a PROPOSED v1 set.
- Downstream reads snippet.ground_truth_themes and writes the JSON column.

== Fork 4 — free_text_question ownership ==
data-world §2.3 calls free_text_question "the prompt shown (form-type-
specific)" but does NOT attribute it to copy_bank — ownership is not
dictated. PROPOSED: copy_bank owns the form questions — it is the text
bank, and prompts are prose, not taxonomy-class canonical names. A small
FormType -> prompt(s) mapping, 1-3 variants per the 6 form types, keyed by
form_type only.

== Fork 5 — sales_notes kind and author ==
DICTATED [data-world §2.4]: kind in {rep_note, call_transcript_snippet},
author in {sdr, ae, sales_engineer}.
PROPOSED:
- kind SHAPES the text. call_transcript_snippet = the lead speaking:
  first-person, persona-voiced, theme-flavored (Gong-style). rep_note =
  the rep summarizing the lead: terse third-person observation, still
  theme-bearing and theme-tagged, but in rep voice, not persona voice.
  copy_bank generates kind-conditioned text.
- author is a row-level metadata dimension applied at sales_notes
  construction (downstream); it does not strongly shape copy text in v1.
- WHICH leads get sales_notes is downstream (outcomes.py / seed.py) per
  §2.4 ("only leads that reached SQL/Opp ...") — not copy_bank's call.

== Fork 6 — channel's role in keying ==
DICTATED [data-world §2.3; aha-patterns SSOT]: the form-answer API key is
(persona, channel, theme). PROPOSED: in v1 the snippet TEXT is shaped by
(persona, theme); channel contributes at most a light optional contextual
opener (a podcast lead may reference the episode; a comparison_page lead
may reference evaluating options). Channel is not a third bank axis —
that would triple the hand-authoring for little voice payoff, since what
a lead types in a form is driven by their pain (theme) and who they are
(persona), not their arrival channel.

== Fork 7 — other locked-doc items ==
- copy_bank imports MWR_VS_DATA_QUALITY_DISAMBIGUATION from taxonomy and
  keeps generation aligned with it; the same constant feeds the CP4
  extraction prompt [taxonomy §3 — DICTATED].
- copy_bank carries NO engineered skews — all skews live in seed.py
  [aha-patterns skew-application order — DICTATED].
- Snippet-variant selection is rng-driven and deterministic; selection
  helpers take a seeded numpy Generator [project determinism convention
  — PROPOSED].
- ground_truth_themes are generation-time labels, not a human-validated
  gold standard; the CP6 README must state this [data-world §4 —
  DICTATED; a README task, not copy_bank code].

== Proposed module API (PROPOSED) ==
- Snippet dataclass: text, primary_theme, secondary_theme | None, with a
  .ground_truth_themes property.
- form_answer(persona, channel, theme, rng) -> Snippet
- sales_note(persona, theme, kind, rng) -> Snippet
- form_question(form_type, rng) -> str
- the static SNIPPET_BANK, plus the Fork 2 anchor-enforcement test.

== What copy_bank does NOT do ==
- No table rows — form_submissions / sales_notes rows are built downstream.
- No decision on which leads get sales_notes (outcomes.py / seed.py).
- No engineered skews.
- No redeclaration of themes / personas / form types / the disambiguation
  rule — all imported from taxonomy.
"""
