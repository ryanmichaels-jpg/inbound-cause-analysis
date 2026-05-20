"""Single source of truth for all canonical names and structural data in ICA.

Every other module imports from here. See `docs/aha-patterns.md` § "Taxonomy:
single source of truth" for the architectural commitment.

Conventions:
- StrEnum values are the literal strings stored in the database.
- Affinity rankings and theme rankings are ordered tuples: strongest first.
- Floats that represent shares sum to 1.0 (enforced by tests/test_taxonomy.py).
- Engineered targets for the aha patterns are committed here so test_aha_patterns
  and generator/seed.py reference the same constants.
"""

from enum import StrEnum

# =============================================================================
# Section 1 — Canonical name enums
# =============================================================================


class Persona(StrEnum):
    MAYA = "Mid-market RevOps Leader"
    DAVID = "VP Sales at growth-stage SaaS"
    PATRICIA = "Enterprise IT Buyer"
    CARLOS = "SMB Founder"


class Channel(StrEnum):
    PODCAST = "podcast"
    LINKEDIN_PAID = "linkedin_paid"
    ORGANIC_SEARCH = "organic_search"
    NEWSLETTER = "newsletter"
    WEBINAR = "webinar"
    COMPARISON_PAGE = "comparison_page"


class Theme(StrEnum):
    MANUAL_WORK_REDUCTION = "manual_work_reduction"
    DATA_QUALITY = "data_quality"
    TOOL_SPRAWL_CONSOLIDATION = "tool_sprawl_consolidation"
    PIPELINE_ATTRIBUTION = "pipeline_attribution"
    FORECASTING_ACCURACY = "forecasting_accuracy"
    REP_EFFICIENCY = "rep_efficiency"
    CROSS_TEAM_ALIGNMENT = "cross_team_alignment"
    ONBOARDING_RAMP = "onboarding_ramp"
    COMPLIANCE_SECURITY = "compliance_security"


class Outcome(StrEnum):
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    DISQUALIFIED = "disqualified"
    GHOSTED = "ghosted"
    NURTURE = "nurture"


class FormType(StrEnum):
    DEMO_REQUEST = "demo_request"
    NEWSLETTER_SIGNUP = "newsletter_signup"
    CONTENT_DOWNLOAD = "content_download"
    CONTACT_SALES = "contact_sales"
    COMPARISON_PAGE_CTA = "comparison_page_cta"
    WEBINAR_REGISTER = "webinar_register"


class EventType(StrEnum):
    PAGE_VIEW = "page_view"
    CONTENT_DOWNLOAD = "content_download"
    FORM_VIEW = "form_view"
    FORM_SUBMIT = "form_submit"
    DEMO_REQUEST = "demo_request"
    DEMO_ATTENDED = "demo_attended"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    PODCAST_LISTEN = "podcast_listen"
    WEBINAR_REGISTER = "webinar_register"
    WEBINAR_ATTENDED = "webinar_attended"


class Seniority(StrEnum):
    IC = "IC"
    MANAGER = "Manager"
    SR_MANAGER = "Sr Manager"
    DIRECTOR = "Director"
    VP = "VP"
    C_LEVEL = "C-level"


# =============================================================================
# Section 2 — Sub-reason vocabularies (per outcome)
# =============================================================================

CLOSED_LOST_SUB_REASONS: tuple[str, ...] = (
    "price",
    "competitor_chosen",
    "timing",
    "no_decision",
    "wrong_fit_late",
)

DISQUALIFIED_SUB_REASONS: tuple[str, ...] = (
    "no_budget",
    "no_authority",
    "out_of_icp_segment",
    "wrong_industry",
    "company_too_small",
    "student_or_competitor",
)

NURTURE_SUB_REASONS: tuple[str, ...] = (
    "too_early",
    "waiting_on_budget",
    "evaluating_in_6mo",
    "champion_changed_role",
)

# =============================================================================
# Section 3 — Theme disambiguation rule
# Imported by copy_bank.py (generation) and the CP4 LLM prompt (extraction)
# so both sides apply identical rules.
# =============================================================================

