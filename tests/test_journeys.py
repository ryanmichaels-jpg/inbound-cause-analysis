"""journeys.py — touchpoint, form-submission, and seed-theme tests."""

from collections import Counter, defaultdict
from datetime import timedelta

import pytest

from ica.generator.channels import assign_channels
from ica.generator.journeys import _stratified_theme_counts, build_journeys
from ica.generator.personas import sample_personas
from ica.taxonomy import (
    F3_PATH_WITHIN_DAYS,
    F3_TARGET_PATH_COUNT,
    PERSONA_POPULATION_SHARE,
    PERSONA_THEME_SHARE,
    TOTAL_LEADS_DEFAULT,
    Channel,
    EventType,
    Persona,
    Theme,
)


@pytest.fixture(scope="module")
def built():
    leads = sample_personas()
    assign_channels(leads)
    touchpoints, submissions = build_journeys(leads)
    return leads, touchpoints, submissions


def _touchpoints_by_lead(touchpoints):
    grouped = defaultdict(list)
    for tp in touchpoints:
        grouped[tp.lead_id].append(tp)
    return grouped


def _f3_path_lead_ids(leads, touchpoints):
    created = {lead.lead_id: lead.created_at for lead in leads}
    channel = {lead.lead_id: lead.created_via_channel for lead in leads}
    grouped = _touchpoints_by_lead(touchpoints)
    path = set()
    for lead_id, tps in grouped.items():
        if channel[lead_id] != Channel.PODCAST:
            continue
        horizon = created[lead_id] + timedelta(days=F3_PATH_WITHIN_DAYS)
        has_organic = any(
            tp.channel == Channel.ORGANIC_SEARCH and tp.ts <= horizon for tp in tps
        )
        has_demo = any(
            tp.event_type == EventType.DEMO_REQUEST and tp.ts <= horizon for tp in tps
        )
        if has_organic and has_demo:
            path.add(lead_id)
    return path


# --- Finding 3 ---------------------------------------------------------------


def test_f3_path_cell_is_exactly_fifty(built):
    leads, touchpoints, _ = built
    assert len(_f3_path_lead_ids(leads, touchpoints)) == F3_TARGET_PATH_COUNT


def test_f3_path_leads_are_podcast_first_touch(built):
    leads, touchpoints, _ = built
    channel = {lead.lead_id: lead.created_via_channel for lead in leads}
    for lead_id in _f3_path_lead_ids(leads, touchpoints):
        assert channel[lead_id] == Channel.PODCAST


# --- Finding 2 / Finding 5 seed-theme cells ----------------------------------


def test_f2_maya_mwr_cell(built):
    leads, _, _ = built
    count = sum(
        1
        for lead in leads
        if lead.persona == Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    )
    assert count == 280


def test_f5_patricia_compliance_cell(built):
    leads, _, _ = built
    count = sum(
        1
        for lead in leads
        if lead.persona == Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    )
    assert count == 260


def test_theme_share_reproducibility(built):
    """Per-(persona, theme) seed counts match the stratified allocation."""
    leads, _, _ = built
    by_persona = defaultdict(list)
    for lead in leads:
        by_persona[lead.persona].append(lead)
    for persona, group in by_persona.items():
        expected = _stratified_theme_counts(len(group), PERSONA_THEME_SHARE[persona])
        actual = Counter(lead.seed_label_theme_primary for lead in group)
        for theme in Theme:
            assert actual[theme] == expected[theme], (persona, theme)


# --- seed-theme completeness -------------------------------------------------


def test_every_lead_has_a_primary_theme(built):
    leads, _, _ = built
    for lead in leads:
        assert lead.seed_label_theme_primary is not None
        secondary = lead.seed_label_theme_secondary
        assert secondary is None or isinstance(secondary, Theme)


def test_every_lead_finalizes_to_a_lead(built):
    leads, _, _ = built
    for lead in leads:
        lead.to_lead()  # raises if any deferred field is still unset


# --- touchpoint invariants ---------------------------------------------------


def test_touchpoint_first_last_and_monotonic(built):
    leads, touchpoints, _ = built
    grouped = _touchpoints_by_lead(touchpoints)
    assert set(grouped.keys()) == {lead.lead_id for lead in leads}
    for tps in grouped.values():
        assert sum(tp.is_first_touch for tp in tps) == 1
        assert sum(tp.is_last_touch for tp in tps) == 1
        timestamps = [tp.ts for tp in tps]
        assert timestamps == sorted(timestamps)
        assert len(tps) >= 2


def test_first_touch_contract(built):
    """The is_first_touch touchpoint replicates the lead exactly."""
    leads, touchpoints, _ = built
    by_lead = {lead.lead_id: lead for lead in leads}
    grouped = _touchpoints_by_lead(touchpoints)
    for lead_id, tps in grouped.items():
        first = next(tp for tp in tps if tp.is_first_touch)
        lead = by_lead[lead_id]
        assert first.ts == lead.created_at
        assert first.channel == lead.created_via_channel
        assert first.utm_campaign == lead.first_touch_utm_campaign


# --- form submissions --------------------------------------------------------


def test_one_form_submission_per_lead(built):
    leads, _, submissions = built
    assert len(submissions) == len(leads)
    assert {s.lead_id for s in submissions} == {lead.lead_id for lead in leads}


def test_form_submission_theme_labels_match_lead(built):
    leads, _, submissions = built
    by_lead = {lead.lead_id: lead for lead in leads}
    for submission in submissions:
        lead = by_lead[submission.lead_id]
        themes = submission.ground_truth_themes
        assert themes[0] == lead.seed_label_theme_primary
        if lead.seed_label_theme_secondary is None:
            assert len(themes) == 1
        else:
            assert themes == [
                lead.seed_label_theme_primary,
                lead.seed_label_theme_secondary,
            ]


# --- determinism -------------------------------------------------------------


def test_build_is_deterministic():
    leads_a = sample_personas()
    assign_channels(leads_a)
    tps_a, subs_a = build_journeys(leads_a)
    leads_b = sample_personas()
    assign_channels(leads_b)
    tps_b, subs_b = build_journeys(leads_b)
    assert tps_a == tps_b
    assert subs_a == subs_b
    assert [lead.seed_label_theme_primary for lead in leads_a] == [
        lead.seed_label_theme_primary for lead in leads_b
    ]


def test_population_unchanged(built):
    leads, _, _ = built
    assert len(leads) == TOTAL_LEADS_DEFAULT
    counts = Counter(lead.persona for lead in leads)
    for persona in Persona:
        assert counts[persona] == round(
            TOTAL_LEADS_DEFAULT * PERSONA_POPULATION_SHARE[persona]
        )
