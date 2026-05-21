"""The five aha-pattern contract assertions — the CP1 acceptance contract.

Each Finding test asserts the verbatim smoke-test thresholds from
docs/aha-patterns.md (per §3 of that doc: "the smoke-test assertion is the
contract"). The thresholds are deliberately looser than the engineered
targets so the contract survives reasonable seed variation. Two
composition-invariant tests and one dataset-distribution test follow.
"""

from collections import Counter
from datetime import timedelta

import pytest

from ica.generator.channels import assign_channels
from ica.generator.journeys import build_journeys
from ica.generator.outcomes import build_outcomes
from ica.generator.personas import sample_personas
from ica.taxonomy import (
    F3_PATH_WITHIN_DAYS,
    F4_TARGET_CAMPAIGN,
    Channel,
    EventType,
    Outcome,
    Persona,
    Theme,
)


@pytest.fixture(scope="module")
def dataset():
    leads = sample_personas()
    assign_channels(leads)
    touchpoints, _ = build_journeys(leads)
    outcomes, _ = build_outcomes(leads, touchpoints)
    return leads, touchpoints, outcomes


def _won_rate(lead_ids, outcome_of):
    ids = list(lead_ids)
    return sum(outcome_of[i] == Outcome.CLOSED_WON for i in ids) / len(ids)


def _f3_path(leads, touchpoints):
    created = {lead.lead_id: lead.created_at for lead in leads}
    channel = {lead.lead_id: lead.created_via_channel for lead in leads}
    by_lead: dict[str, list] = {}
    for tp in touchpoints:
        by_lead.setdefault(tp.lead_id, []).append(tp)
    path = set()
    for lead_id, tps in by_lead.items():
        if channel[lead_id] != Channel.PODCAST:
            continue
        horizon = created[lead_id] + timedelta(days=F3_PATH_WITHIN_DAYS)
        has_organic = any(
            t.channel == Channel.ORGANIC_SEARCH and t.ts <= horizon for t in tps
        )
        has_demo = any(
            t.event_type == EventType.DEMO_REQUEST and t.ts <= horizon for t in tps
        )
        if has_organic and has_demo:
            path.add(lead_id)
    return path


# --- the five Finding contracts ----------------------------------------------


def test_f1_channel_quality_differential(dataset):
    """Finding 1 (aha-patterns.md F1) — a low-volume channel (podcast) drives
    high-value pipeline; a high-volume channel (linkedin_paid) drives
    tire-kickers. Engineered 0.30 / 0.03; contract thresholds below."""
    leads, _, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    podcast = [lead.lead_id for lead in leads if lead.created_via_channel == Channel.PODCAST]
    linkedin = [
        lead.lead_id for lead in leads if lead.created_via_channel == Channel.LINKEDIN_PAID
    ]
    assert len(podcast) <= 250
    assert len(linkedin) >= 800
    podcast_cw = _won_rate(podcast, outcome_of)
    linkedin_cw = _won_rate(linkedin, outcome_of)
    assert podcast_cw >= 0.25, podcast_cw
    assert 0.0 < linkedin_cw <= 0.05, linkedin_cw
    assert podcast_cw / linkedin_cw >= 6.0


def test_f2_maya_mwr_resonance(dataset):
    """Finding 2 (aha-patterns.md F2) — manual_work_reduction resonates ~3x
    harder with Maya than with other personas. Engineered cell 0.25."""
    leads, _, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    target = [
        lead.lead_id
        for lead in leads
        if lead.persona == Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    ]
    other = [
        lead.lead_id
        for lead in leads
        if lead.persona != Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    ]
    assert len(target) >= 100
    assert len(other) >= 100
    target_rate = _won_rate(target, outcome_of)
    other_rate = _won_rate(other, outcome_of)
    assert other_rate > 0
    assert target_rate / other_rate >= 3.0