MWR_VS_DATA_QUALITY_DISAMBIGUATION = """\
Theme disambiguation — manual_work_reduction vs data_quality

manual_work_reduction
    The pain is THE WORK.
    Vocabulary: "burning N hours/week", "copy-paste", "manual list-building",
    "rep time on admin", "ops backlog", "I do this by hand every Monday".

data_quality
    The pain is THE DATA.
    Vocabulary: "dupes", "blank fields", "stale contacts", "bad data",
    "enrichment gaps", "the CRM is a mess".

When a snippet legitimately spans both (e.g., "we spend hours every week
fixing dupes"), tag it as:
    primary   = data_quality           (the goal — what they want to fix)
    secondary = manual_work_reduction  (the symptom — the time-cost of the problem)
"""

# =============================================================================
# Section 4 — Content asset library
# =============================================================================

PODCAST_EPISODES: tuple[str, ...] = (
    "ops-podcast-ep-42",
    "saas-growth-pod-17",
    "go-to-market-show-09",
)

BLOG_POSTS: tuple[str, ...] = (
    "blog-revops-manual-toil",
    "blog-tool-sprawl-2026",
    "blog-attribution-honest",
    "blog-forecast-models",
    "blog-crm-cleanup",
    "blog-compliance-vendor-checklist",
)

LINKEDIN_CAMPAIGNS: tuple[str, ...] = (
    "linkedin_q2_broad_funnel",
    "linkedin_q2_enterprise",
    "linkedin_q2_revops_targeted",
)

WEBINARS: tuple[str, ...] = (
    "webinar-attribution-deepdive",
    "webinar-rep-efficiency-panel",
)

NEWSLETTER_EDITIONS: tuple[str, ...] = tuple(
    f"newsletter-2026-{m:02d}" for m in range(1, 7)
)

COMPARISON_PAGES: tuple[str, ...] = (
    "comparison-vs-competitor-x",
)

ALL_ASSETS: tuple[str, ...] = (
    *PODCAST_EPISODES,
    *BLOG_POSTS,
    *LINKEDIN_CAMPAIGNS,
    *WEBINARS,
    *NEWSLETTER_EDITIONS,
    *COMPARISON_PAGES,
)

# Asset slug -> primary theme (None for mixed/broad assets)
ASSET_THEME: dict[str, Theme | None] = {
    "ops-podcast-ep-42": Theme.MANUAL_WORK_REDUCTION,
    "saas-growth-pod-17": Theme.FORECASTING_ACCURACY,
    "go-to-market-show-09": Theme.PIPELINE_ATTRIBUTION,
    "blog-revops-manual-toil": Theme.MANUAL_WORK_REDUCTION,
    "blog-tool-sprawl-2026": Theme.TOOL_SPRAWL_CONSOLIDATION,
    "blog-attribution-honest": Theme.PIPELINE_ATTRIBUTION,
    "blog-forecast-models": Theme.FORECASTING_ACCURACY,
    "blog-crm-cleanup": Theme.DATA_QUALITY,
    "blog-compliance-vendor-checklist": Theme.COMPLIANCE_SECURITY,
    "linkedin_q2_broad_funnel": None,  # mixed / broad
    "linkedin_q2_enterprise": Theme.TOOL_SPRAWL_CONSOLIDATION,
    "linkedin_q2_revops_targeted": Theme.MANUAL_WORK_REDUCTION,
    "webinar-attribution-deepdive": Theme.PIPELINE_ATTRIBUTION,
    "webinar-rep-efficiency-panel": Theme.REP_EFFICIENCY,
    "comparison-vs-competitor-x": Theme.TOOL_SPRAWL_CONSOLIDATION,
}

# Newsletter editions rotate one theme per month
_NEWSLETTER_THEME_ROTATION: tuple[Theme, ...] = (
    Theme.MANUAL_WORK_REDUCTION,
    Theme.PIPELINE_ATTRIBUTION,
    Theme.DATA_QUALITY,
    Theme.FORECASTING_ACCURACY,
    Theme.REP_EFFICIENCY,
    Theme.TOOL_SPRAWL_CONSOLIDATION,
)
for _i, _slug in enumerate(NEWSLETTER_EDITIONS):
    ASSET_THEME[_slug] = _NEWSLETTER_THEME_ROTATION[_i % len(_NEWSLETTER_THEME_ROTATION)]

