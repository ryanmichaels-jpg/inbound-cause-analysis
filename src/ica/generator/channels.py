"""First-touch channel, campaign, and timestamp assignment.

Consumes the list[PartialLead] from generator/personas.py (2,500 leads
with persona + firmographics + identity set) and fills created_via_channel,
created_at, and — for linkedin_paid leads — first_touch_utm_campaign.
Output is the same list[PartialLead], enriched. Themes, touchpoint rows,
and outcomes are NOT set here.

See `docs/data-world.md` §1 (time window), §7 (channels, volumes, linkedin
campaign mix) and §8 (LinkedIn ad campaigns), and `src/ica/taxonomy.py`
§5/§8 for the canonical values this module assigns against.

TODO (read before implementing — sanity check the plan):

== Locked inputs (pull from taxonomy.py — do not redefine) ==

Channel volumes (CHANNEL_TARGET_VOLUME, sum = 2,500):
    podcast 200 · linkedin_paid 1,000 · organic_search 400 ·
    newsletter 300 · webinar 300 · comparison_page 300
  Canonical channel name is `newsletter` (Channel.NEWSLETTER).

linkedin_paid sub-campaigns — all three are LOCKED Gate 1 values, in
docs/data-world.md §7 ("Within-channel campaign mix — linkedin_paid"
table) and §8 ("LinkedIn ad campaigns" table), and in taxonomy
LINKEDIN_CAMPAIGN_VOLUME / LINKEDIN_CAMPAIGN_PERSONA_MIX. Spelled out
here for visibility (the prior header collapsed them to "etc."):

  linkedin_q2_broad_funnel — 600 leads
    persona mix: Carlos 55 / Patricia 30 / David 10 / Maya 5
    theme: generic/mixed. Finding 4 vehicle — deliberately the most
    non-ICP-skewed campaign (Carlos + Patricia = 85%).
  linkedin_q2_enterprise — 250 leads
    persona mix: Patricia 60 / David 15 / Maya 15 / Carlos 10
    theme: tool_sprawl_consolidation. Enterprise / ABM-style targeting
    (Patricia = Enterprise IT Buyer). Healthier than broad_funnel:
    Carlos drops 55 -> 10, strong-fit David + Maya rise 15 -> 30.
  linkedin_q2_revops_targeted — 150 leads
    persona mix: Maya 55 / David 25 / Carlos 12 / Patricia 8
    theme: manual_work_reduction. ICP-tight — 80% strong-fit
    (Maya + David); targets Maya on her signature theme.

  None of these are new v1 decisions; all are locked in §7/§8 +
  taxonomy. "Healthier" = the enterprise and revops_targeted mixes
  over-index strong-fit personas relative to broad_funnel, which is why
  broad_funnel alone is Finding 4's low-ICP vehicle.

== Assignment approach ==

Step A — linkedin_paid (1,000 leads). NOT affinity-driven; the campaign
persona mixes above are locked. For each campaign, compute exact
per-persona integer counts = volume * LINKEDIN_CAMPAIGN_PERSONA_MIX,
resolving fractional counts (enterprise David/Maya at 37.5; revops
Maya/David at 82.5/37.5) by largest-remainder with a deterministic
tiebreak (proposed: Persona enum order). Pull exactly those counts of
each persona from the persona pool; set created_via_channel =
linkedin_paid and first_touch_utm_campaign = <campaign slug>.
  Feasibility check (done): linkedin consumes Maya 151 / David 134 /
  Patricia 342 / Carlos 373 — derived from the locked mixes plus the
  .5 roundings — all within population 700/550/650/600.

Step B — the other 5 channels (1,500 leads; with the proposed tiebreak
the remainder is Maya 549 / David 416 / Patricia 308 / Carlos 227).
Channel-conditioned via greedy weighted-fill — for each channel, draw
its leads from the remaining persona budgets weighted by
CHANNEL_PERSONA_AFFINITY (linear rank weights 4/3/2/1), decrementing
budgets and dropping exhausted personas. Hits channel volumes and
persona totals exactly by construction (total budget == total volume).
Fill the most affinity-distinctive channels first so the last-filled
channel's residual still reads plausibly. first_touch_utm_campaign
stays None for these leads.

Step C — created_at for all 2,500. Sample from the single locked §1
envelope: +5% MoM growth trend * weekday-heavier weekly seasonality,
over 2026-01-01 .. 2026-06-30 (TIME_WINDOW_START/END). Build a per-day
weight curve, sample a date per lead, add a random intra-day time.
Seeded (DEFAULT_SEED).

== Decisions locked at review (Q1-Q4) ==

Q1 — RESOLVED. first_touch_utm_campaign (TEXT NULL) was added to the
leads schema / Lead / PartialLead in commit 9b20e85. channels.py fills
it for the 1,000 linkedin leads with the campaign slug; non-linkedin
leads keep None. PartialLead.to_lead() enforces non-None for
linkedin_paid leads. Finding 4's group_by("utm_campaign") drops NULL
groups (pandas default), leaving broad_funnel (600) the unambiguous top
campaign; the F4 `db` test helper maps its lookup onto this column.

Q2 — APPROVED. Single §1 envelope for all created_at draws; no
per-channel temporal skew. The linkedin "q2" campaign naming is
branding, not a timing constraint. See Step C.

Q3 — APPROVED. Channel-conditioned persona mix via greedy weighted-fill
(not an IPF solver). See Step B. No Finding hard-constrains the
non-linkedin per-channel mix — it is realism texture only.

Q4 — CONFIRMED. channels.py is lead-level only: it emits NO touchpoint
rows. journeys.py owns the full touchpoint sequence including the
first-touch touchpoint, whose ts must equal the lead's created_at and
whose utm_campaign must equal first_touch_utm_campaign — the lead-level
fields are the single source of truth those touchpoint values copy.
Cross-module note for journeys.py: Finding 3's podcast -> organic_search
-> demo path needs ~14 days of in-window headroom, so F3-path leads must
be drawn from podcast leads created on/before ~2026-06-16; the §1
envelope spreads podcast created_at across the window so enough qualify.

== What this module does NOT do ==
- No touchpoint rows; no utm_source/medium/content/referrer (journeys.py).
- No seed_label_theme_primary/secondary (journeys.py).
- No outcomes; no Finding 1 channel-quality CW skew (outcomes.py).
- No content-asset assignment beyond the linkedin campaign slug.

Output: list[PartialLead] with created_via_channel, created_at, and
first_touch_utm_campaign (linkedin only) populated; themes still None.
"""

