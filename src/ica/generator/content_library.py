"""Static content-asset library — the menu journeys.py draws from.

Design choices (surfaced for diff review):

- LOCKED inventory, not a v1 sizing decision. docs/data-world.md §8 and
  taxonomy.py (PODCAST_EPISODES / BLOG_POSTS / LINKEDIN_CAMPAIGNS /
  WEBINARS / NEWSLETTER_EDITIONS / COMPARISON_PAGES, unioned as
  ALL_ASSETS) fix the inventory at 21 assets — 3 podcast + 6 blog +
  3 linkedin + 2 webinar + 6 newsletter + 1 comparison. The kickoff
  brief floated ~30-80 pieces; the gate overrides the brief. Content
  assets are a SHARED library — one podcast episode is heard by many
  leads — so 21 is ample: journey variety comes from touchpoint
  sequencing in journeys.py, not from unique content per lead.

- No DB table. data-world.md §2 commits CP1 to no reference tables
  ("canonical lists live in code"). This module is pure code; ContentAsset
  is an in-memory record, not persisted. The touchpoints table already
  carries content_asset_slug TEXT as the reference into this library.

- SSOT. slug, theme, and channel come from taxonomy (ASSET_THEME /
  ASSET_CHANNEL); this module adds only the metadata data-world.md §8
  specifies and taxonomy does not — title and target personas. Nothing
  is redeclared. No engineered skews live here — content_library is
  static; journeys.py and seed.py own the skews.

The (channel x theme) grid is sparse — mostly one asset per populated
cell, some cells empty. That is expected: journeys.py picks from a
channel's actual assets, it does not require every cell filled.
"""

from dataclasses import dataclass

from ica.taxonomy import (
    ALL_ASSETS,
    ASSET_CHANNEL,
    ASSET_THEME,
    NEWSLETTER_EDITIONS,
    Channel,
    Persona,
    Theme,
)

__all__ = [
    "CONTENT_LIBRARY",
    "ContentAsset",
    "assets_by_channel",
    "assets_by_theme",
    "assets_for",
    "get_asset",
]


@dataclass(frozen=True)
class ContentAsset:
    """One content piece. slug / channel / theme mirror taxonomy; title and
    target_personas are data-world.md §8 metadata. target_personas is empty
    for general-audience assets (the newsletter editions)."""

    slug: str
    channel: Channel
    theme: Theme | None
    title: str
    target_personas: tuple[Persona, ...]


# Title + target personas (data-world.md §8) for the 15 named assets.
# slug/theme/channel are NOT repeated here — they are pulled from taxonomy.
_ASSET_META: dict[str, tuple[str, tuple[Persona, ...]]] = {
    # Podcast episodes
    "ops-podcast-ep-42": ("Cutting Manual Work in RevOps", (Persona.MAYA,)),
    "saas-growth-pod-17": ("Forecasting in Growth-Stage SaaS", (Persona.DAVID,)),
    "go-to-market-show-09": ("Pipeline Attribution in 2026", (Persona.MAYA,)),
    # Blog posts
    "blog-revops-manual-toil": ("The RevOps Manual Toil Audit", (Persona.MAYA,)),
    "blog-tool-sprawl-2026": (
        "The 2026 GTM Tool Sprawl Problem",
        (Persona.PATRICIA,),
    ),
    "blog-attribution-honest": (
        "Honest Attribution: What B2B Marketers Get Wrong",
        (Persona.MAYA, Persona.DAVID),
    ),
    "blog-forecast-models": ("Forecast Models That Don't Lie", (Persona.DAVID,)),
    "blog-crm-cleanup": ("The Quarterly CRM Cleanup Playbook", (Persona.MAYA,)),
    "blog-compliance-vendor-checklist": (
        "The Enterprise GTM Vendor Compliance Checklist",
        (Persona.PATRICIA,),
    ),
    # LinkedIn ad campaigns
    "linkedin_q2_broad_funnel": (
        "LinkedIn Q2 — Broad Funnel",
        (Persona.CARLOS, Persona.PATRICIA),
    ),
    "linkedin_q2_enterprise": ("LinkedIn Q2 — Enterprise", (Persona.PATRICIA,)),
    "linkedin_q2_revops_targeted": (
        "LinkedIn Q2 — RevOps Targeted",
        (Persona.MAYA,),
    ),
    # Webinars
    "webinar-attribution-deepdive": (
        "Attribution Deep-Dive",
        (Persona.MAYA, Persona.DAVID),
    ),
    "webinar-rep-efficiency-panel": ("Rep Efficiency Panel", (Persona.DAVID,)),
    # Comparison page
    "comparison-vs-competitor-x": (
        "ICA vs Competitor X: GTM Stack Comparison",
        (Persona.MAYA, Persona.DAVID),
    ),
}

# Newsletter editions are programmatic (data-world.md §8) — general-audience,
# titled by month. target_personas is empty: no specific persona target.
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
for _slug in NEWSLETTER_EDITIONS:
    _month = int(_slug.rsplit("-", 1)[1])
    _ASSET_META[_slug] = (f"ICA Monthly — {_MONTH_NAMES[_month - 1]} 2026", ())


CONTENT_LIBRARY: tuple[ContentAsset, ...] = tuple(
    ContentAsset(
        slug=slug,
        channel=ASSET_CHANNEL[slug],
        theme=ASSET_THEME[slug],
        title=_ASSET_META[slug][0],
        target_personas=_ASSET_META[slug][1],
    )
    for slug in ALL_ASSETS
)

_BY_SLUG: dict[str, ContentAsset] = {asset.slug: asset for asset in CONTENT_LIBRARY}


def get_asset(slug: str) -> ContentAsset:
    """Look up one asset by slug."""
    return _BY_SLUG[slug]


def assets_by_channel(channel: Channel) -> tuple[ContentAsset, ...]:
    """Every asset carried on `channel`."""
    return tuple(asset for asset in CONTENT_LIBRARY if asset.channel == channel)


def assets_by_theme(theme: Theme) -> tuple[ContentAsset, ...]:
    """Every asset whose primary theme is `theme`."""
    return tuple(asset for asset in CONTENT_LIBRARY if asset.theme == theme)


def assets_for(channel: Channel, theme: Theme) -> tuple[ContentAsset, ...]:
    """Assets on `channel` matching `theme` — the (channel x theme) cell
    journeys.py draws from."""
    return tuple(
        asset
        for asset in CONTENT_LIBRARY
        if asset.channel == channel and asset.theme == theme
    )