# Asset slug -> channel
ASSET_CHANNEL: dict[str, Channel] = {}
for _slug in PODCAST_EPISODES:
    ASSET_CHANNEL[_slug] = Channel.PODCAST
for _slug in BLOG_POSTS:
    ASSET_CHANNEL[_slug] = Channel.ORGANIC_SEARCH
for _slug in LINKEDIN_CAMPAIGNS:
    ASSET_CHANNEL[_slug] = Channel.LINKEDIN_PAID
for _slug in WEBINARS:
    ASSET_CHANNEL[_slug] = Channel.WEBINAR
for _slug in NEWSLETTER_EDITIONS:
    ASSET_CHANNEL[_slug] = Channel.NEWSLETTER
for _slug in COMPARISON_PAGES:
    ASSET_CHANNEL[_slug] = Channel.COMPARISON_PAGE

# =============================================================================
# Section 5 — Channel persona affinity (strongest -> weakest)
# data-world.md §7
# =============================================================================

CHANNEL_PERSONA_AFFINITY: dict[Channel, tuple[Persona, ...]] = {
    Channel.PODCAST: (Persona.MAYA, Persona.DAVID, Persona.CARLOS, Persona.PATRICIA),
    Channel.LINKEDIN_PAID: (Persona.CARLOS, Persona.PATRICIA, Persona.DAVID, Persona.MAYA),
    Channel.ORGANIC_SEARCH: (Persona.MAYA, Persona.DAVID, Persona.PATRICIA, Persona.CARLOS),
    Channel.NEWSLETTER: (Persona.MAYA, Persona.DAVID, Persona.CARLOS, Persona.PATRICIA),
    Channel.WEBINAR: (Persona.DAVID, Persona.MAYA, Persona.PATRICIA, Persona.CARLOS),
    Channel.COMPARISON_PAGE: (Persona.MAYA, Persona.DAVID, Persona.PATRICIA, Persona.CARLOS),
}

# =============================================================================
# Section 6 — Persona theme propensity (signature theme first, top-5 only)
# data-world.md §6
# =============================================================================

PERSONA_THEME_AFFINITY: dict[Persona, tuple[Theme, ...]] = {
    Persona.MAYA: (
        Theme.MANUAL_WORK_REDUCTION,  # signature — Finding 2 cell
        Theme.PIPELINE_ATTRIBUTION,
        Theme.DATA_QUALITY,
        Theme.TOOL_SPRAWL_CONSOLIDATION,
        Theme.FORECASTING_ACCURACY,
    ),
    Persona.DAVID: (
        Theme.REP_EFFICIENCY,  # signature
        Theme.FORECASTING_ACCURACY,
        Theme.PIPELINE_ATTRIBUTION,
        Theme.MANUAL_WORK_REDUCTION,
        Theme.CROSS_TEAM_ALIGNMENT,
    ),
    Persona.PATRICIA: (
        Theme.COMPLIANCE_SECURITY,  # signature — Finding 5 cell (secondary)
        Theme.TOOL_SPRAWL_CONSOLIDATION,
        Theme.DATA_QUALITY,
        Theme.CROSS_TEAM_ALIGNMENT,
        Theme.FORECASTING_ACCURACY,
    ),
    Persona.CARLOS: (
        Theme.ONBOARDING_RAMP,  # signature
        Theme.REP_EFFICIENCY,
        Theme.MANUAL_WORK_REDUCTION,
        Theme.PIPELINE_ATTRIBUTION,
        Theme.DATA_QUALITY,
    ),
}

# =============================================================================
# Section 7 — Persona company-archetype attributes
# data-world.md §6
# =============================================================================