from datetime import date, datetime, timedelta

import numpy as np

from ica.schema import PartialLead
from ica.taxonomy import (
    CHANNEL_PERSONA_AFFINITY,
    CHANNEL_TARGET_VOLUME,
    DEFAULT_SEED,
    LINKEDIN_CAMPAIGN_PERSONA_MIX,
    LINKEDIN_CAMPAIGN_VOLUME,
    LINKEDIN_CAMPAIGNS,
    TIME_WINDOW_END,
    TIME_WINDOW_START,
    TOTAL_LEADS_DEFAULT,
    Channel,
    Persona,
)

__all__ = ["assign_channels"]

# Affinity rank (strongest -> weakest) -> Step B sampling weight.
_RANK_WEIGHT = (4, 3, 2, 1)

# Persona enum order — the deterministic tiebreak for largest-remainder.
_PERSONA_INDEX = {persona: i for i, persona in enumerate(Persona)}

# Step B fill order. podcast first: it is the narrative-critical high-quality
# channel and should get a clean strong-fit draw on full persona budgets.
# comparison_page last: pure affinity-weighted greedy leaves a structurally
# Patricia-heavy residual (Patricia is low-affinity on every channel, so she
# accumulates), and G2 / comparison-page traffic plausibly skews toward
# methodical enterprise evaluators — so comparison_page is the most natural
# home for that residual. The five volumes sum to 1,500 == the post-linkedin
# persona budget, so the fill is exact by construction.
# The Patricia-heavy / David-light comparison_page residual is expected
# greedy-fill behavior — reviewed and ACCEPTED AS-IS. Do not "correct" it
# toward strict 4/3/2/1 affinity in a later refactor; no Finding constrains
# this mix and the residual is a realistic natural-distortion observation.
_STEP_B_CHANNEL_ORDER = (
    Channel.PODCAST,
    Channel.ORGANIC_SEARCH,
    Channel.NEWSLETTER,
    Channel.WEBINAR,
    Channel.COMPARISON_PAGE,
)

# channel -> {persona -> affinity weight}, precomputed for the Step B channels.
_AFFINITY_WEIGHT: dict[Channel, dict[Persona, int]] = {
    channel: {
        persona: _RANK_WEIGHT[CHANNEL_PERSONA_AFFINITY[channel].index(persona)]
        for persona in Persona
    }
    for channel in _STEP_B_CHANNEL_ORDER
}

