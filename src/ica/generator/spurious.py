"""spurious.py — v1.5 planted false-correlation injection.

Three patterns engineered as "tempting wrong findings": small N + extreme
rate + a slice a real GTM team would casually look at. Each pattern has
a `correlation_shape` (the naive aggregation that surfaces it) so the
§6.2(c) discrimination test in Commit 3 can confirm it is genuinely
findable before asserting the pipeline rejects it on the N-floor.

Per §4 of the v1.5 Phase 1 planning header (see noise.py docstring).
inject_spurious_patterns() runs as the LAST step of apply_noise() so
S3's keyword injection survives any earlier text_noise application.

Plant mechanics differ per pattern:
  - S1 (Tuesday) — natural attribute (lead.created_at.weekday()=1) +
    outcome flip. The Tuesday cohort exists naturally; no attribute
    overwrite.
  - S2 (.ai TLD) — manufactured attribute (overwrite company_domain +
    person_email TLD to `.ai`) + outcome flip. Faker doesn't naturally
    produce .ai domains at the rate we need.
  - S3 ('urgent' keyword) — manufactured attribute (append a sentence
    to form_text) + outcome flip. The keyword doesn't appear naturally
    at the rate we need.

Candidates for all three are filtered to mid-band ICP-fit (50-70) so
firmographics don't covary with the planted dimension — the only
differentiator between planted leads and the rest is the spurious
attribute itself.

Outcome flip semantics: outcome -> CLOSED_WON, sub_reason -> None,
pipeline_value_usd -> 50_000 (a plausible mid-deal value).

Returns: a manifest (list of dicts) the discrimination test reads to
know (a) which lead_ids were planted with which pattern and (b) which
naive aggregation should surface each.
"""

from __future__ import annotations

import re

import numpy as np

from ica.schema import FormSubmission, Lead, OutcomeRow
from ica.taxonomy import NoiseProfile, Outcome

__all__ = ["inject_spurious_patterns", "PATTERN_DEFINITIONS"]


# Pattern definitions — DICTATED §4 of the planning header.
PATTERN_DEFINITIONS: tuple[dict, ...] = (
    {
        "id": "S1",
        "description": "Tuesday signups close at 80%",
        "correlation_shape": "marginal close-rate by day-of-week",
        "target_n": 5,
        "target_rate": 0.80,
        "surface_signal": {"kind": "weekday", "value": 1},  # Mon=0, Tue=1
    },
    {
        "id": "S2",
        "description": "Leads from .ai domains close at 75%",
        "correlation_shape": "marginal close-rate by company-domain TLD",
        "target_n": 8,
        "target_rate": 0.75,
        "surface_signal": {"kind": "tld", "value": ".ai"},
    },
    {
        "id": "S3",
        "description": "Leads with 'urgent' in form-text close at 90%",
        "correlation_shape": "marginal close-rate by keyword in form_text",
        "target_n": 10,
        "target_rate": 0.90,
        "surface_signal": {"kind": "keyword", "value": "urgent"},
    },
)

# Sentence appended to a planted form_text for S3. The buyer-language signal
# in the rest of the form_text is preserved — we add, never replace.
_S3_KEYWORD_SENTENCE = "We need this resolved urgently — when can we start?"

# Mid-band ICP-fit window for candidate filtering (§4 confound removal).
_MID_FIT_LO = 50
_MID_FIT_HI = 70

# Planted-outcome target value — mid-deal CLOSED_WON.
_PLANTED_PIPELINE_VALUE_USD = 50_000


def _select_candidates(
    candidates: list[Lead], target_n: int, rng: np.random.Generator
) -> list[Lead]:
    """Random sample of up to `target_n` leads from a candidate pool.

    No explicit per-persona stratification — the candidate pool has
    hundreds of leads across all four personas at mid-band fit, so a
    random sample of 5-10 naturally spreads. The discrimination test
    (Commit 3) does not assert persona-spread; this is a confound-
    reduction property of the planted cohort, not a correctness
    invariant.
    """
    if len(candidates) <= target_n:
        return list(candidates)
    indices = rng.choice(len(candidates), size=target_n, replace=False)
    return [candidates[int(i)] for i in indices]


def _flip_outcome(outcome_row: OutcomeRow) -> None:
    """Mutate outcome_row -> CLOSED_WON with a planted pipeline value."""
    outcome_row.outcome = Outcome.CLOSED_WON
    outcome_row.sub_reason = None
    outcome_row.pipeline_value_usd = _PLANTED_PIPELINE_VALUE_USD


def _plant_s1_tuesday(
    leads: list[Lead],
    outcome_by_lead: dict[str, OutcomeRow],
    rng: np.random.Generator,
) -> list[str]:
    """S1: Tuesday signups close at 80%. Select from leads with
    created_at.weekday()==1 and mid-band fit; flip outcomes."""
    candidates = [
        lead for lead in leads
        if lead.created_at is not None
        and lead.created_at.weekday() == 1
        and _MID_FIT_LO <= lead.icp_fit_score <= _MID_FIT_HI
        and lead.lead_id in outcome_by_lead
        and outcome_by_lead[lead.lead_id].outcome != Outcome.CLOSED_WON
    ]
    selected = _select_candidates(candidates, target_n=5, rng=rng)
    for lead in selected:
        _flip_outcome(outcome_by_lead[lead.lead_id])
    return [lead.lead_id for lead in selected]