PERSONA_COMPANY_SIZE_RANGE: dict[Persona, tuple[int, int]] = {
    Persona.MAYA: (200, 400),
    Persona.DAVID: (150, 500),
    Persona.PATRICIA: (2000, 10000),
    Persona.CARLOS: (5, 30),
}

PERSONA_INDUSTRY_WEIGHTS: dict[Persona, dict[str, float]] = {
    Persona.MAYA: {
        "SaaS": 0.55, "Martech": 0.20, "Fintech": 0.20, "Other": 0.05,
    },
    Persona.DAVID: {
        "SaaS": 0.55, "Fintech": 0.20, "Martech": 0.15, "Other": 0.10,
    },
    Persona.PATRICIA: {
        "Other": 0.30, "Healthcare": 0.20, "Manufacturing": 0.20,
        "Consumer": 0.15, "Fintech": 0.10, "SaaS": 0.05,
    },
    Persona.CARLOS: {
        "SaaS": 0.40, "E-commerce": 0.25, "Martech": 0.15, "Other": 0.20,
    },
}

PERSONA_SENIORITY_WEIGHTS: dict[Persona, dict[Seniority, float]] = {
    Persona.MAYA: {
        Seniority.DIRECTOR: 0.65, Seniority.SR_MANAGER: 0.20, Seniority.VP: 0.15,
    },
    Persona.DAVID: {
        Seniority.VP: 0.70, Seniority.DIRECTOR: 0.25, Seniority.C_LEVEL: 0.05,
    },
    Persona.PATRICIA: {
        Seniority.DIRECTOR: 0.50, Seniority.VP: 0.35,
        Seniority.SR_MANAGER: 0.10, Seniority.MANAGER: 0.05,
    },
    Persona.CARLOS: {
        Seniority.C_LEVEL: 0.80, Seniority.VP: 0.15, Seniority.DIRECTOR: 0.05,
    },
}

# Persona- and seniority-conditional job titles (data-world.md §2.1),
# keyed by seniority. generator/personas.py draws seniority first, then
# samples a title from that persona's sub-pool for that seniority, so
# person_title and person_seniority are always tier-consistent. Keys
# match exactly the seniorities each persona samples in
# PERSONA_SENIORITY_WEIGHTS. A distinct vocabulary per persona is part of
# what makes a raw lead row readable.
#
# Sub-pools hold >=2 titles, not >=3: the Carlos VP and Director
# sub-pools are narrow founder-at-non-C-level edge cases (~90 and ~30
# leads), and forcing a third title there means inventing implausible
# titles — the realism cost outweighs the variety gain. Do not "fix"
# this up to >=3 in a later refactor.
PERSONA_TITLES: dict[Persona, dict[Seniority, tuple[str, ...]]] = {
    Persona.MAYA: {
        Seniority.DIRECTOR: (
            "Director of RevOps",
            "Director of Revenue Operations",
            "RevOps Director",
        ),
        Seniority.SR_MANAGER: (
            "Senior RevOps Manager",
            "Senior Manager, Revenue Operations",
            "RevOps Lead",
        ),
        Seniority.VP: (
            "VP of Revenue Operations",
            "Head of Revenue Operations",
            "VP of RevOps",
        ),
    },
    Persona.DAVID: {
        Seniority.VP: (
            "VP of Sales",
            "Head of Sales",
            "Regional VP of Sales",
        ),
        Seniority.DIRECTOR: (
            "Director of Sales",
            "Sales Director",
            "Director of Field Sales",
        ),
        Seniority.C_LEVEL: (
            "Chief Revenue Officer",
            "Chief Sales Officer",
            "Chief Commercial Officer",
        ),
    },
    Persona.PATRICIA: {
        Seniority.DIRECTOR: (
            "Director of IT",
            "IT Director",
            "Director of Information Technology",
        ),
        Seniority.VP: (
            "VP of Information Technology",
            "Head of IT",
            "VP of IT Infrastructure",
        ),
        Seniority.SR_MANAGER: (
            "Senior Manager, IT Operations",
            "Senior IT Procurement Manager",
            "Senior Manager, IT Security & Compliance",
        ),
        Seniority.MANAGER: (
            "IT Procurement Manager",
            "IT Operations Manager",
            "IT Security & Compliance Manager",
        ),
    },
    Persona.CARLOS: {
        Seniority.C_LEVEL: (
            "Founder & CEO",
            "CEO",
            "Co-Founder & CEO",
            "Founder",
        ),
        Seniority.VP: (
            "Co-Founder",
            "VP of Operations",
        ),
        Seniority.DIRECTOR: (
            "Founding Team Member",
            "Director of Operations",
        ),
    },
}

