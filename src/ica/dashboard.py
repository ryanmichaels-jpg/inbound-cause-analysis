"""ICA dashboard — a Streamlit app over the generated dataset.

The presentation layer: renders the five aha Findings, lets a reviewer
explore the persona/channel/theme segments, and reserves the slot where
the signature feature (auto-generated GTM action artifacts) will land.

Sources: PROJECT.md (stage 5 "Insight + loop-back", the signature move,
the ruthless cut order); docs/aha-patterns.md ("Rendering note" — F1-4 vs
F5 placement); docs/data-world.md §4 (ground_truth_themes are seeded,
generation-time labels — not human-validated gold).

Run: `streamlit run src/ica/dashboard.py`. Deploy target: Streamlit Cloud.

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (locked-doc, cited) or PROPOSED (a v1 design choice).

== Flag — where the dashboard sits in the build sequence ==
PROJECT.md's five-stage architecture puts CP2 (structuring), CP3 (driver
identification) and CP4 (the Claude resonance-extraction layer + theme-
stability check) BETWEEN the generator and the dashboard. We are going
CP1 -> dashboard directly. That is workable — the dashboard reads
data/ica.db and the five Findings plus all persona/channel/theme analysis
are computable from the raw five tables (test_aha_patterns.py already
proves the Findings are query-reproducible). But CP4 is NOT built, so the
dashboard's theme views would use the SEEDED ground_truth_themes, which
data-world.md §4 explicitly calls generation-time labels, not LLM-
extracted gold. DECISION NEEDED: is CP4 (a) deferred — the dashboard
labels theme views honestly as "seeded ground-truth labels", (b) folded
into the upcoming signature-feature work (the Claude layer), or (c) a
prerequisite that should be built first? Recommend (a) + (b): v1 dashboard
on honestly-labelled seeded themes; the Claude resonance/extraction work
is the signature feature.

== Item 1 — views ==
v1 SHIPS (DICTATED that all five Findings appear — PROJECT.md "if any is
missing from the final dashboard, we re-seed"):
- Overview / "Key findings" — F1-F4 as prominent cards; F5 in a smaller
  "Additional patterns surfaced" card below [DICTATED — aha-patterns.md
  Rendering note].
- Per-Finding detail — each Finding's chart + supporting numbers.
- Segment Explorer — a persona x theme (and persona x channel) view with
  a basic filter.
- GTM Actions — the signature-feature slot (see Item 4).
DEFERS if time tightens: a raw-table browser; advanced explorer filters;
the theme-stability score (cut per PROJECT.md's ruthless cut order item 3
— README will acknowledge it as planned next).

== Item 2 — navigation ==
PROPOSED: a single-file app with top-level `st.tabs` — Overview ·
Findings · Explore · Actions. No multi-page routing, no session state.
Simplest to build and to deploy. (Sidebar `st.radio` is the alternative.)

== Item 3 — data layer ==
PROPOSED: one `@st.cache_data` loader that ensures data/ica.db exists —
calling `seed.generate()` if it does not — then reads the five tables via
`pandas.read_sql` into DataFrames. Raw SQL aggregation queries, no ORM
(SQLAlchemy/SQLModel would be over-engineering for read-only rollups).
FLAG: data/ica.db is git-ignored, so a Streamlit Cloud deploy has no DB
file — the loader regenerates it on first load (the generator is
deterministic, ~15s, then cached for the session). streamlit and pandas
are added to pyproject (a `[dashboard]` optional-dependency extra so the
generator/test install stays lean).

== Item 4 — signature-feature integration point ==
The signature feature (auto-generated GTM action artifacts) is not built.
PROPOSED: it surfaces in a dedicated "Actions" tab. v1 dashboard ships
that tab as a labelled placeholder ("recommended GTM actions render
here"); the signature-feature work fills it. Reserving a whole tab means
the dashboard needs no structural refactor when the feature lands.

== Item 5 — chart per Finding (readable over clever) ==
PROPOSED:
- F1 channel quality — bar: closed-won rate by channel (podcast tall,
  linkedin_paid short); the Pareto reframe reads at a glance.
- F2 Maya x mwr — grouped bar: mwr closed-won rate per persona.
- F3 multi-touch path — comparison bar: path vs non-path-podcast vs
  dataset-overall CW. NOT a Sankey — clever, fiddly in Streamlit, and the
  bar makes the ~6x lift obvious.
- F4 ICP/volume mismatch — bar: campaign volume with bad-outcome share
  overlaid (or a volume-vs-mean-ICP scatter).
- F5 Patricia x compliance — same grouped-bar style as F2, smaller card.
- Explorer — a persona x theme heatmap (Altair). Plain `st.bar_chart`
  elsewhere; Altair only where a heatmap genuinely helps.

== Item 6 — time-budget scoping (lean ship) ==
- Overview + per-Finding detail: full v1 — non-negotiable (the re-seed
  clause).
- Segment Explorer: ship a basic version (one heatmap + one filter);
  defer richer filtering.
- GTM Actions: ship the placeholder tab only; the feature is separate
  work and is first to degrade per the ruthless cut order.
- Raw-table browser, theme-stability score: deferred.
Scoped so the signature feature keeps adequate runway.

== Item 7 — other doc constraints ==
- All five Findings must render or we re-seed [DICTATED — PROJECT.md].
- F1-4 prominent, F5 subordinated [DICTATED — aha-patterns Rendering note].
- Theme views must be honestly labelled as seeded generation-time labels
  until CP4 exists [DICTATED — data-world.md §4].
- The app must deploy to Streamlit Cloud and run locally in one command
  [DICTATED — PROJECT.md stack/deliverables].

== What v1 does NOT do ==
- No CP4 Claude resonance extraction, no theme-stability score.
- No write-back to the DB — read-only.
- No auth, no multi-dataset switching.

Output: a single deployable Streamlit app rendering all five Findings,
a segment explorer, and the reserved Actions slot.
"""
