"""Internal consistency invariants on the taxonomy module.

Catches regressions when constants drift — e.g., adding a new theme but
forgetting to update PERSONA_THEME_AFFINITY, or rebalancing a persona's
seniority weights to no longer sum to 1.0.
"""

import math

import pytest

from ica.taxonomy import (
    ALL_ASSETS,
    ASSET_CHANNEL,
    ASSET_THEME,
    BASELINE_OUTCOME_MIX,
    BLOG_POSTS,
    BROAD_FUNNEL_PERSONA_OUTCOMES,
    BROAD_FUNNEL_WFL_FRACTION_OF_LOST,
    CHANNEL_BASELINE_CW_RATE,
    CHANNEL_PERSONA_AFFINITY,
    CHANNEL_TARGET_VOLUME,
    COMPARISON_PAGES,
    INDUSTRIES,
    LINKEDIN_CAMPAIGN_PERSONA_MIX,
    LINKEDIN_CAMPAIGN_VOLUME,
    LINKEDIN_CAMPAIGNS,
    NEWSLETTER_EDITIONS,
    PERSONA_COMPANY_SIZE_RANGE,
    PERSONA_GHOST_SHARE_OF_NON_WINS,
    PERSONA_INDUSTRY_WEIGHTS,
    PERSONA_POPULATION_SHARE,
    PERSONA_SENIORITY_WEIGHTS,
    PERSONA_THEME_AFFINITY,
    PERSONA_THEME_SHARE,
    PERSONA_TITLES,
    PODCAST_EPISODES,
    THEME_ANCHOR_VOCAB,
    THEME_BRIDGE_PAIRS,
    TOTAL_LEADS_DEFAULT,
    WEBINARS,
    Channel,
    Outcome,
    Persona,
    Theme,
)

EPS = 1e-9


def _approx_one(value: float) -> bool:
    return math.isclose(value, 1.0, abs_tol=EPS)


# -----------------------------------------------------------------------------
# Population shares and volume conservation
# -----------------------------------------------------------------------------


def test_persona_population_share_sums_to_one():
    assert _approx_one(sum(PERSONA_POPULATION_SHARE.values()))


def test_persona_population_share_covers_all_personas():
    assert set(PERSONA_POPULATION_SHARE.keys()) == set(Persona)


def test_channel_target_volume_sums_to_total_leads_default():
    assert sum(CHANNEL_TARGET_VOLUME.values()) == TOTAL_LEADS_DEFAULT


def test_channel_target_volume_covers_all_channels():
    assert set(CHANNEL_TARGET_VOLUME.keys()) == set(Channel)


def test_linkedin_campaign_volume_sums_to_linkedin_paid_target():
    assert sum(LINKEDIN_CAMPAIGN_VOLUME.values()) == CHANNEL_TARGET_VOLUME[Channel.LINKEDIN_PAID]


def test_linkedin_campaign_volume_covers_all_named_campaigns():
    assert set(LINKEDIN_CAMPAIGN_VOLUME.keys()) == set(LINKEDIN_CAMPAIGNS)


# -----------------------------------------------------------------------------
# Persona × channel × theme affinity rankings
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("channel", list(Channel))
def test_channel_persona_affinity_ranks_all_four_personas(channel: Channel):
    ranking = CHANNEL_PERSONA_AFFINITY[channel]
    assert len(ranking) == 4
    assert set(ranking) == set(Persona)


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_theme_affinity_has_five_unique_themes(persona: Persona):
    ranking = PERSONA_THEME_AFFINITY[persona]
    assert len(ranking) == 5
    assert len(set(ranking)) == 5
    for theme in ranking:
        assert isinstance(theme, Theme)


# -----------------------------------------------------------------------------
# Persona attribute distributions
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_industry_weights_sum_to_one(persona: Persona):
    weights = PERSONA_INDUSTRY_WEIGHTS[persona]
    assert _approx_one(sum(weights.values()))


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_industry_weights_reference_known_industries(persona: Persona):
    weights = PERSONA_INDUSTRY_WEIGHTS[persona]
    for industry in weights:
        assert industry in INDUSTRIES


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_seniority_weights_sum_to_one(persona: Persona):
    weights = PERSONA_SENIORITY_WEIGHTS[persona]
    assert _approx_one(sum(weights.values()))


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_company_size_range_is_valid(persona: Persona):
    lo, hi = PERSONA_COMPANY_SIZE_RANGE[persona]
    assert lo > 0
    assert hi > lo


# -----------------------------------------------------------------------------
# Persona titles
# -----------------------------------------------------------------------------