# =============================================================================
# Section 8 — Population shares and volume targets
# =============================================================================

PERSONA_POPULATION_SHARE: dict[Persona, float] = {
    Persona.MAYA: 0.28,
    Persona.DAVID: 0.22,
    Persona.PATRICIA: 0.26,
    Persona.CARLOS: 0.24,
}

CHANNEL_TARGET_VOLUME: dict[Channel, int] = {
    Channel.PODCAST: 200,
    Channel.LINKEDIN_PAID: 1000,
    Channel.ORGANIC_SEARCH: 400,
    Channel.NEWSLETTER: 300,
    Channel.WEBINAR: 300,
    Channel.COMPARISON_PAGE: 300,
}

# Within-linkedin_paid per-campaign volumes
LINKEDIN_CAMPAIGN_VOLUME: dict[str, int] = {
    "linkedin_q2_broad_funnel": 600,
    "linkedin_q2_enterprise": 250,
    "linkedin_q2_revops_targeted": 150,
}

# Within-campaign persona mix for the linkedin_paid sub-campaigns
LINKEDIN_CAMPAIGN_PERSONA_MIX: dict[str, dict[Persona, float]] = {
    "linkedin_q2_broad_funnel": {
        Persona.CARLOS: 0.55,
        Persona.PATRICIA: 0.30,
        Persona.DAVID: 0.10,
        Persona.MAYA: 0.05,
    },
    "linkedin_q2_enterprise": {
        Persona.PATRICIA: 0.60,
        Persona.DAVID: 0.15,
        Persona.MAYA: 0.15,
        Persona.CARLOS: 0.10,
    },
    "linkedin_q2_revops_targeted": {
        Persona.MAYA: 0.55,
        Persona.DAVID: 0.25,
        Persona.CARLOS: 0.12,
        Persona.PATRICIA: 0.08,
    },
}

# =============================================================================
# Section 9 — Channel baseline CW rates (Finding 1 enforces podcast/linkedin)
# =============================================================================

CHANNEL_BASELINE_CW_RATE: dict[Channel, float] = {
    Channel.PODCAST: 0.30,
    Channel.LINKEDIN_PAID: 0.03,
    Channel.ORGANIC_SEARCH: 0.07,
    Channel.NEWSLETTER: 0.06,
    Channel.WEBINAR: 0.05,
    Channel.COMPARISON_PAGE: 0.09,
}

# =============================================================================
# Section 10 — Baseline outcome mix and per-persona ghost skew
# data-world.md §5
# =============================================================================

BASELINE_OUTCOME_MIX: dict[Outcome, float] = {
    Outcome.CLOSED_WON: 0.06,
    Outcome.CLOSED_LOST: 0.10,
    Outcome.DISQUALIFIED: 0.25,
    Outcome.GHOSTED: 0.24,
    Outcome.NURTURE: 0.35,
}

# Per-persona share of non-won outcomes resolving as ghosted.
# Strong-fit personas: low ghost share. Weak-fit: high.
PERSONA_GHOST_SHARE_OF_NON_WINS: dict[Persona, float] = {
    Persona.MAYA: 0.12,
    Persona.DAVID: 0.18,
    Persona.PATRICIA: 0.30,
    Persona.CARLOS: 0.38,
}

# =============================================================================
# Section 11 — Finding 4 broad_funnel per-persona outcome distributions
# aha-patterns.md §11
# =============================================================================