def test_f3_multitouch_path(dataset):
    """Finding 3 (aha-patterns.md F3) — the podcast -> organic_search -> demo
    journey within 14 days converts at ~4x the dataset average. Engineered
    path 0.45."""
    leads, touchpoints, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    path = _f3_path(leads, touchpoints)
    assert len(path) >= 30
    overall = _won_rate([lead.lead_id for lead in leads], outcome_of)
    assert overall > 0
    assert _won_rate(path, outcome_of) / overall >= 4.0


def test_f4_broad_funnel_bad_outcome(dataset):
    """Finding 4 (aha-patterns.md F4) — the highest-volume campaign brings in
    mostly non-ICP leads. Engineered bad-share ~0.78, ICP ratio ~0.685."""
    leads, _, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    sub_of = {o.lead_id: o.sub_reason for o in outcomes}
    volumes = Counter(
        lead.first_touch_utm_campaign for lead in leads if lead.first_touch_utm_campaign
    )
    assert volumes.most_common(1)[0][0] == F4_TARGET_CAMPAIGN
    top = {lead.lead_id for lead in leads if lead.first_touch_utm_campaign == F4_TARGET_CAMPAIGN}
    bad = sum(
        1
        for i in top
        if outcome_of[i] in (Outcome.DISQUALIFIED, Outcome.GHOSTED)
        or (outcome_of[i] == Outcome.CLOSED_LOST and sub_of[i] == "wrong_fit_late")
    )
    assert bad / len(top) >= 0.65
    top_icp = sum(lead.icp_fit_score for lead in leads if lead.lead_id in top) / len(top)
    dataset_icp = sum(lead.icp_fit_score for lead in leads) / len(leads)
    assert top_icp / dataset_icp <= 0.75


def test_f5_patricia_compliance(dataset):
    """Finding 5 (aha-patterns.md Secondary Finding) — compliance_security
    resonates with Patricia. Softer 2.0x contract; engineered cell 0.18."""
    leads, _, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    target = [
        lead.lead_id
        for lead in leads
        if lead.persona == Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    ]
    other = [
        lead.lead_id
        for lead in leads
        if lead.persona != Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    ]
    assert len(target) >= 100
    assert len(other) >= 80
    target_rate = _won_rate(target, outcome_of)
    other_rate = _won_rate(other, outcome_of)
    assert other_rate > 0
    assert target_rate / other_rate >= 2.0


# --- composition invariants --------------------------------------------------


def test_compensation_non_path_podcast(dataset):
    """Composition invariant (aha-patterns.md F3 "How seed.py applies") — F3
    rebalances non-path podcast leads to ~25.3% so the podcast channel mean
    stays ~30%, Finding 1's cap. Tolerance band 0.20-0.32."""
    leads, touchpoints, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    path = _f3_path(leads, touchpoints)
    non_path = [
        lead.lead_id
        for lead in leads
        if lead.created_via_channel == Channel.PODCAST and lead.lead_id not in path
    ]
    assert 0.20 <= _won_rate(non_path, outcome_of) <= 0.32


def test_compensation_non_path_maya_mwr(dataset):
    """Composition invariant — non-path Maya x mwr leads carry the F2 cell to
    0.25 while linkedin members stay capped; the non-path subset lands near
    0.247. Tolerance band 0.18-0.32."""
    leads, touchpoints, outcomes = dataset
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    path = _f3_path(leads, touchpoints)
    non_path = [
        lead.lead_id
        for lead in leads
        if lead.persona == Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
        and lead.lead_id not in path
    ]
    assert 0.18 <= _won_rate(non_path, outcome_of) <= 0.32


def test_dataset_outcome_distribution(dataset):
    """Post-skew dataset mix — closed_won ~7.1% (aha-patterns.md F3),
    ghosted ~24% (data-world.md §5). Tolerance bands below."""
    _, _, outcomes = dataset
    counts = Counter(o.outcome for o in outcomes)
    total = len(outcomes)
    assert 0.060 <= counts[Outcome.CLOSED_WON] / total <= 0.085
    assert 0.21 <= counts[Outcome.GHOSTED] / total <= 0.28
