"""test_noise_tolerance.py — v1.5 §6.3 degradation-curve contract.

Parametrized over noise multipliers {1.0, 2.0, 4.0}, regenerates the
dataset and counts how many of the five F-findings still recover. The
multiplier-to-floor tiers define the degradation curve the Phase 3
README publishes:

  1.0x  -> all 5 findings recover (the §6.1 contract).
  2.0x  -> at least 3 findings recover (graceful degradation).
  4.0x  -> at least 1 finding recovers (the system has not collapsed).

This file holds its own F1-F5 evaluators rather than importing from
test_aha_patterns — the per-finding assertions there are pytest
functions, not boolean evaluators. The duplication is intentional and
documented; refactoring into a shared findings-evaluator module is a
Phase 2+ concern.
"""

from collections import Counter
from datetime import timedelta

import pytest

from ica.generator.channels import assign_channels
from ica.generator.journeys import build_journeys
from ica.generator.noise import apply_noise
from ica.generator.outcomes import build_outcomes
from ica.generator.personas import sample_personas
from ica.taxonomy import (
    DEFAULT_SEED,
    F3_PATH_WITHIN_DAYS,
    F4_TARGET_CAMPAIGN,
    REALISTIC,
    Channel,
    EventType,
    Outcome,
    Persona,
    Theme,
)

# -----------------------------------------------------------------------------
# Per-finding evaluators — mirror the contract thresholds in
# test_aha_patterns.py. Each returns True iff the F-finding passes.
# -----------------------------------------------------------------------------


def _won_rate(lead_ids, outcome_of) -> float:
    ids = list(lead_ids)
    if not ids:
        return 0.0
    return sum(outcome_of.get(i) == Outcome.CLOSED_WON for i in ids) / len(ids)


def _f3_path(leads, touchpoints) -> set[str]:
    created = {lead.lead_id: lead.created_at for lead in leads}
    channel = {lead.lead_id: lead.created_via_channel for lead in leads}
    by_lead: dict[str, list] = {}
    for tp in touchpoints:
        by_lead.setdefault(tp.lead_id, []).append(tp)
    path: set[str] = set()
    for lead_id, tps in by_lead.items():
        if channel.get(lead_id) != Channel.PODCAST:
            continue
        if created.get(lead_id) is None:
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


def _evaluate_findings(leads, touchpoints, outcomes) -> dict[str, bool]:
    outcome_of = {o.lead_id: o.outcome for o in outcomes}
    sub_of = {o.lead_id: o.sub_reason for o in outcomes}
    results: dict[str, bool] = {}

    # F1 — channel quality differential
    podcast = [lead.lead_id for lead in leads if lead.created_via_channel == Channel.PODCAST]
    linkedin = [
        lead.lead_id for lead in leads if lead.created_via_channel == Channel.LINKEDIN_PAID
    ]
    podcast_cw = _won_rate(podcast, outcome_of)
    linkedin_cw = _won_rate(linkedin, outcome_of)
    results["F1"] = (
        len(podcast) <= 250
        and len(linkedin) >= 800
        and podcast_cw >= 0.25
        and 0.0 < linkedin_cw <= 0.05
        and linkedin_cw > 0
        and podcast_cw / linkedin_cw >= 6.0
    )

    # F2 — Maya x MWR resonance
    target = [
        lead.lead_id for lead in leads
        if lead.persona == Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    ]
    other = [
        lead.lead_id for lead in leads
        if lead.persona != Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    ]
    target_rate = _won_rate(target, outcome_of)
    other_rate = _won_rate(other, outcome_of)
    results["F2"] = (
        len(target) >= 100
        and len(other) >= 100
        and other_rate > 0
        and target_rate / other_rate >= 3.0
    )

    # F3 — multi-touch path
    path = _f3_path(leads, touchpoints)
    overall = _won_rate([lead.lead_id for lead in leads], outcome_of)
    results["F3"] = (
        len(path) >= 30
        and overall > 0
        and _won_rate(path, outcome_of) / overall >= 4.0
    )

    # F4 — broad-funnel bad-outcome share + ICP ratio
    volumes = Counter(
        lead.first_touch_utm_campaign for lead in leads if lead.first_touch_utm_campaign
    )
    top_camp = volumes.most_common(1)[0][0] if volumes else None
    top = {
        lead.lead_id for lead in leads
        if lead.first_touch_utm_campaign == F4_TARGET_CAMPAIGN
    }
    if not top:
        results["F4"] = False
    else:
        bad = sum(
            1 for i in top
            if outcome_of.get(i) in (Outcome.DISQUALIFIED, Outcome.GHOSTED)
            or (outcome_of.get(i) == Outcome.CLOSED_LOST and sub_of.get(i) == "wrong_fit_late")
        )
        top_icp = sum(lead.icp_fit_score for lead in leads if lead.lead_id in top) / len(top)
        ds_icp = sum(lead.icp_fit_score for lead in leads) / len(leads)
        results["F4"] = (
            top_camp == F4_TARGET_CAMPAIGN
            and bad / len(top) >= 0.65
            and top_icp / ds_icp <= 0.75
        )

    # F5 — Patricia x compliance_security
    pat = [
        lead.lead_id for lead in leads
        if lead.persona == Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    ]
    other = [
        lead.lead_id for lead in leads
        if lead.persona != Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    ]
    pat_rate = _won_rate(pat, outcome_of)
    other_rate = _won_rate(other, outcome_of)
    results["F5"] = (
        len(pat) >= 100
        and len(other) >= 80
        and other_rate > 0
        and pat_rate / other_rate >= 2.0
    )

    return results


# -----------------------------------------------------------------------------
# Regen + parametrize
# -----------------------------------------------------------------------------


def _regen_at(multiplier: float):
    """Generate a fresh dataset at REALISTIC.scaled(multiplier)."""
    leads = sample_personas()
    assign_channels(leads)
    touchpoints, form_submissions = build_journeys(leads)
    outcomes, sales_notes = build_outcomes(leads, touchpoints)
    lead_rows = [lead.to_lead() for lead in leads]
    profile = REALISTIC.scaled(multiplier) if multiplier > 0 else REALISTIC.scaled(0)
    lead_rows, touchpoints, _fs, _sn, outcomes, _manifest = apply_noise(
        lead_rows, touchpoints, form_submissions, sales_notes, outcomes,
        profile=profile, seed=DEFAULT_SEED,
    )
    return lead_rows, touchpoints, outcomes


@pytest.mark.parametrize(
    "multiplier,min_passing",
    [
        (1.0, 5),   # default REALISTIC — all 5 hold (the §6.1 contract)
        (2.0, 3),   # 2x stress — graceful degradation
        (4.0, 1),   # 4x stress — system has not collapsed
    ],
)
def test_findings_recovery_under_noise(multiplier, min_passing):
    leads, touchpoints, outcomes = _regen_at(multiplier)
    results = _evaluate_findings(leads, touchpoints, outcomes)
    passing = sum(results.values())
    assert passing >= min_passing, (
        f"at noise x{multiplier}: only {passing}/5 findings recovered: {results}"
    )