BROAD_FUNNEL_PERSONA_OUTCOMES: dict[Persona, dict[Outcome, float]] = {
    Persona.CARLOS: {
        Outcome.CLOSED_WON: 0.01,
        Outcome.CLOSED_LOST: 0.02,
        Outcome.DISQUALIFIED: 0.47,
        Outcome.GHOSTED: 0.45,
        Outcome.NURTURE: 0.05,
    },
    Persona.PATRICIA: {
        Outcome.CLOSED_WON: 0.02,
        Outcome.CLOSED_LOST: 0.06,
        Outcome.DISQUALIFIED: 0.45,
        Outcome.GHOSTED: 0.38,
        Outcome.NURTURE: 0.09,
    },
    Persona.DAVID: {
        Outcome.CLOSED_WON: 0.08,
        Outcome.CLOSED_LOST: 0.12,
        Outcome.DISQUALIFIED: 0.15,
        Outcome.GHOSTED: 0.12,
        Outcome.NURTURE: 0.53,
    },
    Persona.MAYA: {
        Outcome.CLOSED_WON: 0.14,
        Outcome.CLOSED_LOST: 0.09,
        Outcome.DISQUALIFIED: 0.08,
        Outcome.GHOSTED: 0.06,
        Outcome.NURTURE: 0.63,
    },
}

# Fraction of closed_lost in broad_funnel tagged 'wrong_fit_late' per persona
BROAD_FUNNEL_WFL_FRACTION_OF_LOST: dict[Persona, float] = {
    Persona.CARLOS: 0.70,
    Persona.PATRICIA: 0.70,
    Persona.DAVID: 0.30,
    Persona.MAYA: 0.20,
}

# =============================================================================
# Section 12 — Engineered skew targets per finding
# Imported by generator/seed.py and tests/test_aha_patterns.py
# so both sides reference identical numbers.
# =============================================================================

# Finding 1 — channel quality surprise
PODCAST_TARGET_CW_RATE: float = 0.30
LINKEDIN_PAID_TARGET_CW_RATE: float = 0.03

# Finding 2 — message-persona resonance differential (headline)
F2_TARGET_CELL_PERSONA: Persona = Persona.MAYA
F2_TARGET_CELL_THEME: Theme = Theme.MANUAL_WORK_REDUCTION
F2_TARGET_CELL_CW_RATE: float = 0.25

# Finding 3 — multi-touch journey pattern
F3_PATH_FIRST_TOUCH_CHANNEL: Channel = Channel.PODCAST
F3_PATH_BLOG_CHANNEL: Channel = Channel.ORGANIC_SEARCH
F3_PATH_WITHIN_DAYS: int = 14
F3_TARGET_PATH_COUNT: int = 50
F3_TARGET_PATH_CW_RATE: float = 0.45

# Finding 4 — ICP fit vs volume mismatch
F4_TARGET_CAMPAIGN: str = "linkedin_q2_broad_funnel"
F4_TARGET_BAD_SHARE: float = 0.78
F4_BAD_OUTCOMES: tuple[Outcome, ...] = (Outcome.DISQUALIFIED, Outcome.GHOSTED)
F4_BAD_CLOSED_LOST_SUB_REASON: str = "wrong_fit_late"

# Finding 5 (secondary) — Patricia × compliance_security resonance
F5_TARGET_CELL_PERSONA: Persona = Persona.PATRICIA
F5_TARGET_CELL_THEME: Theme = Theme.COMPLIANCE_SECURITY
F5_TARGET_CELL_CW_RATE: float = 0.18

# =============================================================================
# Section 13 — Dataset-level constants
# =============================================================================

TOTAL_LEADS_DEFAULT: int = 2500
TIME_WINDOW_START: str = "2026-01-01"
TIME_WINDOW_END: str = "2026-06-30"
DEFAULT_SEED: int = 42

# Industries (union of values appearing in PERSONA_INDUSTRY_WEIGHTS)
INDUSTRIES: tuple[str, ...] = (
    "SaaS",
    "Fintech",
    "Martech",
    "E-commerce",
    "Healthcare",
    "Manufacturing",
    "Consumer",
    "Other",
)