# data-world.md §1 created_at envelope.
_MOM_GROWTH = 1.05
_WEEKEND_WEIGHT = 0.5


def _campaign_persona_counts(volume: int, mix: dict[Persona, float]) -> dict[Persona, int]:
    """Exact integer per-persona counts for a linkedin campaign of `volume`
    leads allocated by `mix`.

    Largest-remainder in integer (percent) arithmetic, so floating-point dust
    can never flip a .5 tie; ties are broken by Persona enum order. The mix
    fractions are whole-percent values, so the * 100 scaling is exact.
    """
    percent = {persona: round(mix[persona] * 100) for persona in mix}
    numerator = {persona: volume * percent[persona] for persona in percent}
    counts = {persona: numerator[persona] // 100 for persona in percent}
    deficit = volume - sum(counts.values())
    ranked = sorted(
        percent,
        key=lambda persona: (-(numerator[persona] % 100), _PERSONA_INDEX[persona]),
    )
    for persona in ranked[:deficit]:
        counts[persona] += 1
    return counts


def _created_at_series(rng: np.random.Generator, n: int) -> list[datetime]:
    """`n` first-touch timestamps sampled from the data-world §1 envelope:
    +5% month-over-month growth * weekday-heavier weekly seasonality."""
    start = date.fromisoformat(TIME_WINDOW_START)
    end = date.fromisoformat(TIME_WINDOW_END)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    weights = np.array(
        [
            _MOM_GROWTH ** ((d.year - start.year) * 12 + d.month - start.month)
            * (_WEEKEND_WEIGHT if d.weekday() >= 5 else 1.0)
            for d in days
        ],
        dtype=float,
    )
    weights /= weights.sum()
    day_index = rng.choice(len(days), size=n, p=weights)
    seconds = rng.integers(0, 86_400, size=n)
    out: list[datetime] = []
    for day_i, sec in zip(day_index, seconds, strict=True):
        day = days[int(day_i)]
        out.append(datetime(day.year, day.month, day.day) + timedelta(seconds=int(sec)))
    return out


def assign_channels(
    leads: list[PartialLead],
    seed: int = DEFAULT_SEED,
) -> list[PartialLead]:
    """Fill created_via_channel, created_at, and (linkedin_paid only)
    first_touch_utm_campaign on each PartialLead. See the module docstring
    for the locked inputs and the three-step approach.

    Mutates the PartialLeads in place and returns the same list.
    """
    if len(leads) != TOTAL_LEADS_DEFAULT:
        raise ValueError(
            f"assign_channels expects the {TOTAL_LEADS_DEFAULT}-lead world; "
            f"got {len(leads)}"
        )
    rng = np.random.default_rng(seed)

    pools: dict[Persona, list[PartialLead]] = {persona: [] for persona in Persona}
    for lead in leads:
        pools[lead.persona].append(lead)
    cursor = {persona: 0 for persona in Persona}

    # Step A — linkedin_paid: locked campaign volumes and persona mixes.
    for campaign in LINKEDIN_CAMPAIGNS:
        counts = _campaign_persona_counts(
            LINKEDIN_CAMPAIGN_VOLUME[campaign],
            LINKEDIN_CAMPAIGN_PERSONA_MIX[campaign],
        )
        for persona, count in counts.items():
            for _ in range(count):
                lead = pools[persona][cursor[persona]]
                cursor[persona] += 1
                lead.created_via_channel = Channel.LINKEDIN_PAID
                lead.first_touch_utm_campaign = campaign

    # Step B — the other five channels: greedy affinity-weighted fill.
    for channel in _STEP_B_CHANNEL_ORDER:
        weight_of = _AFFINITY_WEIGHT[channel]
        for _ in range(CHANNEL_TARGET_VOLUME[channel]):
            available = [p for p in Persona if cursor[p] < len(pools[p])]
            weights = np.array([weight_of[p] for p in available], dtype=float)
            weights /= weights.sum()
            persona = available[int(rng.choice(len(available), p=weights))]
            lead = pools[persona][cursor[persona]]
            cursor[persona] += 1
            lead.created_via_channel = channel

    # Step C — created_at for every lead, from the §1 envelope.
    for lead, timestamp in zip(leads, _created_at_series(rng, len(leads)), strict=True):
        lead.created_at = timestamp

    return leads
