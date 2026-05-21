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

import sqlite3
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from ica.generator.seed import DEFAULT_DB_PATH, generate
from ica.taxonomy import (
    F3_PATH_WITHIN_DAYS,
    Channel,
    EventType,
    Outcome,
    Persona,
    Theme,
)

st.set_page_config(page_title="ICA — Inbound Cause Analysis", layout="wide")

_TABLES = ("leads", "touchpoints", "outcomes")
_WON = Outcome.CLOSED_WON.value
_BROAD_FUNNEL = "linkedin_q2_broad_funnel"
_CW_COL = "Closed-won rate"

# Visible everywhere a theme label is shown — the honesty discipline that keeps
# the eventual signature-feature reveal credible (data-world.md §4).
_THEME_NOTE = (
    "Themes here are generation-time seed labels (`ground_truth_themes`), not "
    "human-validated gold. LLM-extracted variants land with the signature-"
    "feature update."
)

_PERSONA_LABEL = {
    Persona.MAYA.value: "Maya · RevOps",
    Persona.DAVID.value: "David · VP Sales",
    Persona.PATRICIA.value: "Patricia · Ent. IT",
    Persona.CARLOS.value: "Carlos · SMB",
}


# =============================================================================
# Data layer — load + derive, cached so the generator runs at most once.
# =============================================================================


def _f3_path_ids(leads: pd.DataFrame, touchpoints: pd.DataFrame) -> set[str]:
    """Lead IDs on the Finding 3 journey: a podcast first touch followed by an
    organic-search touch and a demo_request, all within F3_PATH_WITHIN_DAYS."""
    created = dict(
        zip(leads["lead_id"], pd.to_datetime(leads["created_at"]), strict=True)
    )
    podcast_ids = set(
        leads.loc[leads["created_via_channel"] == Channel.PODCAST.value, "lead_id"]
    )
    tps = touchpoints.assign(ts=pd.to_datetime(touchpoints["ts"]))
    path: set[str] = set()
    for lead_id, grp in tps.groupby("lead_id"):
        if lead_id not in podcast_ids:
            continue
        within = grp[grp["ts"] <= created[lead_id] + timedelta(days=F3_PATH_WITHIN_DAYS)]
        has_blog = (within["channel"] == Channel.ORGANIC_SEARCH.value).any()
        has_demo = (within["event_type"] == EventType.DEMO_REQUEST.value).any()
        if has_blog and has_demo:
            path.add(lead_id)
    return path