# =============================================================================
# Section 14 — Theme anchor vocabulary and bridge pairs
# Imported by generator/copy_bank.py (snippet generation + the lexical-
# separation test) and, in CP4, by the LLM extraction prompt.
# =============================================================================

# Per-theme anchor vocabulary: lowercase substring tokens that name a theme's
# specific pain object or action. An anchor is distinctive — it would read as
# out of place in another theme's snippet. Ambient GTM vocabulary (pipeline,
# team, process, deal, quota, growth) is deliberately excluded: it appears
# across every theme and carries no separating signal. For the closest pair,
# manual_work_reduction vs data_quality, the split is dictated by §4 of
# data-world.md — mwr anchors name manual ACTIONS, data_quality anchors name
# data DEFECTS. copy_bank.py enforces, per snippet: a pure single-theme
# snippet contains >=1 of its own anchors and zero foreign anchors; a bridge
# snippet contains >=1 anchor from each of its two themes.
THEME_ANCHOR_VOCAB: dict[Theme, tuple[str, ...]] = {
    Theme.MANUAL_WORK_REDUCTION: (
        "copy-paste", "copy and paste", "by hand", "manual",
        "list-building", "ops backlog", "admin",
    ),
    Theme.DATA_QUALITY: (
        "dupes", "duplicate", "blank field", "stale contact",
        "bad data", "dirty data", "enrichment gap", "crm is a mess",
    ),
    Theme.TOOL_SPRAWL_CONSOLIDATION: (
        "tool sprawl", "too many tools", "point solution", "stitch",
        "consolidat", "disparate system",
    ),
    Theme.PIPELINE_ATTRIBUTION: (
        "attribution", "which channels", "which campaigns",
        "first-touch", "last-touch", "drives pipeline",
    ),
    Theme.FORECASTING_ACCURACY: (
        "forecast", "sandbag", "pipeline coverage", "commit number",
        "call the quarter", "slipped deal",
    ),
    Theme.REP_EFFICIENCY: (
        "talk track", "call quality", "follow-up cadence",
        "selling time", "call coaching", "rep productivity",
    ),
    Theme.CROSS_TEAM_ALIGNMENT: (
        "align", "sales and marketing", "marketing and sales",
        "handoff", "hand-off", "silo", "finger-point",
    ),
    Theme.ONBOARDING_RAMP: (
        "ramp", "new hire", "new rep", "onboarding",
        "up to speed", "time to first deal",
    ),
    Theme.COMPLIANCE_SECURITY: (
        "soc2", "soc 2", "sso", "security review", "data residency",
        "gdpr", "dpa", "vendor evaluation", "procurement",
    ),
}

# Thematic-adjacency bridge pairs — the only theme pairs a bridge snippet
# (~30% of the copy bank) may span. Each pair is ordered (primary, secondary):
# primary = the goal / what the lead wants to fix, secondary = the symptom or
# cause. This is §4's mwr/data_quality direction rule, generalized.
THEME_BRIDGE_PAIRS: tuple[tuple[Theme, Theme], ...] = (
    # data-world.md §4 — DICTATED. "We burn hours every week fixing dupes."
    (Theme.DATA_QUALITY, Theme.MANUAL_WORK_REDUCTION),
    # §4 names this example. Manual admin load eats reps' selling time.
    (Theme.REP_EFFICIENCY, Theme.MANUAL_WORK_REDUCTION),
    # §8 pairs these on the comparison page. Attribution is guesswork when
    # the data is split across too many tools.
    (Theme.PIPELINE_ATTRIBUTION, Theme.TOOL_SPRAWL_CONSOLIDATION),
    # §6 — Patricia's top two themes. Every new point tool is another
    # vendor security review.
    (Theme.COMPLIANCE_SECURITY, Theme.TOOL_SPRAWL_CONSOLIDATION),
    # §6 — Carlos's top two themes. New hires ramp slowly when the talk
    # tracks are not documented.
    (Theme.ONBOARDING_RAMP, Theme.REP_EFFICIENCY),
    # Sales and marketing dispute attribution credit every QBR.
    (Theme.CROSS_TEAM_ALIGNMENT, Theme.PIPELINE_ATTRIBUTION),
)