def _plant_s2_ai_tld(
    leads: list[Lead],
    outcome_by_lead: dict[str, OutcomeRow],
    rng: np.random.Generator,
) -> list[str]:
    """S2: .ai-domain leads close at 75%. Select mid-band-fit leads (any
    persona); overwrite company_domain + person_email TLD to `.ai`;
    flip outcomes."""
    # Exclude leads already on .ai domains (rare but possible via Faker).
    candidates = [
        lead for lead in leads
        if _MID_FIT_LO <= lead.icp_fit_score <= _MID_FIT_HI
        and not lead.company_domain.endswith(".ai")
        and lead.lead_id in outcome_by_lead
        and outcome_by_lead[lead.lead_id].outcome != Outcome.CLOSED_WON
    ]
    selected = _select_candidates(candidates, target_n=8, rng=rng)
    for lead in selected:
        # Replace whatever TLD the domain has with `.ai`. Slug part stays.
        base = re.sub(r"\.[a-z]+$", "", lead.company_domain)
        lead.company_domain = f"{base}.ai"
        # Re-derive email to keep email domain consistent with company domain.
        local = lead.person_email.split("@", 1)[0]
        lead.person_email = f"{local}@{lead.company_domain}"
        _flip_outcome(outcome_by_lead[lead.lead_id])
    return [lead.lead_id for lead in selected]


def _plant_s3_urgent_keyword(
    leads: list[Lead],
    form_submissions: list[FormSubmission],
    outcome_by_lead: dict[str, OutcomeRow],
    rng: np.random.Generator,
) -> list[str]:
    """S3: 'urgent' keyword in form-text -> 90% close. Select mid-band-fit
    leads with at least one form_submission; append the urgent-keyword
    sentence to one of their form_submissions; flip outcomes."""
    # Map lead -> first form_submission (we mutate only one per lead).
    fs_by_lead: dict[str, FormSubmission] = {}
    for fs in form_submissions:
        fs_by_lead.setdefault(fs.lead_id, fs)

    candidates = [
        lead for lead in leads
        if _MID_FIT_LO <= lead.icp_fit_score <= _MID_FIT_HI
        and lead.lead_id in fs_by_lead
        and lead.lead_id in outcome_by_lead
        and outcome_by_lead[lead.lead_id].outcome != Outcome.CLOSED_WON
        # Don't double-plant on leads that already organically contain
        # 'urgent' — keeps the keyword cohort exactly the planted set.
        and "urgent" not in (fs_by_lead[lead.lead_id].free_text_answer or "").lower()
    ]
    selected = _select_candidates(candidates, target_n=10, rng=rng)
    for lead in selected:
        fs = fs_by_lead[lead.lead_id]
        existing = fs.free_text_answer or ""
        sep = " " if existing and not existing.endswith((" ", ".", "!", "?")) else ""
        fs.free_text_answer = f"{existing}{sep}{_S3_KEYWORD_SENTENCE}"
        _flip_outcome(outcome_by_lead[lead.lead_id])
    return [lead.lead_id for lead in selected]


def inject_spurious_patterns(
    leads: list[Lead],
    form_submissions: list[FormSubmission],
    outcomes: list[OutcomeRow],
    *,
    profile: NoiseProfile,
    rng: np.random.Generator,
) -> list[dict]:
    """Plant the three spurious patterns. Mutates leads / form_submissions
    / outcomes in place. Returns a manifest list — one entry per planted
    pattern, with planted_lead_ids and the surface_signal needed by the
    discrimination test (§6.2c).

    `profile.spurious_count` gates the number of patterns to plant: 0
    skips entirely; >= 3 plants all three (S1, S2, S3 — no plant exceeds
    PATTERN_DEFINITIONS). Phase 1 default is 3.
    """
    if profile.spurious_count <= 0:
        return []

    outcome_by_lead: dict[str, OutcomeRow] = {o.lead_id: o for o in outcomes}
    manifest: list[dict] = []

    # Plant in fixed S1 -> S2 -> S3 order so reruns produce identical
    # manifests; the RNG sub-stream is the one source of variation.
    planters = (
        ("S1", lambda r: _plant_s1_tuesday(leads, outcome_by_lead, r)),
        ("S2", lambda r: _plant_s2_ai_tld(leads, outcome_by_lead, r)),
        ("S3", lambda r: _plant_s3_urgent_keyword(leads, form_submissions, outcome_by_lead, r)),
    )
    plant_count = min(profile.spurious_count, len(planters))
    for i in range(plant_count):
        pattern_id, planter = planters[i]
        defn = PATTERN_DEFINITIONS[i]
        assert defn["id"] == pattern_id  # sanity: definitions align with planters
        planted_lead_ids = planter(rng)
        manifest.append({
            "id": pattern_id,
            "description": defn["description"],
            "correlation_shape": defn["correlation_shape"],
            "target_n": defn["target_n"],
            "target_rate": defn["target_rate"],
            "surface_signal": defn["surface_signal"],
            "planted_lead_ids": planted_lead_ids,
        })

    return manifest
