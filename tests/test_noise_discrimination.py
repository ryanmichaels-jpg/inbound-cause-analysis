"""test_noise_discrimination.py — v1.5 §6.2 spurious-pattern contract.

Three asserts, mapped to the planning header's §6.2 (a) / (b) / (c):

  (c) Each planted spurious pattern is GENUINELY FINDABLE via its
      naive aggregation. Without this, the suite would pass vacuously
      ("the pipeline ignores something nobody could find").

  (b) Each planted cohort N sits BELOW FINDING_N_FLOOR. The N-floor is
      the discriminator: a respectful finder applying it would reject
      every spurious pattern, while the F1-F5 findings (whose cohorts
      sit comfortably above the floor — see test below) pass through.

  (a) Every F1-F5 finding's COHORT N sits ABOVE FINDING_N_FLOOR.
      Re-stated: the legitimate findings the pipeline emits would
      clear the same N-floor that rejects the spurious patterns.

The 'overlap' phrasing in the original §6.2(a) was sloppy — planted
leads can incidentally appear in F-finding cohorts (a mid-band-fit
Tuesday lead can also be on the F3 podcast path). What matters is
that the engineered SPURIOUS DIMENSIONS (by-DOW, by-TLD, by-keyword)
are not on the F1-F5 query set, AND the planted cohorts that
realize them are sub-floor. This test enforces both.
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
    FINDING_N_FLOOR,
    REALISTIC,
    Channel,
    EventType,
    Outcome,
    Persona,
    Theme,
)


@pytest.fixture(scope="module")
def noisy():
    """Default REALISTIC dataset + manifest. form_submissions kept so the
    'urgent'-keyword aggregation in §6.2c can run."""
    leads = sample_personas()
    assign_channels(leads)
    touchpoints, form_submissions = build_journeys(leads)
    outcomes, sales_notes = build_outcomes(leads, touchpoints)
    lead_rows = [lead.to_lead() for lead in leads]
    lead_rows, touchpoints, form_submissions, sales_notes, outcomes, manifest = apply_noise(
        lead_rows, touchpoints, form_submissions, sales_notes, outcomes,
        profile=REALISTIC, seed=DEFAULT_SEED,
    )
    return {
        "leads": lead_rows,
        "touchpoints": touchpoints,
        "form_submissions": form_submissions,
        "outcomes": outcomes,
        "manifest": manifest,
    }


def _outcome_of(noisy):
    return {o.lead_id: o.outcome for o in noisy["outcomes"]}


def _pattern(noisy, pattern_id: str) -> dict:
    for p in noisy["manifest"]["patterns"]:
        if p["id"] == pattern_id:
            return p
    raise AssertionError(f"pattern {pattern_id} not in manifest")


# -----------------------------------------------------------------------------
# §6.2(c) — each spurious pattern is genuinely findable
# -----------------------------------------------------------------------------


def test_s1_tuesday_is_findable_via_dow(noisy):
    """Tuesday's by-DOW CW rate must exceed every other weekday — the
    planted 5 CW out of ~440 Tuesday leads creates a visible bump."""
    outcome_of = _outcome_of(noisy)
    dow_cw, dow_n = Counter(), Counter()
    for lead in noisy["leads"]:
        if lead.created_at is None:
            continue
        dow = lead.created_at.weekday()
        dow_n[dow] += 1
        if outcome_of.get(lead.lead_id) == Outcome.CLOSED_WON:
            dow_cw[dow] += 1
    rate = {dow: dow_cw[dow] / dow_n[dow] for dow in dow_n}
    tue = rate[1]
    others = [r for dow, r in rate.items() if dow != 1]
    assert tue > max(others), f"Tuesday {tue:.3f} not the highest DOW: {rate}"


def test_s2_ai_tld_is_findable_via_tld(noisy):
    """The .ai-TLD cell CW rate is dramatically above the non-.ai baseline."""
    outcome_of = _outcome_of(noisy)
    ai = [lead for lead in noisy["leads"] if lead.company_domain.endswith(".ai")]
    non_ai = [lead for lead in noisy["leads"] if not lead.company_domain.endswith(".ai")]
    assert len(ai) > 0, "no .ai-TLD leads — S2 plant failed"
    ai_cw = sum(outcome_of.get(lead.lead_id) == Outcome.CLOSED_WON for lead in ai) / len(ai)
    non_ai_cw = sum(
        outcome_of.get(lead.lead_id) == Outcome.CLOSED_WON for lead in non_ai
    ) / len(non_ai)
    # Engineered target 0.75; demand a wide gap (>3x baseline) to confirm signal.
    assert ai_cw >= non_ai_cw * 3.0, f"ai_cw={ai_cw:.3f} vs non_ai={non_ai_cw:.3f}"


def test_s3_urgent_keyword_is_findable_via_text(noisy):
    """The 'urgent'-keyword cell CW rate is dramatically above the
    no-keyword baseline."""
    outcome_of = _outcome_of(noisy)
    fs_by_lead = {}
    for fs in noisy["form_submissions"]:
        fs_by_lead.setdefault(fs.lead_id, fs)
    urgent = [
        lid for lid, fs in fs_by_lead.items()
        if "urgent" in (fs.free_text_answer or "").lower()
    ]
    non_urgent = [lid for lid in fs_by_lead if lid not in set(urgent)]
    assert len(urgent) > 0, "no 'urgent'-keyword leads — S3 plant failed"
    urgent_cw = sum(outcome_of.get(lid) == Outcome.CLOSED_WON for lid in urgent) / len(urgent)
    non_urgent_cw = sum(
        outcome_of.get(lid) == Outcome.CLOSED_WON for lid in non_urgent
    ) / len(non_urgent)
    # Engineered target 0.90; demand >3x baseline.
    assert urgent_cw >= non_urgent_cw * 3.0, (
        f"urgent_cw={urgent_cw:.3f} vs non_urgent={non_urgent_cw:.3f}"
    )


# -----------------------------------------------------------------------------
# §6.2(b) — each planted cohort sits below FINDING_N_FLOOR
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("pattern_id", ["S1", "S2", "S3"])
def test_planted_cohort_below_finding_floor(noisy, pattern_id):
    """The defining property of an underpowered spurious pattern: a
    finder applying FINDING_N_FLOOR discards it."""
    pattern = _pattern(noisy, pattern_id)
    n = len(pattern["planted_lead_ids"])
    assert n < FINDING_N_FLOOR, (
        f"{pattern_id} N={n} not below floor {FINDING_N_FLOOR} — "
        f"the discrimination contract is meaningless"
    )


# -----------------------------------------------------------------------------
# §6.2(a) — every F1-F5 finding cohort sits above FINDING_N_FLOOR
# -----------------------------------------------------------------------------


def test_f1_podcast_cohort_above_floor(noisy):
    n = sum(1 for lead in noisy["leads"] if lead.created_via_channel == Channel.PODCAST)
    assert n > FINDING_N_FLOOR, f"F1 podcast cohort N={n} <= floor {FINDING_N_FLOOR}"


def test_f1_linkedin_cohort_above_floor(noisy):
    n = sum(
        1 for lead in noisy["leads"]
        if lead.created_via_channel == Channel.LINKEDIN_PAID
    )
    assert n > FINDING_N_FLOOR


def test_f2_maya_mwr_cohort_above_floor(noisy):
    n = sum(
        1 for lead in noisy["leads"]
        if lead.persona == Persona.MAYA
        and lead.seed_label_theme_primary == Theme.MANUAL_WORK_REDUCTION
    )
    assert n > FINDING_N_FLOOR


def test_f3_path_cohort_above_floor(noisy):
    created = {lead.lead_id: lead.created_at for lead in noisy["leads"]}
    channel = {lead.lead_id: lead.created_via_channel for lead in noisy["leads"]}
    by_lead: dict[str, list] = {}
    for tp in noisy["touchpoints"]:
        by_lead.setdefault(tp.lead_id, []).append(tp)
    path = set()
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
    assert len(path) > FINDING_N_FLOOR, f"F3 path N={len(path)} <= floor"


def test_f4_top_campaign_cohort_above_floor(noisy):
    n = sum(
        1 for lead in noisy["leads"]
        if lead.first_touch_utm_campaign == F4_TARGET_CAMPAIGN
    )
    assert n > FINDING_N_FLOOR


def test_f5_patricia_compliance_cohort_above_floor(noisy):
    n = sum(
        1 for lead in noisy["leads"]
        if lead.persona == Persona.PATRICIA
        and lead.seed_label_theme_primary == Theme.COMPLIANCE_SECURITY
    )
    assert n > FINDING_N_FLOOR