# =============================================================================
# Section 15 — Per-persona seed-theme share distribution
# Consumed by generator/journeys.py to assign seed_label_theme_primary by
# stratified sampling (exact round(share * persona population) per cell).
# =============================================================================

# Probability that a lead of each persona gets a given primary theme. Rows
# sum to 1.0 (enforced by tests/test_taxonomy.py).
#
# DICTATED cells — do not rebalance without reopening Gate 2:
#   Maya x manual_work_reduction   = 0.40  aha-patterns.md F2 (0.40*700 = 280)
#   Patricia x compliance_security = 0.40  aha-patterns.md F5 (0.40*650 = 260)
#   non-Patricia x compliance_security = 0.06 each  aha-patterns.md F5
#       ("~6% of each non-Patricia persona"). The F2 comparison cell also
#       constrains non-Maya x manual_work_reduction to sum-weight ~207.
#
# PROPOSED cells — v1 design choice: within each persona the shares are
# monotonic with the §6 PERSONA_THEME_AFFINITY ranking (signature theme
# highest, rank-5 lowest, off-affinity themes a small tail below rank-5).
# Exception: compliance_security is pinned at the F5-dictated 0.06 for the
# three non-Patricia personas, so it sits at tail level regardless of
# affinity. This keeps each persona's theme mix recognizable.
PERSONA_THEME_SHARE: dict[Persona, dict[Theme, float]] = {
    Persona.MAYA: {
        Theme.MANUAL_WORK_REDUCTION: 0.40,
        Theme.PIPELINE_ATTRIBUTION: 0.18,
        Theme.DATA_QUALITY: 0.14,
        Theme.TOOL_SPRAWL_CONSOLIDATION: 0.10,
        Theme.FORECASTING_ACCURACY: 0.07,
        Theme.COMPLIANCE_SECURITY: 0.06,
        Theme.REP_EFFICIENCY: 0.02,
        Theme.CROSS_TEAM_ALIGNMENT: 0.02,
        Theme.ONBOARDING_RAMP: 0.01,
    },
    Persona.DAVID: {
        Theme.REP_EFFICIENCY: 0.28,
        Theme.FORECASTING_ACCURACY: 0.22,
        Theme.PIPELINE_ATTRIBUTION: 0.18,
        Theme.MANUAL_WORK_REDUCTION: 0.16,
        Theme.CROSS_TEAM_ALIGNMENT: 0.06,
        Theme.COMPLIANCE_SECURITY: 0.06,
        Theme.DATA_QUALITY: 0.02,
        Theme.TOOL_SPRAWL_CONSOLIDATION: 0.01,
        Theme.ONBOARDING_RAMP: 0.01,
    },
    Persona.PATRICIA: {
        Theme.COMPLIANCE_SECURITY: 0.40,
        Theme.TOOL_SPRAWL_CONSOLIDATION: 0.20,
        Theme.DATA_QUALITY: 0.15,
        Theme.CROSS_TEAM_ALIGNMENT: 0.10,
        Theme.FORECASTING_ACCURACY: 0.07,
        Theme.PIPELINE_ATTRIBUTION: 0.03,
        Theme.MANUAL_WORK_REDUCTION: 0.02,
        Theme.REP_EFFICIENCY: 0.02,
        Theme.ONBOARDING_RAMP: 0.01,
    },
    Persona.CARLOS: {
        Theme.ONBOARDING_RAMP: 0.30,
        Theme.REP_EFFICIENCY: 0.24,
        Theme.MANUAL_WORK_REDUCTION: 0.18,
        Theme.PIPELINE_ATTRIBUTION: 0.10,
        Theme.DATA_QUALITY: 0.07,
        Theme.COMPLIANCE_SECURITY: 0.06,
        Theme.TOOL_SPRAWL_CONSOLIDATION: 0.02,
        Theme.FORECASTING_ACCURACY: 0.02,
        Theme.CROSS_TEAM_ALIGNMENT: 0.01,
    },
}
