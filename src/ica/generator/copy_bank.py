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

from dataclasses import dataclass

import numpy as np

from ica.taxonomy import (
    Channel,
    FormType,
    Persona,
    Theme,
)

__all__ = ["Snippet", "form_answer", "sales_note", "form_question"]

_T = Theme  # local brevity alias for the dense bank literals below


@dataclass(frozen=True)
class Snippet:
    """One bank entry. primary_theme is the theme the snippet was keyed by;
    secondary_theme is set only on bridge snippets (~30% of the bank)."""

    text: str
    primary_theme: Theme
    secondary_theme: Theme | None = None

    @property
    def ground_truth_themes(self) -> list[Theme]:
        """Primary first, optional secondary — the form_submissions /
        sales_notes ground_truth_themes array (data-world.md §2.3, §4)."""
        if self.secondary_theme is None:
            return [self.primary_theme]
        return [self.primary_theme, self.secondary_theme]


# =============================================================================
# Form free-text answers — keyed (persona, primary theme).
# Pure snippets carry one theme; bridge snippets carry a (primary, secondary)
# pair from taxonomy.THEME_BRIDGE_PAIRS. ~30% of the bank are bridges.
# =============================================================================

_FORM_ANSWERS: dict[tuple[Persona, Theme], tuple[Snippet, ...]] = {
    (Persona.MAYA, _T.MANUAL_WORK_REDUCTION): (
        Snippet(
            "We're burning something like 12 hours a week on manual "
            "list-building before a single campaign goes out — it's all "
            "copy-paste between tools.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Honestly my ops team does the lead routing by hand every "
            "Monday. The ops backlog never clears.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Every list pull, every status update — it's manual. My two "
            "ops folks spend more time on admin than on real work.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "I timed it — 9 hours a week of copy-paste between our CRM and "
            "the sales engagement tool. That's a headcount.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "The amount of manual admin my team eats every week is what "
            "keeps us from scaling. We do all of it by hand.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.MAYA, _T.PIPELINE_ATTRIBUTION): (
        Snippet(
            "I genuinely cannot tell you which channels drive our best "
            "pipeline. Attribution is a black box here.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "We run first-touch and last-touch side by side and they tell "
            "completely different stories. I trust neither.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "Marketing reports attribution numbers I cannot reconcile. "
            "Which campaigns actually work? No idea.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "Attribution is guesswork when the pipeline data is stitched "
            "across six different point solutions.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "I cannot run clean attribution because every tool reports "
            "which campaigns differently — classic tool sprawl.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.MAYA, _T.DATA_QUALITY): (
        Snippet(
            "Our CRM is a mess — dupes everywhere, half the company "
            "records have blank fields.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "I don't trust a single dashboard — the data underneath is "
            "full of duplicate accounts and blank fields.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "We burn hours every week hand-cleaning dupes before a "
            "campaign — fixing the data by hand.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Bad data is the root problem, but day to day it's my team "
            "fixing records by hand, copy-paste, every Monday.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Stale contacts pile up and clearing them is pure manual "
            "grind for my ops team.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.MAYA, _T.TOOL_SPRAWL_CONSOLIDATION): (
        Snippet(
            "We've got tool sprawl bad — fourteen GTM tools and half of "
            "them overlap.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Every quarter someone buys another point solution. Nobody "
            "consolidates anything.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Our stack is too many tools stitched together with brittle "
            "integrations.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "I want to consolidate. We pay for disparate systems that all "
            "kind of do the same thing.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "The tool sprawl is out of control — I can't get one tool to "
            "talk to the next without a point solution in between.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.MAYA, _T.FORECASTING_ACCURACY): (
        Snippet(
            "My forecast swings 30% week to week. I can't give the CRO a "
            "number I believe.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Pipeline coverage looks fine on paper but the forecast never "
            "lands. Something's off in how we score stages.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Reps sandbag, then deals come in we never forecasted. It's "
            "not a forecast, it's a guess.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Every quarter we miss the commit number and nobody can "
            "explain the gap afterward.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "I've got slipped deals showing up in three different "
            "forecast categories. The forecast hygiene is just bad.",
            _T.FORECASTING_ACCURACY,
        ),
    ),
    (Persona.DAVID, _T.REP_EFFICIENCY): (
        Snippet(
            "My reps get maybe a third of the day as real selling time — "
            "rep productivity is killing my number.",
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "Our talk tracks are inconsistent. Call quality is all over "
            "the place between my best AE and the rest.",
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "Rep productivity is bleeding out — reps lose selling time to "
            "manual admin instead of working deals.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Call quality would be fine if my AEs weren't doing "
            "list-building by hand instead of prepping for calls.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Rep productivity tanks when AEs do manual data entry instead "
            "of selling.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.DAVID, _T.FORECASTING_ACCURACY): (
        Snippet(
            "I have to call the quarter for the board and right now my "
            "forecast is a coin flip.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Pipeline coverage says 3x but I know half of it is air. Reps "
            "sandbag and it wrecks the forecast.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "We miss the commit number and I find out the week of. I need "
            "to see slipped deals coming, not after.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "My forecast and my gut disagree every single month. That's "
            "not a forecast I can take to the CEO.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "The forecast process is broken — reps sandbag low and I'm the "
            "one holding the commit number.",
            _T.FORECASTING_ACCURACY,
        ),
    ),
    (Persona.DAVID, _T.PIPELINE_ATTRIBUTION): (
        Snippet(
            "Marketing tells me which campaigns are working. I don't "
            "believe the attribution — it never matches my closed deals.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "I need to know which channels actually produce revenue so I "
            "can tell my reps where to spend their day.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "First-touch attribution gives marketing all the credit, "
            "last-touch gives my reps all of it. Nobody measures the "
            "truth.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "I can't tell which channels drive pipeline when the data "
            "lives in too many tools that don't agree.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Attribution is impossible — every point solution claims "
            "credit and nothing reconciles.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.DAVID, _T.MANUAL_WORK_REDUCTION): (
        Snippet(
            "My AEs waste the back half of every day on manual CRM "
            "updates. That's revenue time gone.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "I've got reps doing account research by hand, tab by tab. "
            "It's a joke at our deal size.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "The amount of copy-paste my team does between systems — I "
            "could give every rep back a day a week.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Manual list-building is eating my SDRs alive. They should be "
            "dialing, not building lists.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Every Monday it's the same manual ops backlog before anyone "
            "can actually work a deal.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.DAVID, _T.CROSS_TEAM_ALIGNMENT): (
        Snippet(
            "Sales and marketing are not aligned. We argue about lead "
            "quality in every single meeting.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "The handoff from marketing to my reps is broken. Leads sit, "
            "nobody owns them — a silo on both sides.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "Every QBR turns into finger-pointing between the teams. Zero "
            "alignment on what a good lead even is.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "Sales and marketing burn every QBR finger-pointing over who "
            "owns the attribution credit.",
            _T.CROSS_TEAM_ALIGNMENT,
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "The fight between marketing and sales is really an "
            "attribution fight — nobody agrees which campaigns get "
            "credit.",
            _T.CROSS_TEAM_ALIGNMENT,
            _T.PIPELINE_ATTRIBUTION,
        ),
    ),
    (Persona.PATRICIA, _T.COMPLIANCE_SECURITY): (
        Snippet(
            "Before we go further I need your SOC2 report, your DPA, and "
            "details on data residency.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Every vendor goes through our security review — SSO support "
            "and GDPR posture are non-negotiable.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Procurement won't even start a vendor evaluation without "
            "SOC 2 Type II in hand.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Every new point solution is another full security review for "
            "my team — the tool sprawl is a compliance burden.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Consolidating vendors isn't about cost for me — each one is "
            "another SOC2 review and another DPA.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.PATRICIA, _T.TOOL_SPRAWL_CONSOLIDATION): (
        Snippet(
            "We have too many tools and leadership is pushing hard to "
            "consolidate the vendor list.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Our environment is disparate systems bolted together, each "
            "one its own integration headache.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Too many point solutions. I want one platform, not fifteen "
            "things to stitch together.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "The tool sprawl in our stack is genuinely a risk surface. "
            "Consolidation is on my roadmap this year.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "We're paying for too many tools that overlap. Consolidating "
            "the stack is the priority.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.PATRICIA, _T.DATA_QUALITY): (
        Snippet(
            "The records we inherited are full of duplicate accounts and "
            "stale contacts. The data can't be trusted.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "It's a governance problem for us — blank fields, dupes, no "
            "clear system of record. Bad data everywhere.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "Our analysts fix dupes by hand all week — the bad data just "
            "regenerates.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "The duplicate records are bad enough, but it's the manual "
            "cleanup eating my team's time that I can't sustain.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "The enrichment gaps are constant, and clearing them is "
            "endless manual work for my analysts.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.PATRICIA, _T.CROSS_TEAM_ALIGNMENT): (
        Snippet(
            "IT and the revenue teams operate in total silos here. No "
            "shared definitions, no handoff process.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "There's no alignment between what sales and marketing ask IT "
            "for. We get conflicting requests weekly.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "Every cross-team request turns into finger-pointing. The "
            "hand-off between departments is undefined.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "Marketing and sales escalate attribution disputes to IT to "
            "arbitrate — that misalignment lands on my desk.",
            _T.CROSS_TEAM_ALIGNMENT,
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "The silo between the teams shows up as attribution arguments "
            "nobody can settle with our data.",
            _T.CROSS_TEAM_ALIGNMENT,
            _T.PIPELINE_ATTRIBUTION,
        ),
    ),
    (Persona.PATRICIA, _T.FORECASTING_ACCURACY): (
        Snippet(
            "Leadership wants IT to support a more reliable forecast, but "
            "our data feeds make the forecast unstable.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "The revenue team's forecast depends on systems my team owns, "
            "and pipeline coverage reporting is fragile.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "We get asked why the forecast missed and it always traces "
            "back to the data the forecast was built on.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Every quarter the commit number debate lands in IT because "
            "the reporting layer can't be trusted.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "Slipped deals aren't flagged anywhere in the system until the "
            "forecast has already moved.",
            _T.FORECASTING_ACCURACY,
        ),
    ),
    (Persona.CARLOS, _T.ONBOARDING_RAMP): (
        Snippet(
            "I just hired my first two reps and have no idea how to ramp "
            "them. There's no onboarding anything.",
            _T.ONBOARDING_RAMP,
        ),
        Snippet(
            "My new hires take forever to get up to speed. Time to first "
            "deal is brutal — like a full quarter.",
            _T.ONBOARDING_RAMP,
        ),
        Snippet(
            "New reps ramp slowly because we have no documented talk "
            "tracks for them to learn from.",
            _T.ONBOARDING_RAMP,
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "Getting a new hire up to speed would be faster if I had any "
            "call coaching system at all.",
            _T.ONBOARDING_RAMP,
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "A new rep would ramp faster with real call coaching instead "
            "of guesswork.",
            _T.ONBOARDING_RAMP,
            _T.REP_EFFICIENCY,
        ),
    ),
    (Persona.CARLOS, _T.REP_EFFICIENCY): (
        Snippet(
            "It's just me and two reps. Their call quality is wildly "
            "inconsistent and I have no time to fix it.",
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "We have no talk track, no follow-up cadence — every rep does "
            "their own thing.",
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "My reps' selling time is gone — they do all their "
            "list-building by hand because we can't afford tools.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Call quality is the least of it — my reps are stuck on "
            "manual admin all day.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "I'd fix call quality if my reps weren't doing everything by "
            "hand.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.CARLOS, _T.MANUAL_WORK_REDUCTION): (
        Snippet(
            "It's mostly me doing everything by hand — list-building, data "
            "entry, all of it.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "We can't afford tools so it's all manual. I copy-paste leads "
            "into a spreadsheet every night.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "My reps spend their day on manual admin because we have no "
            "automation at all.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Honestly the ops backlog is just a list of things I haven't "
            "gotten to by hand yet.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Everything is copy and paste between three free tools. It's "
            "manual and it's slow.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (Persona.CARLOS, _T.PIPELINE_ATTRIBUTION): (
        Snippet(
            "I have no idea which channels are working. I'm spending on "
            "three things and flying blind on attribution.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "Someone said I should track first-touch but I don't even "
            "know what drives pipeline yet.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "Which campaigns actually bring in customers? I genuinely "
            "could not tell you. No attribution at all.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "I can't do attribution because my data is split across too "
            "many tools I duct-taped together.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "Figuring out which channels work is impossible when every "
            "point solution shows different numbers.",
            _T.PIPELINE_ATTRIBUTION,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.CARLOS, _T.DATA_QUALITY): (
        Snippet(
            "My CRM is a mess already and the company is two years old. "
            "Dupes everywhere.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "Half my contact records have blank fields. It's bad data "
            "from day one.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "The dupes pile up and I clean them by hand whenever I get a "
            "free hour.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Bad data everywhere, and fixing it is just me, manually, late "
            "at night.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "The blank fields never end — I fill them in by hand every "
            "weekend.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    # Cross-theme cells — the F2/F5 comparison cells. Added in the journeys.py
    # gate once PERSONA_THEME_SHARE confirmed these (persona, theme) pairs
    # occur: Maya/David/Carlos x compliance_security (F5), Patricia x
    # manual_work_reduction (F2).
    (Persona.MAYA, _T.COMPLIANCE_SECURITY): (
        Snippet(
            "Every tool I want to roll out gets stuck in security review for "
            "a quarter. It is killing our roadmap.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "I am the one chasing SOC2 reports and DPAs for every vendor my "
            "team wants. Not my job, but it falls to me.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Procurement will not approve anything without SSO and a data "
            "residency commitment. Every rollout stalls there.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Every new point solution my team wants is another security "
            "review — the tool sprawl doubles our compliance load.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "I would consolidate the stack just to cut the SOC2 reviews — "
            "each disparate system is its own vendor evaluation.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.DAVID, _T.COMPLIANCE_SECURITY): (
        Snippet(
            "Deals stall in my prospect's security review for months. I lose "
            "the quarter waiting on a SOC 2 sign-off.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Every enterprise deal now needs SSO, a DPA, GDPR answers. My "
            "reps aren't equipped for that conversation.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Procurement and security review on the buyer side add ninety "
            "days to every deal cycle.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Buyers ask why we run so many systems — each point solution is "
            "another security review for their team.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "The deal needs us to consolidate vendors — every disparate "
            "system triggers its own vendor evaluation and SOC2 check.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.CARLOS, _T.COMPLIANCE_SECURITY): (
        Snippet(
            "A big prospect asked for our SOC2 and I don't even have one "
            "yet. No idea where to start.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Suddenly everyone wants SSO and a security review and I'm a "
            "five-person company. It's overwhelming.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "A customer's procurement team sent me a GDPR and data residency "
            "questionnaire. I had to look up half of it.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "Every tool I bolt on is another thing a prospect's security "
            "review flags — I should consolidate before I get audited.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "I stitched together five free tools and now a buyer wants a "
            "vendor evaluation on each one.",
            _T.COMPLIANCE_SECURITY,
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (Persona.PATRICIA, _T.MANUAL_WORK_REDUCTION): (
        Snippet(
            "My team runs every vendor security check by hand — it is a "
            "manual slog through spreadsheets.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "User provisioning is all manual here — we add and remove access "
            "by hand, account by account.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "Every access ticket is manual — IT copy-pastes the same setup "
            "steps for each new system.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "We track our whole asset inventory by hand in a spreadsheet. "
            "The manual upkeep eats a full headcount.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "My analysts spend their week on manual reporting pulls — "
            "copy-paste from four systems into one deck.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
}


# =============================================================================
# Sales notes — keyed (theme, kind). call_transcript_snippet is the lead
# speaking (Gong-style); rep_note is the rep summarizing. Each carries
# ground_truth_themes like form answers.
# =============================================================================

_REP_NOTE = "rep_note"
_TRANSCRIPT = "call_transcript_snippet"

_SALES_NOTES: dict[tuple[Theme, str], tuple[Snippet, ...]] = {
    (_T.MANUAL_WORK_REDUCTION, _TRANSCRIPT): (
        Snippet(
            "...yeah honestly it's the manual stuff, we copy-paste lists "
            "by hand every single week, it never ends.",
            _T.MANUAL_WORK_REDUCTION,
        ),
        Snippet(
            "...my ops person is just buried, it's all manual "
            "list-building, nothing is automated.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (_T.MANUAL_WORK_REDUCTION, _REP_NOTE): (
        Snippet(
            "Discovery call — pain is manual toil, heavy copy-paste and "
            "list-building. Clear automation fit.",
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (_T.DATA_QUALITY, _TRANSCRIPT): (
        Snippet(
            "...the CRM is a mess, total dupes, blank fields all over, we "
            "can't trust any report.",
            _T.DATA_QUALITY,
        ),
        Snippet(
            "...it's bad data, stale contacts everywhere, and we fix the "
            "dupes by hand all week.",
            _T.DATA_QUALITY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (_T.DATA_QUALITY, _REP_NOTE): (
        Snippet(
            "Disco — data quality pain. Dupes, blank fields, enrichment "
            "gaps. Wants a clean system of record.",
            _T.DATA_QUALITY,
        ),
    ),
    (_T.TOOL_SPRAWL_CONSOLIDATION, _TRANSCRIPT): (
        Snippet(
            "...we've got too many tools, every team bought its own point "
            "solution, nothing is consolidated.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
        Snippet(
            "...the tool sprawl is real, like fifteen things stitched "
            "together, impossible to manage.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (_T.TOOL_SPRAWL_CONSOLIDATION, _REP_NOTE): (
        Snippet(
            "Call — classic tool sprawl, disparate systems, wants to "
            "consolidate the stack.",
            _T.TOOL_SPRAWL_CONSOLIDATION,
        ),
    ),
    (_T.PIPELINE_ATTRIBUTION, _TRANSCRIPT): (
        Snippet(
            "...I really can't tell which channels work, attribution here "
            "is basically a guess.",
            _T.PIPELINE_ATTRIBUTION,
        ),
        Snippet(
            "...marketing shows me first-touch, sales shows me last-touch, "
            "the attribution never agrees.",
            _T.PIPELINE_ATTRIBUTION,
        ),
    ),
    (_T.PIPELINE_ATTRIBUTION, _REP_NOTE): (
        Snippet(
            "Disco — attribution pain. Can't see which campaigns produce "
            "revenue. Reporting need.",
            _T.PIPELINE_ATTRIBUTION,
        ),
    ),
    (_T.FORECASTING_ACCURACY, _TRANSCRIPT): (
        Snippet(
            "...the forecast is a coin flip, reps sandbag, I never know "
            "the real number.",
            _T.FORECASTING_ACCURACY,
        ),
        Snippet(
            "...pipeline coverage looks great but the forecast misses, I "
            "can't call the quarter at all.",
            _T.FORECASTING_ACCURACY,
        ),
    ),
    (_T.FORECASTING_ACCURACY, _REP_NOTE): (
        Snippet(
            "Call — forecasting pain. Slipped deals, sandbagging, weak "
            "commit number confidence.",
            _T.FORECASTING_ACCURACY,
        ),
    ),
    (_T.REP_EFFICIENCY, _TRANSCRIPT): (
        Snippet(
            "...my reps' call quality is all over the place, no real talk "
            "track, everyone improvises.",
            _T.REP_EFFICIENCY,
        ),
        Snippet(
            "...selling time is gone, my reps do list-building by hand "
            "instead of calls.",
            _T.REP_EFFICIENCY,
            _T.MANUAL_WORK_REDUCTION,
        ),
    ),
    (_T.REP_EFFICIENCY, _REP_NOTE): (
        Snippet(
            "Disco — rep efficiency. Inconsistent talk tracks, low rep "
            "productivity, wants call coaching at scale.",
            _T.REP_EFFICIENCY,
        ),
    ),
    (_T.CROSS_TEAM_ALIGNMENT, _TRANSCRIPT): (
        Snippet(
            "...sales and marketing just don't align, every handoff is a "
            "fight, total silos.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
        Snippet(
            "...there's so much finger-pointing between the teams, the "
            "hand-off is broken.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
    ),
    (_T.CROSS_TEAM_ALIGNMENT, _REP_NOTE): (
        Snippet(
            "Call — cross-team pain. Sales-and-marketing silos, broken "
            "handoff, finger-pointing in QBRs.",
            _T.CROSS_TEAM_ALIGNMENT,
        ),
    ),
    (_T.ONBOARDING_RAMP, _TRANSCRIPT): (
        Snippet(
            "...my new reps take forever to ramp, there's no onboarding, "
            "it's just sink or swim.",
            _T.ONBOARDING_RAMP,
        ),
        Snippet(
            "...a new hire isn't up to speed for a whole quarter, no "
            "talk track for them to learn.",
            _T.ONBOARDING_RAMP,
            _T.REP_EFFICIENCY,
        ),
    ),
    (_T.ONBOARDING_RAMP, _REP_NOTE): (
        Snippet(
            "Disco — onboarding pain. New hires slow to ramp, no "
            "onboarding program, long time to first deal.",
            _T.ONBOARDING_RAMP,
        ),
    ),
    (_T.COMPLIANCE_SECURITY, _TRANSCRIPT): (
        Snippet(
            "...before anything I need your SOC2, the DPA, SSO support — "
            "procurement won't move without it.",
            _T.COMPLIANCE_SECURITY,
        ),
        Snippet(
            "...we have a hard security review, data residency and GDPR "
            "are dealbreakers.",
            _T.COMPLIANCE_SECURITY,
        ),
    ),
    (_T.COMPLIANCE_SECURITY, _REP_NOTE): (
        Snippet(
            "Call — compliance gating. Needs SOC 2, SSO, DPA. Full vendor "
            "evaluation underway.",
            _T.COMPLIANCE_SECURITY,
        ),
    ),
}


# =============================================================================
# Form questions — keyed by form_type (data-world.md §2.3). Plain prompt
# strings; not theme-tagged.
# =============================================================================

_FORM_QUESTIONS: dict[FormType, tuple[str, ...]] = {
    FormType.DEMO_REQUEST: (
        "What's the biggest GTM challenge you're hoping a demo can address?",
        "What would you most want to see in a demo?",
    ),
    FormType.NEWSLETTER_SIGNUP: (
        "What GTM topics do you most want us to cover?",
        "What's the one GTM problem you'd love to read about?",
    ),
    FormType.CONTENT_DOWNLOAD: (
        "What prompted you to grab this resource?",
        "What are you hoping to solve right now?",
    ),
    FormType.CONTACT_SALES: (
        "What's the situation you're looking to solve?",
        "Tell us briefly what you need help with.",
    ),
    FormType.COMPARISON_PAGE_CTA: (
        "What's driving your evaluation right now?",
        "What are you weighing us against, and why?",
    ),
    FormType.WEBINAR_REGISTER: (
        "What do you hope to take away from this session?",
        "What's the GTM challenge on your mind heading into this?",
    ),
}


# =============================================================================
# Channel flavor — a light optional contextual opener (Fork 6). Openers are
# anchor-free so flavored output keeps the bank snippet's theme labels exact.
# organic_search has none — a search arrival has no distinctive voice.
# =============================================================================

_CHANNEL_FLAVOR: dict[Channel, tuple[str, ...]] = {
    Channel.PODCAST: (
        "Caught your podcast episode and had to reach out — ",
        "After listening to the podcast — ",
    ),
    Channel.LINKEDIN_PAID: (
        "Clicked through from your LinkedIn ad. ",
        "Saw this on LinkedIn — ",
    ),
    Channel.WEBINAR: (
        "Signing up for the webinar. ",
        "After the webinar I figured I'd ask — ",
    ),
    Channel.COMPARISON_PAGE: (
        "Comparing a few options right now. ",
        "Found you on a comparison site — ",
    ),
    Channel.NEWSLETTER: (
        "Been reading the newsletter for a while. ",
    ),
}

_FLAVOR_PROBABILITY = 0.5


def _apply_channel_flavor(
    snippet: Snippet, channel: Channel, rng: np.random.Generator
) -> Snippet:
    """Optionally prepend a channel opener. Themes are unchanged — openers
    carry no anchors."""
    openers = _CHANNEL_FLAVOR.get(channel)
    if not openers or rng.random() >= _FLAVOR_PROBABILITY:
        return snippet
    opener = openers[int(rng.integers(len(openers)))]
    return Snippet(
        opener + snippet.text, snippet.primary_theme, snippet.secondary_theme
    )


def form_answer(
    persona: Persona, channel: Channel, theme: Theme, rng: np.random.Generator
) -> Snippet:
    """A form_submissions.free_text_answer for a (persona, channel, theme)
    lead. Keyed by (persona, theme); channel applies a light optional opener.
    """
    pool = _FORM_ANSWERS[(persona, theme)]
    base = pool[int(rng.integers(len(pool)))]
    return _apply_channel_flavor(base, channel, rng)


def sales_note(theme: Theme, kind: str, rng: np.random.Generator) -> Snippet:
    """A sales_notes.text snippet for a theme. kind is rep_note or
    call_transcript_snippet (data-world.md §2.4)."""
    pool = _SALES_NOTES[(theme, kind)]
    return pool[int(rng.integers(len(pool)))]


def form_question(form_type: FormType, rng: np.random.Generator) -> str:
    """The free_text_question prompt shown for a form type."""
    pool = _FORM_QUESTIONS[form_type]
    return pool[int(rng.integers(len(pool)))]


def iter_bank_snippets() -> tuple[Snippet, ...]:
    """Every Snippet in the static bank (form answers + sales notes) — used
    by the lexical-separation discipline test."""
    out: list[Snippet] = []
    for pool in _FORM_ANSWERS.values():
        out.extend(pool)
    for pool in _SALES_NOTES.values():
        out.extend(pool)
    return tuple(out)