def test_persona_titles_cover_all_personas():
    assert set(PERSONA_TITLES.keys()) == set(Persona)


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_title_subpools_match_sampled_seniorities(persona: Persona):
    """Every sampled seniority has a title sub-pool, and no sub-pool exists
    for a seniority the persona never samples. This is what makes the
    two-step (seniority -> title) draw in personas.py KeyError-safe."""
    assert set(PERSONA_TITLES[persona].keys()) == set(
        PERSONA_SENIORITY_WEIGHTS[persona].keys()
    )


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_titles_at_least_two_per_subpool(persona: Persona):
    for seniority, titles in PERSONA_TITLES[persona].items():
        assert len(titles) >= 2, f"{persona}/{seniority} has {len(titles)} titles"


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_titles_at_least_three_per_persona(persona: Persona):
    total = sum(len(titles) for titles in PERSONA_TITLES[persona].values())
    assert total >= 3


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_titles_unique_within_persona(persona: Persona):
    flat = [t for pool in PERSONA_TITLES[persona].values() for t in pool]
    assert len(flat) == len(set(flat))


def test_persona_titles_no_cross_persona_overlap():
    seen: dict[str, Persona] = {}
    for persona, subpools in PERSONA_TITLES.items():
        for titles in subpools.values():
            for title in titles:
                assert title not in seen, (
                    f"title {title!r} appears for both {seen[title]} and {persona}"
                )
                seen[title] = persona


# -----------------------------------------------------------------------------
# Outcome distributions
# -----------------------------------------------------------------------------


def test_baseline_outcome_mix_sums_to_one():
    assert _approx_one(sum(BASELINE_OUTCOME_MIX.values()))


def test_baseline_outcome_mix_covers_all_outcomes():
    assert set(BASELINE_OUTCOME_MIX.keys()) == set(Outcome)


@pytest.mark.parametrize("persona", list(Persona))
def test_broad_funnel_persona_outcomes_sum_to_one(persona: Persona):
    dist = BROAD_FUNNEL_PERSONA_OUTCOMES[persona]
    assert _approx_one(sum(dist.values()))


@pytest.mark.parametrize("persona", list(Persona))
def test_broad_funnel_persona_outcomes_covers_all_outcomes(persona: Persona):
    dist = BROAD_FUNNEL_PERSONA_OUTCOMES[persona]
    assert set(dist.keys()) == set(Outcome)


@pytest.mark.parametrize("persona", list(Persona))
def test_broad_funnel_wfl_fraction_in_range(persona: Persona):
    f = BROAD_FUNNEL_WFL_FRACTION_OF_LOST[persona]
    assert 0.0 <= f <= 1.0


def test_persona_ghost_share_covers_all_personas():
    assert set(PERSONA_GHOST_SHARE_OF_NON_WINS.keys()) == set(Persona)
    for share in PERSONA_GHOST_SHARE_OF_NON_WINS.values():
        assert 0.0 <= share <= 1.0


# -----------------------------------------------------------------------------
# linkedin_paid within-channel campaign mix
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("campaign", list(LINKEDIN_CAMPAIGNS))
def test_linkedin_campaign_persona_mix_sums_to_one(campaign: str):
    mix = LINKEDIN_CAMPAIGN_PERSONA_MIX[campaign]
    assert _approx_one(sum(mix.values()))


@pytest.mark.parametrize("campaign", list(LINKEDIN_CAMPAIGNS))
def test_linkedin_campaign_persona_mix_covers_all_personas(campaign: str):
    mix = LINKEDIN_CAMPAIGN_PERSONA_MIX[campaign]
    assert set(mix.keys()) == set(Persona)


def test_broad_funnel_is_the_highest_volume_campaign():
    """Finding 4 assumes broad_funnel is the highest-volume utm_campaign."""
    top = max(LINKEDIN_CAMPAIGN_VOLUME, key=LINKEDIN_CAMPAIGN_VOLUME.get)
    assert top == "linkedin_q2_broad_funnel"


# -----------------------------------------------------------------------------
# Content asset library coverage
# -----------------------------------------------------------------------------


def test_all_assets_has_expected_count():
    """16 named assets across 6 categories: 3 podcasts + 6 blogs + 3 LI + 2 webinars
    + 6 newsletter editions + 1 comparison = 21. Note: 16 was for the data-world.md
    intro counting only the explicitly-listed unique assets. With the 6 generated
    newsletter editions counted individually, total = 21.
    """
    assert (
        len(ALL_ASSETS)
        == len(PODCAST_EPISODES) + len(BLOG_POSTS) + len(LINKEDIN_CAMPAIGNS)
        + len(WEBINARS) + len(NEWSLETTER_EDITIONS) + len(COMPARISON_PAGES)
    )


def test_every_asset_has_theme_mapping():
    for slug in ALL_ASSETS:
        assert slug in ASSET_THEME


def test_every_asset_has_channel_mapping():
    for slug in ALL_ASSETS:
        assert slug in ASSET_CHANNEL


def test_asset_theme_value_is_theme_or_none():
    for slug, theme in ASSET_THEME.items():
        assert theme is None or isinstance(theme, Theme), (
            f"{slug} has non-Theme value {theme}"
        )


