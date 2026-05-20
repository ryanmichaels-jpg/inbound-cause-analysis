"""channels.py — channel, campaign, and created_at assignment tests."""

from collections import Counter
from datetime import datetime

import pytest

from ica.generator.channels import _campaign_persona_counts, assign_channels
from ica.generator.personas import sample_personas
from ica.taxonomy import (
    CHANNEL_TARGET_VOLUME,
    LINKEDIN_CAMPAIGN_PERSONA_MIX,
    LINKEDIN_CAMPAIGN_VOLUME,
    LINKEDIN_CAMPAIGNS,
    PERSONA_POPULATION_SHARE,
    TOTAL_LEADS_DEFAULT,
    Channel,
    Persona,
)


@pytest.fixture(scope="module")
def leads():
    return assign_channels(sample_personas())


# --- channel volumes & coverage ----------------------------------------------


@pytest.mark.parametrize("channel", list(Channel))
def test_channel_volume_exact(leads, channel):
    count = sum(1 for lead in leads if lead.created_via_channel == channel)
    assert count == CHANNEL_TARGET_VOLUME[channel]


def test_every_lead_has_channel_and_created_at(leads):
    for lead in leads:
        assert lead.created_via_channel is not None
        assert lead.created_at is not None


def test_persona_totals_unchanged(leads):
    counts = Counter(lead.persona for lead in leads)
    for persona in Persona:
        expected = round(TOTAL_LEADS_DEFAULT * PERSONA_POPULATION_SHARE[persona])
        assert counts[persona] == expected


# --- linkedin campaigns ------------------------------------------------------


@pytest.mark.parametrize("campaign", list(LINKEDIN_CAMPAIGNS))
def test_linkedin_campaign_volume_exact(leads, campaign):
    count = sum(1 for lead in leads if lead.first_touch_utm_campaign == campaign)
    assert count == LINKEDIN_CAMPAIGN_VOLUME[campaign]


def test_linkedin_campaign_persona_counts_match_largest_remainder(leads):
    for campaign in LINKEDIN_CAMPAIGNS:
        expected = _campaign_persona_counts(
            LINKEDIN_CAMPAIGN_VOLUME[campaign],
            LINKEDIN_CAMPAIGN_PERSONA_MIX[campaign],
        )
        actual = Counter(
            lead.persona
            for lead in leads
            if lead.first_touch_utm_campaign == campaign
        )
        for persona in Persona:
            assert actual[persona] == expected[persona]


def test_linkedin_persona_consumption(leads):
    """The headline feasibility totals from the planning header."""
    linkedin = Counter(
        lead.persona
        for lead in leads
        if lead.created_via_channel == Channel.LINKEDIN_PAID
    )
    assert linkedin == {
        Persona.MAYA: 151,
        Persona.DAVID: 134,
        Persona.PATRICIA: 342,
        Persona.CARLOS: 373,
    }


def test_largest_remainder_tiebreak_enterprise():
    counts = _campaign_persona_counts(
        LINKEDIN_CAMPAIGN_VOLUME["linkedin_q2_enterprise"],
        LINKEDIN_CAMPAIGN_PERSONA_MIX["linkedin_q2_enterprise"],
    )
    assert counts == {
        Persona.MAYA: 38,
        Persona.DAVID: 37,
        Persona.PATRICIA: 150,
        Persona.CARLOS: 25,
    }


def test_largest_remainder_tiebreak_revops():
    counts = _campaign_persona_counts(
        LINKEDIN_CAMPAIGN_VOLUME["linkedin_q2_revops_targeted"],
        LINKEDIN_CAMPAIGN_PERSONA_MIX["linkedin_q2_revops_targeted"],
    )
    assert counts == {
        Persona.MAYA: 83,
        Persona.DAVID: 37,
        Persona.PATRICIA: 12,
        Persona.CARLOS: 18,
    }


def test_campaign_set_only_on_linkedin_leads(leads):
    for lead in leads:
        if lead.created_via_channel == Channel.LINKEDIN_PAID:
            assert lead.first_touch_utm_campaign in set(LINKEDIN_CAMPAIGNS)
        else:
            assert lead.first_touch_utm_campaign is None


# --- created_at envelope -----------------------------------------------------


def test_created_at_within_window(leads):
    lo = datetime(2026, 1, 1)
    hi = datetime(2026, 7, 1)
    for lead in leads:
        assert lo <= lead.created_at < hi


def test_created_at_weekday_heavier_than_weekend(leads):
    weekday = sum(1 for lead in leads if lead.created_at.weekday() < 5)
    weekend = len(leads) - weekday
    # 5 weekdays vs 2 weekend days, weekend down-weighted — weekdays dominate.
    assert weekday > weekend * 2


def test_created_at_growth_trend(leads):
    by_month = Counter(lead.created_at.month for lead in leads)
    assert by_month[6] > by_month[1]


# --- determinism -------------------------------------------------------------


def test_assignment_is_deterministic():
    run_a = assign_channels(sample_personas())
    run_b = assign_channels(sample_personas())
    for lead_a, lead_b in zip(run_a, run_b, strict=True):
        assert lead_a.created_via_channel == lead_b.created_via_channel
        assert lead_a.first_touch_utm_campaign == lead_b.first_touch_utm_campaign
        assert lead_a.created_at == lead_b.created_at
