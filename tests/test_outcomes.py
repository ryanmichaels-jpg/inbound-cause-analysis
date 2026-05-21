"""outcomes.py — structural unit tests. The five aha-pattern contract
assertions live separately in test_aha_patterns.py."""

from collections import Counter

import pytest

from ica.generator.channels import assign_channels
from ica.generator.journeys import build_journeys
from ica.generator.outcomes import _DAYS_BAND, build_outcomes
from ica.generator.personas import sample_personas
from ica.taxonomy import (
    CLOSED_LOST_SUB_REASONS,
    DISQUALIFIED_SUB_REASONS,
    NURTURE_SUB_REASONS,
    EventType,
    Outcome,
    Theme,
)


@pytest.fixture(scope="module")
def built():
    leads = sample_personas()
    assign_channels(leads)
    touchpoints, _ = build_journeys(leads)
    outcomes, sales_notes = build_outcomes(leads, touchpoints)
    return leads, touchpoints, outcomes, sales_notes


def test_one_outcome_per_lead(built):
    leads, _, outcomes, _ = built
    assert len(outcomes) == len(leads)
    assert {o.lead_id for o in outcomes} == {lead.lead_id for lead in leads}


def test_outcome_values_are_valid(built):
    _, _, outcomes, _ = built
    for row in outcomes:
        assert row.outcome in set(Outcome)


def test_pipeline_value_rules(built):
    _, _, outcomes, _ = built
    for row in outcomes:
        if row.outcome == Outcome.CLOSED_WON:
            assert 40_000 <= row.pipeline_value_usd <= 200_000
        elif row.outcome == Outcome.CLOSED_LOST:
            assert 30_000 <= row.pipeline_value_usd <= 150_000
        else:
            assert row.pipeline_value_usd is None


def test_sub_reason_rules(built):
    _, _, outcomes, _ = built
    for row in outcomes:
        if row.outcome in (Outcome.CLOSED_WON, Outcome.GHOSTED):
            assert row.sub_reason is None
        elif row.outcome == Outcome.CLOSED_LOST:
            assert row.sub_reason in CLOSED_LOST_SUB_REASONS
        elif row.outcome == Outcome.DISQUALIFIED:
            assert row.sub_reason in DISQUALIFIED_SUB_REASONS
        else:
            assert row.sub_reason in NURTURE_SUB_REASONS


def test_resolved_at_and_days_bands(built):
    leads, _, outcomes, _ = built
    created = {lead.lead_id: lead.created_at for lead in leads}
    for row in outcomes:
        lo, hi = _DAYS_BAND[row.outcome]
        assert lo <= row.days_to_outcome < hi
        delta = (row.resolved_at - created[row.lead_id]).days
        assert delta == row.days_to_outcome


def test_sales_notes_gating(built):
    leads, touchpoints, outcomes, sales_notes = built
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    demo_leads = {
        tp.lead_id
        for tp in touchpoints
        if tp.event_type in (EventType.DEMO_REQUEST, EventType.DEMO_ATTENDED)
    }
    note_lead_ids = [note.lead_id for note in sales_notes]
    # one note per lead at most
    assert len(note_lead_ids) == len(set(note_lead_ids))
    for note in sales_notes:
        assert outcome_of[note.lead_id] in (
            Outcome.CLOSED_WON,
            Outcome.CLOSED_LOST,
            Outcome.DISQUALIFIED,
        )
        assert note.lead_id in demo_leads
        assert note.kind in ("rep_note", "call_transcript_snippet")
        assert note.author in ("sdr", "ae", "sales_engineer")
        assert note.ground_truth_themes
        assert note.ground_truth_themes[0] in set(Theme)


def test_dataset_closed_won_in_range(built):
    _, _, outcomes, _ = built
    counts = Counter(o.outcome for o in outcomes)
    cw_rate = counts[Outcome.CLOSED_WON] / len(outcomes)
    # post-skew dataset CW ~7.1% (aha-patterns.md F3)
    assert 0.06 <= cw_rate <= 0.085


def test_build_is_deterministic():
    leads_a = sample_personas()
    assign_channels(leads_a)
    tps_a, _ = build_journeys(leads_a)
    out_a, notes_a = build_outcomes(leads_a, tps_a)
    leads_b = sample_personas()
    assign_channels(leads_b)
    tps_b, _ = build_journeys(leads_b)
    out_b, notes_b = build_outcomes(leads_b, tps_b)
    assert out_a == out_b
    assert notes_a == notes_b
