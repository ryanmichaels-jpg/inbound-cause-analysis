"""Multi-touch journey synthesis — touchpoints, form submissions, seed themes.

journeys.py is the most involved generator module. It consumes the
list[PartialLead] from channels.py and, using content_library and
copy_bank, produces:
  - the touchpoints table rows for every lead,
  - the form_submissions table rows,
  - seed_label_theme_primary and seed_label_theme_secondary on each lead.
seed_label_theme_primary is the last unset PartialLead field — after
journeys.py every PartialLead.to_lead() succeeds.

Sources: docs/data-world.md §1, §2.1-2.3, §4, §5; docs/aha-patterns.md
Finding 3 + the skew-application order; src/ica/taxonomy.py (EventType,
FormType, the F3_* constants, THEME_BRIDGE_PAIRS, PERSONA_THEME_AFFINITY).

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (locked-doc, cited) or PROPOSED (a v1 design choice
needing approval).

== Item 1 — Finding 3 mechanics ==

DICTATED [aha-patterns.md Finding 3 path definition + §14 decision #4;
taxonomy F3_* constants]:
- The path: created_via_channel == podcast (first touch), AND a touchpoint
  with channel == organic_search within 14 days, AND a touchpoint with
  event_type == demo_request within 14 days.
- "25% path fraction" is 25% of the 200 PODCAST leads — F3_TARGET_PATH_COUNT
  = 50 leads. Not 25% of all leads.
- The 14-day window is measured from lead.created_at (the podcast
  first-touch timestamp) to each of the organic_search and demo_request
  touchpoints. F3_PATH_WITHIN_DAYS = 14.
- "demo" is event_type == demo_request (taxonomy EventType.DEMO_REQUEST) —
  the touchpoints table column is event_type, there is no "kind" column.
- Headroom: F3-path leads need podcast created_at on/before ~2026-06-16
  (14 days before the 2026-06-30 window end). channels.py's verification
  showed podcast created_at spread across Jan-Jun; well over 50 podcast
  leads fall on/before 2026-06-16, so the 50-lead path clears comfortably.

PROPOSED — module boundary for F3. aha-patterns.md describes
`apply_finding_3_journey_skew` as a seed.py skew function that synthesizes
the path touchpoints AND rebalances outcomes. Recommendation: the
touchpoint-synthesis half lives in journeys.py — journeys.py is the single
owner of the touchpoints table, and the F3 path is just a specific journey
shape. journeys.py deterministically selects 50 eligible podcast leads and
builds their path touchpoints. seed.py orchestrates; the ~45% CW lift is
NOT journeys.py — it composes in outcomes.py / the seed.py skew step
(F3_TARGET_PATH_CW_RATE = 0.45). This reinterprets aha-patterns.md's
"seed.py synthesizes" placement — flag for approval.

F3 is theme-agnostic (a journey-shape finding, not a persona-theme cell).
A path lead keeps its own seed_label_theme_primary; per aha-patterns.md
that theme flows downstream via the demo_request form-submission free-text.
The podcast/blog touchpoints carry content assets with the assets' own
themes, which need not equal the lead's theme.

== Item 2 — seed_label_theme_primary / secondary derivation ==

DICTATED [data-world.md §2.1; aha-patterns.md F2 + F5]:
- seed_label_theme_primary is "the theme this lead's journey was generated
  to express"; secondary is optional, on ~30% of leads.
- F2 needs ~280 (Maya, manual_work_reduction) leads = 40% of Maya's 700,
  and ~207 non-Maya x manual_work_reduction.
- F5 needs ~260 (Patricia, compliance_security) leads = 40% of Patricia's
  650, and ~120 non-Patricia x compliance_security (~6% of each other
  persona).

PROPOSED — derivation. Assign seed_label_theme_primary by sampling from a
per-persona theme-share distribution (NOT by reading it off a content
asset). Reasoning: (a) the F2/F5 cell sizes are precise targets that
emergent-from-content assignment cannot hit; (b) content covers only 7 of
9 themes — content-derivation would make onboarding_ramp and
cross_team_alignment unreachable as primary, yet onboarding_ramp is
Carlos's signature theme; (c) copy_bank already has form-answer cells for
all 9 themes. The per-persona theme-share table spans all 9 themes (not
just each persona's top-5 affinity — F5 needs a ~6% compliance tail on
non-Patricia personas) and is anchored on the DICTATED F2/F5 numbers; the
full table is a v1 design choice — it will be proposed as a small
taxonomy commit before journeys.py implementation (the pattern used for
the copy_bank anchor vocab).

PROPOSED — secondary. journeys.py picks the primary theme, then draws the
lead's form-answer from copy_bank's (persona, primary) cell; the drawn
Snippet IS the source of truth — seed_label_theme_primary =
snippet.primary_theme, seed_label_theme_secondary = snippet.secondary_theme
(a THEME_BRIDGE_PAIRS partner when the snippet is a bridge). This makes
the seed labels and the free-text inherently consistent (§4: "primary
theme = the slug the copy-bank entry was keyed by"). The realized
secondary rate is copy_bank's ~30% form-answer bridge rate, weighted by
cell occupancy — journeys.py will verify it lands near the §2.1 ~30%
target; if it drifts, the lever is the per-cell bridge fractions, not a
new code path.

== Item 3 — touchpoint mechanics ==

DICTATED [data-world.md §2.2]: ts is ordered and monotonic per lead;
exactly one is_first_touch TRUE and one is_last_touch TRUE per lead;
event_type is the 11-value taxonomy EventType enum; content_asset_slug is
nullable.

PROPOSED:
- Touchpoints per lead: a small distribution, ~1-8, mean ~3-4. Pure
  form-only / low-engagement leads sit at the low end; richer journeys
  run longer. Exact distribution is a v1 choice.
- Journeys are multi-channel — the first touch is the lead's
  created_via_channel, later touchpoints may cross channels (the F3 path
  itself spans podcast -> organic_search).
- ts spacing: touchpoints fall between created_at and a lead-level
  horizon; spacing is a v1 choice (and F3-path touchpoints are
  constrained to the 14-day window).
- first-touch event_type is channel-conditioned (podcast -> podcast_listen,
  webinar -> webinar_register, etc.) — a proposed mapping.

== Item 4 — cross-module contracts ==

CONTRACT (DICTATED — established by the channels.py planning header and
data-world.md §2.1's "denormalized convenience"): the is_first_touch
touchpoint MUST replicate the lead exactly — ts == lead.created_at,
channel == lead.created_via_channel, and utm_campaign ==
first_touch_utm_campaign (for linkedin_paid leads). The lead-level fields
are the single source of truth; the first-touch touchpoint copies them and
must never drift. journeys.py reads channels.py output and content_library
/ copy_bank as libraries; it writes touchpoints + form_submissions and
sets the seed-theme fields.

== Item 5 — other locked-doc items ==
- form_submissions: each row links a form_submit touchpoint (touchpoint_id
  FK), carries form_type, free_text_question (copy_bank.form_question),
  free_text_answer (copy_bank.form_answer), and ground_truth_themes = the
  form-answer Snippet's ground_truth_themes [DICTATED §2.3, §4].
- sales_notes are NOT journeys.py — only leads reaching SQL/Opp carry
  them, an outcomes.py / seed.py concern [DICTATED §2.4, §5].
- journeys.py runs before outcomes.py, so baseline journeys are
  outcome-blind. data-world §5 marks stage progression loosely via
  event_type (demo_attended ~ SQL); whether journey richness correlates
  with the (not-yet-assigned) outcome is a surfaced question — proposed
  v1 answer: journeys are outcome-blind, the correlation stays loose.
- journeys.py is seeded (DEFAULT_SEED); fully deterministic.
- No engineered skews beyond the F3 path shape — all CW skews live in
  outcomes.py / seed.py [aha-patterns.md skew order].

== What journeys.py does NOT do ==
- No outcomes, no sales_notes, no CW-rate skews.
- No re-derivation of channel / campaign / created_at — those are read
  from channels.py output and copied onto the first-touch touchpoint.
- No content/copy text — content_library and copy_bank own those.

Output: list[PartialLead] with seed_label_theme_primary/secondary set
(every lead now finalizable via to_lead()), plus the touchpoints and
form_submissions row collections.
"""
