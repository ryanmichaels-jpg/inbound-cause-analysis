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

import uuid
from datetime import date, datetime, timedelta

import numpy as np

from ica.generator.content_library import assets_by_channel, assets_for
from ica.generator.copy_bank import form_answer, form_question
from ica.schema import FormSubmission, PartialLead, Touchpoint
from ica.taxonomy import (
    DEFAULT_SEED,
    F3_PATH_WITHIN_DAYS,
    F3_TARGET_PATH_COUNT,
    PERSONA_THEME_SHARE,
    TIME_WINDOW_END,
    Channel,
    EventType,
    FormType,
    Persona,
    Theme,
)

__all__ = ["build_journeys"]

_TOUCHPOINT_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "ica.touchpoint")
_SUBMISSION_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "ica.form-submission")

_THEME_INDEX = {theme: i for i, theme in enumerate(Theme)}

# First-touch event_type per channel.
_FIRST_TOUCH_EVENT: dict[Channel, EventType] = {
    Channel.PODCAST: EventType.PODCAST_LISTEN,
    Channel.LINKEDIN_PAID: EventType.PAGE_VIEW,
    Channel.ORGANIC_SEARCH: EventType.PAGE_VIEW,
    Channel.NEWSLETTER: EventType.EMAIL_CLICK,
    Channel.WEBINAR: EventType.WEBINAR_REGISTER,
    Channel.COMPARISON_PAGE: EventType.PAGE_VIEW,
}

# utm_source / utm_medium per channel (data-world.md §7); set on the
# first-touch touchpoint only.
_CHANNEL_UTM: dict[Channel, tuple[str, str]] = {
    Channel.PODCAST: ("podcast", "audio"),
    Channel.LINKEDIN_PAID: ("linkedin", "cpc"),
    Channel.ORGANIC_SEARCH: ("google", "organic"),
    Channel.NEWSLETTER: ("newsletter", "email"),
    Channel.WEBINAR: ("webinar", "event"),
    Channel.COMPARISON_PAGE: ("g2", "referral"),
}

# Non-F3 lead-creating form types and weights. F3 leads are forced to
# demo_request (the path needs a demo_request touchpoint).
_FORM_TYPES: tuple[FormType, ...] = (
    FormType.CONTENT_DOWNLOAD,
    FormType.DEMO_REQUEST,
    FormType.CONTACT_SALES,
    FormType.NEWSLETTER_SIGNUP,
    FormType.COMPARISON_PAGE_CTA,
    FormType.WEBINAR_REGISTER,
)
_FORM_TYPE_WEIGHTS = np.array([0.35, 0.20, 0.15, 0.12, 0.10, 0.08])