@st.cache_data(show_spinner="Generating the ICA dataset (first load only, ~15s)…")
def load_dataset(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Load the tables into DataFrames, regenerating the SQLite file first if it
    is absent — a Streamlit Cloud deploy has no committed DB (data/ica.db is
    git-ignored). Cached, so the generator runs at most once per session."""
    if not Path(db_path).exists():
        generate(db_path=db_path)
    conn = sqlite3.connect(db_path)
    try:
        tables = {t: pd.read_sql(f"SELECT * FROM {t}", conn) for t in _TABLES}
    finally:
        conn.close()
    leads = tables["leads"].merge(tables["outcomes"], on="lead_id")
    leads["won"] = leads["outcome"] == _WON
    return {
        "leads": leads,
        "f3_path": _f3_path_ids(tables["leads"], tables["touchpoints"]),
    }


# =============================================================================
# Metric helpers
# =============================================================================


def _cw_rate(frame: pd.DataFrame) -> float:
    return float(frame["won"].mean()) if len(frame) else 0.0


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _bad_share(frame: pd.DataFrame) -> float:
    """Finding 4 'bad outcome' share: disqualified or ghosted, plus closed_lost
    tagged wrong_fit_late."""
    if not len(frame):
        return 0.0
    bad = frame["outcome"].isin([Outcome.DISQUALIFIED.value, Outcome.GHOSTED.value]) | (
        (frame["outcome"] == Outcome.CLOSED_LOST.value)
        & (frame["sub_reason"] == "wrong_fit_late")
    )
    return float(bad.mean())


def _cw_by(frame: pd.DataFrame, col: str) -> pd.DataFrame:
    return frame.groupby(col)["won"].mean().rename(_CW_COL).reset_index()


# =============================================================================
# Views
# =============================================================================


def render_overview(data: dict) -> None:
    leads = data["leads"]

    pod = _cw_rate(leads[leads["created_via_channel"] == Channel.PODCAST.value])
    lin = _cw_rate(leads[leads["created_via_channel"] == Channel.LINKEDIN_PAID.value])

    mwr = leads[leads["seed_label_theme_primary"] == Theme.MANUAL_WORK_REDUCTION.value]
    maya_mwr = _cw_rate(mwr[mwr["persona"] == Persona.MAYA.value])
    rest_mwr = _cw_rate(mwr[mwr["persona"] != Persona.MAYA.value])

    path = leads[leads["lead_id"].isin(data["f3_path"])]
    path_cw, overall_cw = _cw_rate(path), _cw_rate(leads)

    bf = leads[leads["first_touch_utm_campaign"] == _BROAD_FUNNEL]

    comp = leads[leads["seed_label_theme_primary"] == Theme.COMPLIANCE_SECURITY.value]
    pat_comp = _cw_rate(comp[comp["persona"] == Persona.PATRICIA.value])
    rest_comp = _cw_rate(comp[comp["persona"] != Persona.PATRICIA.value])

    st.subheader("Key findings")
    st.caption(
        "Four headline patterns ICA surfaces from 2,500 inbound leads — "
        "what to amplify, and what is quietly expensive."
    )

    cards = [
        (
            "Finding 1 — Channel quality surprise",
            f"{_ratio(pod, lin):.0f}× closed-won gap",
            f"Podcast converts at {pod:.0%} against LinkedIn paid at {lin:.0%}. "
            "The lowest-volume channel is the highest-value one.",
        ),
        (
            "Finding 2 — Message–persona resonance",
            f"{_ratio(maya_mwr, rest_mwr):.1f}× resonance lift",
            f"RevOps leaders on a manual-work-reduction message close at "
            f"{maya_mwr:.0%} — versus {rest_mwr:.1%} for that message to "
            "every other persona.",
        ),
        (
            "Finding 3 — Multi-touch journey",
            f"{_ratio(path_cw, overall_cw):.1f}× journey lift",
            f"Podcast → blog → demo inside two weeks closes at {path_cw:.0%}, "
            f"against a {overall_cw:.1%} dataset-wide rate.",
        ),
        (
            "Finding 4 — ICP fit vs volume",
            f"{_bad_share(bf):.0%} bad-outcome share",
            f"The largest LinkedIn campaign ({len(bf)} leads) is the worst-fit "
            "one — most of that spend disqualifies or ghosts.",
        ),
    ]
    columns = st.columns(2)
    for i, (title, value, text) in enumerate(cards):
        with columns[i % 2], st.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(f"### {value}")
            st.caption(text)

    st.subheader("Additional patterns surfaced")
    with st.container(border=True):
        st.markdown("**Finding 5 — Compliance resonance**  ·  *secondary*")
        st.write(
            f"Enterprise IT buyers on a compliance/security message close at "
            f"{pat_comp:.0%} — a {_ratio(pat_comp, rest_comp):.0f}× lift over "
            f"that message to other personas ({rest_comp:.1%}). A narrower, "
            "lower-volume cell than F1–F4, so it is surfaced here rather than "
            "headlined above."
        )
        st.caption(_THEME_NOTE)


def _finding_metrics(*specs: tuple[str, str, str | None]) -> None:
    """Render a row of st.metric cards. Each spec is (label, value, sub-note);
    the sub-note, when present, is folded into the metric label (st.metric's
    delta slot is reserved for signed changes — a lead count is not one)."""
    for column, (label, value, note) in zip(st.columns(len(specs)), specs, strict=True):
        column.metric(f"{label}  ·  {note}" if note else label, value)


def render_findings(data: dict) -> None:
    leads = data["leads"]

    st.subheader("Finding 1 — Channel quality surprise")
    st.bar_chart(_cw_by(leads, "created_via_channel"), x="created_via_channel",
                 y=_CW_COL, height=260)
    pod_leads = leads[leads["created_via_channel"] == Channel.PODCAST.value]
    lin_leads = leads[leads["created_via_channel"] == Channel.LINKEDIN_PAID.value]
    _finding_metrics(
        ("Podcast closed-won", f"{_cw_rate(pod_leads):.0%}", f"{len(pod_leads)} leads"),
        ("LinkedIn paid closed-won", f"{_cw_rate(lin_leads):.0%}", f"{len(lin_leads)} leads"),
        ("Quality gap", f"{_ratio(_cw_rate(pod_leads), _cw_rate(lin_leads)):.1f}×", None),
    )
    st.caption(
        "The high-volume paid channel is the low-quality one. Budget tends to "
        "follow volume; pipeline follows the podcast."
    )
    st.divider()

    st.subheader("Finding 2 — Message–persona resonance")
    mwr = leads[leads["seed_label_theme_primary"] == Theme.MANUAL_WORK_REDUCTION.value].copy()
    mwr["Persona"] = mwr["persona"].map(_PERSONA_LABEL)
    st.bar_chart(_cw_by(mwr, "Persona"), x="Persona", y=_CW_COL, height=260)
    maya = _cw_rate(mwr[mwr["persona"] == Persona.MAYA.value])
    rest = _cw_rate(mwr[mwr["persona"] != Persona.MAYA.value])
    _finding_metrics(
        ("Maya × manual-work-reduction", f"{maya:.0%}", None),
        ("Same message, other personas", f"{rest:.1%}", None),
        ("Resonance lift", f"{_ratio(maya, rest):.1f}×", None),
    )
    st.caption(
        "The manual-work-reduction message is not universally strong — it is "
        "strong for RevOps leaders specifically. Same words, different buyer, "
        "roughly nine times the conversion."
    )
    st.caption(_THEME_NOTE)
    st.divider()

    st.subheader("Finding 3 — Multi-touch journey")
    path = leads[leads["lead_id"].isin(data["f3_path"])]
    other_pod = leads[
        (leads["created_via_channel"] == Channel.PODCAST.value)
        & (~leads["lead_id"].isin(data["f3_path"]))
    ]
    f3_df = pd.DataFrame({
        "Segment": ["Podcast→blog→demo path", "Other podcast leads", "Dataset overall"],
        _CW_COL: [_cw_rate(path), _cw_rate(other_pod), _cw_rate(leads)],
    })
    st.bar_chart(f3_df, x="Segment", y=_CW_COL, height=260)
    _finding_metrics(
        ("Path closed-won", f"{_cw_rate(path):.0%}", f"{len(path)} leads"),
        ("Dataset overall", f"{_cw_rate(leads):.1%}", None),
        ("Journey lift", f"{_ratio(_cw_rate(path), _cw_rate(leads)):.1f}×", None),
    )
    st.caption(
        "A specific three-step journey — podcast first touch, a blog read, a "
        "demo request, all inside two weeks — is the highest-converting path "
        "in the dataset. It is a sequence, not a single channel."
    )
    st.divider()

    st.subheader("Finding 4 — ICP fit vs volume")
    campaigns = leads[leads["first_touch_utm_campaign"].notna()]
    volume = campaigns.groupby("first_touch_utm_campaign").size().rename("Leads").reset_index()
    st.bar_chart(volume, x="first_touch_utm_campaign", y="Leads", height=260)
    bf = leads[leads["first_touch_utm_campaign"] == _BROAD_FUNNEL]
    _finding_metrics(
        ("Broad-funnel campaign", f"{len(bf)} leads", "largest LinkedIn campaign"),
        ("Bad-outcome share", f"{_bad_share(bf):.0%}", None),
        ("Mean ICP fit", f"{bf['icp_fit_score'].mean():.0f}",
         f"vs {leads['icp_fit_score'].mean():.0f} dataset-wide"),
    )
    st.caption(
        "The biggest LinkedIn campaign by spend is the worst by fit. Most of "
        "its leads disqualify or ghost — raw volume is masking low-quality "
        "pipeline."
    )
    st.divider()

    st.subheader("Finding 5 — Compliance resonance  ·  secondary")
    comp = leads[leads["seed_label_theme_primary"] == Theme.COMPLIANCE_SECURITY.value].copy()
    comp["Persona"] = comp["persona"].map(_PERSONA_LABEL)
    st.bar_chart(_cw_by(comp, "Persona"), x="Persona", y=_CW_COL, height=240)
    pat = _cw_rate(comp[comp["persona"] == Persona.PATRICIA.value])
    rest = _cw_rate(comp[comp["persona"] != Persona.PATRICIA.value])
    _finding_metrics(
        ("Patricia × compliance", f"{pat:.0%}", None),
        ("Same message, other personas", f"{rest:.1%}", None),
        ("Resonance lift", f"{_ratio(pat, rest):.0f}×", None),
    )
    st.caption(
        "The same persona–message resonance as Finding 2, on a narrower cell: "
        "a compliance/security message lands with enterprise IT buyers. "
        "Secondary — lower volume, surfaced for completeness."
    )
    st.caption(_THEME_NOTE)


def render_explore(data: dict) -> None:
    leads = data["leads"].copy()
    leads["Persona"] = leads["persona"].map(_PERSONA_LABEL)

    st.subheader("Segment explorer")
    st.caption(
        "Every persona × primary-theme cell. The engineered resonance cells "
        "(Maya × manual-work-reduction, Patricia × compliance) light up here."
    )
    metric = st.radio("Cell value", [_CW_COL, "Lead count"], horizontal=True)
    if metric == _CW_COL:
        grid = leads.groupby(["Persona", "seed_label_theme_primary"])["won"].mean()
        value_format = ".0%"
    else:
        grid = leads.groupby(["Persona", "seed_label_theme_primary"]).size()
        value_format = "d"
    grid = grid.rename("value").reset_index()

    chart = (
        alt.Chart(grid)
        .mark_rect()
        .encode(
            x=alt.X("seed_label_theme_primary:N", title="Primary theme"),
            y=alt.Y("Persona:N", title="Persona"),
            color=alt.Color("value:Q", title=metric, scale=alt.Scale(scheme="blues")),
            tooltip=[
                alt.Tooltip("Persona:N"),
                alt.Tooltip("seed_label_theme_primary:N", title="Theme"),
                alt.Tooltip("value:Q", title=metric, format=value_format),
            ],
        )
        .properties(width="container", height=340)
    )
    st.altair_chart(chart)
    st.caption(_THEME_NOTE)


def render_actions() -> None:
    st.subheader("GTM action artifacts")
    st.info("Reserved for the signature feature — not yet built.")
    st.markdown(
        "This tab will surface **auto-generated GTM action artifacts**: content "
        "briefs, ad-copy variants, and ICP refinements that Claude drafts from "
        "the resonance themes ICA surfaces. It closes the loop from *insight* "
        "(the findings in the other tabs) to *action* a GTM team can ship.\n\n"
        "It lands with the signature-feature update, which also folds in the "
        "CP4 resonance-extraction layer — replacing the seeded theme labels "
        "used today with themes Claude extracts from the raw form answers and "
        "sales notes."
    )


def main() -> None:
    st.title("ICA · Inbound Cause Analysis")
    st.caption(
        "Why inbound leads convert — and which channels, messages, and "
        "journeys a GTM team should amplify."
    )
    data = load_dataset()
    overview, findings, explore, actions = st.tabs(
        ["Overview", "Findings", "Explore", "Actions"]
    )
    with overview:
        render_overview(data)
    with findings:
        render_findings(data)
    with explore:
        render_explore(data)
    with actions:
        render_actions()


main()