def test_only_broad_funnel_has_none_theme():
    """Only the broad LinkedIn campaign is mixed; everything else has a primary theme."""
    none_themed = [slug for slug, theme in ASSET_THEME.items() if theme is None]
    assert none_themed == ["linkedin_q2_broad_funnel"]


# -----------------------------------------------------------------------------
# Channel baseline CW rates
# -----------------------------------------------------------------------------


def test_channel_baseline_cw_rate_covers_all_channels():
    assert set(CHANNEL_BASELINE_CW_RATE.keys()) == set(Channel)


def test_channel_baseline_cw_rates_in_range():
    for channel, rate in CHANNEL_BASELINE_CW_RATE.items():
        assert 0.0 <= rate <= 1.0, f"{channel} CW rate {rate} out of range"


def test_podcast_is_highest_baseline_cw():
    """Finding 1 assumes podcast is the high-quality channel."""
    top = max(CHANNEL_BASELINE_CW_RATE, key=CHANNEL_BASELINE_CW_RATE.get)
    assert top == Channel.PODCAST


def test_linkedin_paid_is_lowest_baseline_cw():
    """Finding 1 assumes linkedin_paid is the low-quality channel."""
    bottom = min(CHANNEL_BASELINE_CW_RATE, key=CHANNEL_BASELINE_CW_RATE.get)
    assert bottom == Channel.LINKEDIN_PAID


# -----------------------------------------------------------------------------
# Theme anchor vocabulary and bridge pairs
# -----------------------------------------------------------------------------


def test_theme_anchor_vocab_covers_all_themes():
    assert set(THEME_ANCHOR_VOCAB.keys()) == set(Theme)


def test_theme_anchors_nonempty_lowercase_unique():
    for theme, anchors in THEME_ANCHOR_VOCAB.items():
        assert anchors, theme
        assert len(anchors) == len(set(anchors)), theme
        for anchor in anchors:
            assert anchor == anchor.lower(), anchor
            assert anchor.strip(), theme


def test_theme_anchors_disjoint_across_themes():
    """An anchor belongs to exactly one theme — else it is ambient, not an
    anchor, and would break copy_bank's lexical-separation enforcement."""
    seen: dict[str, Theme] = {}
    for theme, anchors in THEME_ANCHOR_VOCAB.items():
        for anchor in anchors:
            assert anchor not in seen, (
                f"anchor {anchor!r} appears for both {seen[anchor]} and {theme}"
            )
            seen[anchor] = theme


def test_theme_bridge_pairs_distinct_and_unique():
    seen: set[tuple[Theme, Theme]] = set()
    for primary, secondary in THEME_BRIDGE_PAIRS:
        assert primary != secondary, (primary, secondary)
        assert (primary, secondary) not in seen
        assert (secondary, primary) not in seen, f"reverse-duplicate {primary}/{secondary}"
        seen.add((primary, secondary))


# -----------------------------------------------------------------------------
# Per-persona seed-theme share distribution
# -----------------------------------------------------------------------------


def test_persona_theme_share_covers_all_personas():
    assert set(PERSONA_THEME_SHARE.keys()) == set(Persona)


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_theme_share_covers_all_themes(persona: Persona):
    assert set(PERSONA_THEME_SHARE[persona].keys()) == set(Theme)


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_theme_share_sums_to_one(persona: Persona):
    assert _approx_one(sum(PERSONA_THEME_SHARE[persona].values()))


def test_persona_theme_share_engineered_cells_hit_targets():
    """F2 and F5 cell sizes — locked here to catch silent drift before
    test_aha_patterns.py. Each cell is round(share * persona population)."""
    pop = {
        p: round(TOTAL_LEADS_DEFAULT * PERSONA_POPULATION_SHARE[p])
        for p in Persona
    }
    share = PERSONA_THEME_SHARE
    maya_mwr = round(
        pop[Persona.MAYA] * share[Persona.MAYA][Theme.MANUAL_WORK_REDUCTION]
    )
    patricia_compliance = round(
        pop[Persona.PATRICIA] * share[Persona.PATRICIA][Theme.COMPLIANCE_SECURITY]
    )
    non_maya_mwr = sum(
        round(pop[p] * share[p][Theme.MANUAL_WORK_REDUCTION])
        for p in Persona
        if p is not Persona.MAYA
    )
    non_patricia_compliance = sum(
        round(pop[p] * share[p][Theme.COMPLIANCE_SECURITY])
        for p in Persona
        if p is not Persona.PATRICIA
    )
    assert maya_mwr == 280  # F2 target cell
    assert patricia_compliance == 260  # F5 target cell
    assert non_maya_mwr == 209  # F2 comparison cell (aha-patterns threshold >= 100)
    assert non_patricia_compliance == 111  # F5 comparison cell (threshold >= 80)