def _stratified_theme_counts(pop: int, shares: dict[Theme, float]) -> dict[Theme, int]:
    """Exact integer per-theme counts for `pop` leads — largest-remainder in
    integer-percent arithmetic, Theme-enum-order tiebreak. Sums to pop."""
    pct = {theme: round(shares[theme] * 100) for theme in shares}
    numerator = {theme: pop * pct[theme] for theme in pct}
    counts = {theme: numerator[theme] // 100 for theme in pct}
    deficit = pop - sum(counts.values())
    ranked = sorted(
        pct, key=lambda theme: (-(numerator[theme] % 100), _THEME_INDEX[theme])
    )
    for theme in ranked[:deficit]:
        counts[theme] += 1
    return counts


def _assign_primary_themes(leads: list[PartialLead], rng: np.random.Generator) -> None:
    """Stratified seed_label_theme_primary per PERSONA_THEME_SHARE — exact
    cell counts, shuffled within each persona to decorrelate theme from the
    channel assignment already on the leads."""
    by_persona: dict[Persona, list[PartialLead]] = {p: [] for p in Persona}
    for lead in leads:
        by_persona[lead.persona].append(lead)
    for persona, group in by_persona.items():
        counts = _stratified_theme_counts(len(group), PERSONA_THEME_SHARE[persona])
        themes: list[Theme] = []
        for theme, count in counts.items():
            themes.extend([theme] * count)
        order = rng.permutation(len(group))
        for slot, theme in zip(order, themes, strict=True):
            group[int(slot)].seed_label_theme_primary = theme


def _select_f3_path_lead_ids(
    leads: list[PartialLead], rng: np.random.Generator
) -> set[str]:
    """Pick exactly F3_TARGET_PATH_COUNT podcast leads with enough in-window
    headroom for the 14-day path."""
    end = date.fromisoformat(TIME_WINDOW_END)
    cutoff = datetime(end.year, end.month, end.day) - timedelta(
        days=F3_PATH_WITHIN_DAYS
    )
    eligible = [
        lead
        for lead in leads
        if lead.created_via_channel == Channel.PODCAST and lead.created_at < cutoff
    ]
    chosen = rng.choice(len(eligible), size=F3_TARGET_PATH_COUNT, replace=False)
    return {eligible[int(i)].lead_id for i in chosen}


def _gap(rng: np.random.Generator, lo_days: int, hi_days: int) -> timedelta:
    return timedelta(
        days=int(rng.integers(lo_days, hi_days)), hours=int(rng.integers(0, 24))
    )


def _pick_asset(channel: Channel, theme: Theme, rng: np.random.Generator) -> str:
    """A content asset slug for `channel`, theme-matched where the channel
    carries one for that theme."""
    matching = assets_for(channel, theme)
    pool = matching if matching else assets_by_channel(channel)
    return pool[int(rng.integers(len(pool)))].slug


def _touchpoint(
    lead: PartialLead,
    seq: int,
    ts: datetime,
    channel: Channel,
    event_type: EventType,
    *,
    content_asset_slug: str | None = None,
    is_first: bool = False,
    is_last: bool = False,
) -> Touchpoint:
    utm_source = utm_medium = utm_campaign = None
    if is_first:
        utm_source, utm_medium = _CHANNEL_UTM[channel]
        # First-touch contract: the touchpoint replicates the lead's
        # denormalized first-touch campaign exactly.
        utm_campaign = lead.first_touch_utm_campaign
    return Touchpoint(
        touchpoint_id=str(uuid.uuid5(_TOUCHPOINT_NS, f"{lead.lead_id}:{seq}")),
        lead_id=lead.lead_id,
        ts=ts,
        channel=channel,
        event_type=event_type,
        content_asset_slug=content_asset_slug,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        is_first_touch=is_first,
        is_last_touch=is_last,
    )


def _build_one_journey(
    lead: PartialLead, is_f3: bool, rng: np.random.Generator
) -> tuple[list[Touchpoint], FormSubmission]:
    channel = lead.created_via_channel
    theme = lead.seed_label_theme_primary

    # The form-answer snippet fixes free_text_answer, ground_truth_themes,
    # and the lead's secondary theme in one draw.
    snippet = form_answer(lead.persona, channel, theme, rng)
    lead.seed_label_theme_secondary = snippet.secondary_theme

    # (ts, channel, event_type, content_asset_slug) specs, chronological.
    first_asset = (
        lead.first_touch_utm_campaign
        if channel == Channel.LINKEDIN_PAID
        else _pick_asset(channel, theme, rng)
    )
    specs: list[tuple[datetime, Channel, EventType, str | None]] = [
        (lead.created_at, channel, _FIRST_TOUCH_EVENT[channel], first_asset)
    ]

    if is_f3:
        # podcast first touch -> organic_search blog -> demo_request, <=14d.
        blog_ts = lead.created_at + _gap(rng, 3, 8)
        specs.append(
            (
                blog_ts,
                Channel.ORGANIC_SEARCH,
                EventType.PAGE_VIEW,
                _pick_asset(Channel.ORGANIC_SEARCH, theme, rng),
            )
        )
        specs.append(
            (blog_ts + _gap(rng, 2, 6), Channel.ORGANIC_SEARCH, EventType.DEMO_REQUEST, None)
        )
        form_type = FormType.DEMO_REQUEST
    else:
        # Single-channel: first touch + 0-3 page views + a form submission.
        ts = lead.created_at
        for _ in range(int(rng.integers(0, 4))):
            ts = ts + _gap(rng, 1, 6)
            specs.append((ts, channel, EventType.PAGE_VIEW, None))
        ts = ts + _gap(rng, 1, 6)
        form_type = _FORM_TYPES[
            int(rng.choice(len(_FORM_TYPES), p=_FORM_TYPE_WEIGHTS))
        ]
        event = (
            EventType.DEMO_REQUEST
            if form_type == FormType.DEMO_REQUEST
            else EventType.FORM_SUBMIT
        )
        specs.append((ts, channel, event, None))

    last = len(specs) - 1
    touchpoints = [
        _touchpoint(
            lead,
            seq,
            ts,
            ch,
            event,
            content_asset_slug=asset,
            is_first=(seq == 0),
            is_last=(seq == last),
        )
        for seq, (ts, ch, event, asset) in enumerate(specs)
    ]
    form_tp = touchpoints[-1]
    submission = FormSubmission(
        submission_id=str(uuid.uuid5(_SUBMISSION_NS, lead.lead_id)),
        lead_id=lead.lead_id,
        touchpoint_id=form_tp.touchpoint_id,
        ts=form_tp.ts,
        form_type=form_type,
        free_text_question=form_question(form_type, rng),
        free_text_answer=snippet.text,
        ground_truth_themes=snippet.ground_truth_themes,
    )
    return touchpoints, submission


def build_journeys(
    leads: list[PartialLead],
    seed: int = DEFAULT_SEED,
) -> tuple[list[Touchpoint], list[FormSubmission]]:
    """Assign seed themes and synthesize touchpoints + form submissions.

    Mutates each PartialLead (sets seed_label_theme_primary/secondary) and
    returns the touchpoint and form_submission row collections.
    """
    rng = np.random.default_rng(seed)
    _assign_primary_themes(leads, rng)
    f3_ids = _select_f3_path_lead_ids(leads, rng)

    touchpoints: list[Touchpoint] = []
    submissions: list[FormSubmission] = []
    for lead in leads:
        lead_tps, submission = _build_one_journey(lead, lead.lead_id in f3_ids, rng)
        touchpoints.extend(lead_tps)
        submissions.append(submission)
    return touchpoints, submissions
