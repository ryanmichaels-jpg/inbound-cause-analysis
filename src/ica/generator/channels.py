"""First-touch channel, campaign, and timestamp assignment.

Consumes the list[PartialLead] from generator/personas.py (2,500 leads
with persona + firmographics + identity set) and fills created_via_channel,
created_at, and — for linkedin_paid leads — first_touch_utm_campaign.
Output is the same list[PartialLead], enriched. Themes, touchpoint rows,
and outcomes are NOT set here.

See `docs/data-world.md` §1 (time window) and §7 (channels, volumes,
linkedin campaign mix), and `src/ica/taxonomy.py` §5/§8 for the canonical
values this module assigns against.

TODO (read before implementing — sanity check the plan):

== Locked inputs (pull from taxonomy.py — do not redefine) ==

Channel volumes (CHANNEL_TARGET_VOLUME, sum = 2,500):
    podcast 200 · linkedin_paid 1,000 · organic_search 400 ·
    newsletter 300 · webinar 300 · comparison_page 300
  NOTE: the canonical channel name is `newsletter` (Channel.NEWSLETTER),
  not "newsletter_referral" — flagging a slip in the kickoff brief.

linkedin_paid sub-campaigns (LINKEDIN_CAMPAIGN_VOLUME, sum = 1,000):
    linkedin_q2_broad_funnel 600 · linkedin_q2_enterprise 250 ·
    linkedin_q2_revops_targeted 150
  Per-campaign persona mix: LINKEDIN_CAMPAIGN_PERSONA_MIX.

== Assignment approach ==

Step A — linkedin_paid (1,000 leads). NOT affinity-driven; the campaign
persona mixes are locked. For each campaign, compute exact per-persona
integer counts = volume * LINKEDIN_CAMPAIGN_PERSONA_MIX, resolving
fractional counts (enterprise David/Maya at 37.5; revops Maya/David at
82.5/37.5) by largest-remainder with a deterministic tiebreak (proposed:
Persona enum order). Pull exactly those counts of each persona from the
persona pool; set created_via_channel = linkedin_paid and
first_touch_utm_campaign = <campaign slug>.
  Feasibility check (done): linkedin consumes Maya 151 / David 134 /
  Patricia 342 / Carlos 373 — all within population 700/550/650/600.

Step B — the other 5 channels (1,500 leads; with the proposed tiebreak
the remainder is Maya 549 / David 416 / Patricia 308 / Carlos 227).
Channel-conditioned, not uniform — see Q3. Proposed: greedy weighted-fill
— for each channel, draw its leads from the remaining persona budgets
weighted by CHANNEL_PERSONA_AFFINITY, decrementing budgets and dropping
exhausted personas. Hits channel volumes and persona totals exactly by
construction (total budget == total volume). Fill the most affinity-
distinctive channels first so the last-filled channel's residual still
reads plausibly.

Step C — created_at for all 2,500. Sample from the locked §1 envelope:
+5% MoM growth trend * weekday-heavier weekly seasonality, over
2026-01-01 .. 2026-06-30 (TIME_WINDOW_START/END). Build a per-day weight
curve, sample a date per lead, add a random intra-day time. Seeded
(DEFAULT_SEED).

== Open questions surfaced for review ==

Q1 — Campaign queryability (needs a decision BEFORE implementation).
Finding 4's test does db.leads.group_by("utm_campaign"); the leads table
has no campaign column (utm_campaign lives only on touchpoints, built
later by journeys.py). Since F4 must be reproducible from channels-layer
output alone, recommend adding a denormalized first_touch_utm_campaign
(TEXT, nullable) to the leads table / Lead / PartialLead — an exact
parallel to created_via_channel. This is a small schema.py commit BEFORE
channels.py implementation. (Minor: it must be a trailing defaulted field
so dataclass field ordering stays valid.) channels.py fills it for the
1,000 linkedin leads; non-linkedin leads stay NULL at this stage (their
per-content-asset campaigns attach downstream). F4's group_by then drops
NULL groups (pandas default), leaving broad_funnel (600) the unambiguous
top campaign. Naming: first_touch_utm_campaign for consistency with
created_via_channel; F4's `db` test helper maps its group_by onto it.

Q2 — Timestamp distribution. Recommend ALL channels draw created_at from
the single locked §1 envelope (no per-channel skew). The linkedin "q2"
campaign names imply Q2 timing, but taking that literally contradicts
§1's dataset-wide +5% MoM trend — linkedin is 40% of volume, so a hard
Q2 cluster becomes a Q2 cliff, not a gentle trend. Recommend treating
"q2" as campaign branding, not a timing constraint. Per-channel texture
(podcast clustering near episode releases, newsletter aligned to edition
months) is a deferrable realism enhancement — flagged, not planned.
Decide: uniform §1 envelope (recommended) vs per-channel skew.

Q3 — Per-channel persona mix: channel-conditioned, not uniform-by-
population. data-world §7 mandates affinity-conditioned channel
assignment, and uniform would erase channel character (podcast, the
strong-fit channel, should over-index Maya/David). Note: no Finding
hard-constrains the non-linkedin per-channel persona mix — it is realism
texture only — which is why Step B uses the simpler greedy weighted-fill
over an IPF matrix-balancing solver. IPF is the alternative if strict
affinity fidelity is wanted; greedy is recommended (exact margins by
construction, smaller bug surface). Affinity->weight mapping proposed as
linear rank weights (4/3/2/1); confirm or specify steeper.

Q4 — Other items spotted:
- channels.py is lead-level only — it emits NO touchpoint rows. The
  first-touch touchpoint (ts == created_at, is_first_touch TRUE) is built
  by journeys.py, which owns the full touchpoint sequence. Confirm this
  module boundary.
- created_at is the canonical first-touch timestamp; journeys.py must
  make the is_first_touch touchpoint's ts equal it.
- Finding 3's podcast->organic_search->demo path needs ~14 days of
  in-window headroom; the §1 envelope spreads podcast created_at across
  Jan–Jun, so enough podcast leads qualify — noting the cross-module
  dependency for journeys.py to honor when it selects path leads.

== What this module does NOT do ==
- No touchpoint rows; no utm_source/medium/content/referrer (journeys.py).
- No seed_label_theme_primary/secondary (journeys.py).
- No outcomes; no Finding 1 channel-quality CW skew (outcomes.py).
- No content-asset assignment beyond the linkedin campaign slug.

Output: list[PartialLead] with created_via_channel, created_at, and
first_touch_utm_campaign (linkedin only) populated; themes still None.
"""
