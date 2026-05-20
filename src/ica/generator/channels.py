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
