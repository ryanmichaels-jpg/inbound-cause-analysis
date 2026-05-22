"""personas.py — dedicated unit coverage for the persona generator.

Closes the suite-parity gap: taxonomy, schema, and channels each have a
dedicated test module; personas.py was previously only exercised at sample
level and indirectly through downstream generator tests."""

import numpy as np
import pytest

from ica.generator.personas import (
    _company_domain,
    _person_email,
    _persona_counts,
    _sample_employee_count,
    sample_personas,
)
from ica.schema import revenue_band_for_employee_count
from ica.taxonomy import (
    PERSONA_COMPANY_SIZE_RANGE,
    PERSONA_INDUSTRY_WEIGHTS,
    PERSONA_POPULATION_SHARE,
    PERSONA_SENIORITY_WEIGHTS,
    PERSONA_TITLES,
    TOTAL_LEADS_DEFAULT,
    Persona,
)


@pytest.fixture(scope="module")
def leads():
    return sample_personas()


# --- population shares & counts ----------------------------------------------


def test_total_lead_count(leads):
    assert len(leads) == TOTAL_LEADS_DEFAULT


@pytest.mark.parametrize("persona", list(Persona))
def test_persona_population_share(leads, persona):
    count = sum(1 for lead in leads if lead.persona == persona)
    assert count == round(TOTAL_LEADS_DEFAULT * PERSONA_POPULATION_SHARE[persona])


def test_persona_counts_default_exact():
    assert _persona_counts(TOTAL_LEADS_DEFAULT) == {
        Persona.MAYA: 700,
        Persona.DAVID: 550,
        Persona.PATRICIA: 650,
        Persona.CARLOS: 600,
    }


def test_persona_counts_remainder_goes_to_maya():
    # 2501 does not divide evenly across the shares — the +1 lands on Maya.
    counts = _persona_counts(2501)
    assert sum(counts.values()) == 2501
    assert counts[Persona.MAYA] == 701


# --- field population --------------------------------------------------------


def test_identity_fields_populated(leads):
    for lead in leads:
        assert lead.lead_id
        assert lead.person_first_name and lead.person_last_name
        assert lead.person_email.endswith(f"@{lead.company_domain}")
        assert lead.person_title
        assert lead.company_name and lead.company_domain
        assert lead.persona in set(Persona)


def test_deferred_fields_left_unset(leads):
    # channels.py and journeys.py fill these — personas.py must leave them None.
    for lead in leads:
        assert lead.created_at is None
        assert lead.created_via_channel is None
        assert lead.first_touch_utm_campaign is None
        assert lead.seed_label_theme_primary is None
        assert lead.seed_label_theme_secondary is None


def test_icp_fit_score_within_bounds(leads):
    for lead in leads:
        assert 0 <= lead.icp_fit_score <= 100


def test_lead_ids_unique(leads):
    ids = [lead.lead_id for lead in leads]
    assert len(set(ids)) == len(ids)


# --- per-persona attribute consistency ---------------------------------------


def test_seniority_within_persona_weights(leads):
    for lead in leads:
        assert lead.person_seniority in PERSONA_SENIORITY_WEIGHTS[lead.persona]


def test_title_drawn_from_seniority_subpool(leads):
    # person_title must come from the sub-pool scoped to the lead's seniority —
    # no "VP seniority with a Manager-level title" rows.
    for lead in leads:
        subpool = PERSONA_TITLES[lead.persona][lead.person_seniority]
        assert lead.person_title in subpool


def test_industry_within_persona_weights(leads):
    for lead in leads:
        assert lead.company_industry in PERSONA_INDUSTRY_WEIGHTS[lead.persona]


def test_employee_count_within_persona_range(leads):
    for lead in leads:
        lo, hi = PERSONA_COMPANY_SIZE_RANGE[lead.persona]
        assert lo <= lead.company_employee_count <= hi


def test_revenue_band_matches_employee_count(leads):
    for lead in leads:
        assert lead.company_revenue_band == revenue_band_for_employee_count(
            lead.company_employee_count
        )


# --- derived-field helpers ---------------------------------------------------


def test_person_email_derivation():
    assert _person_email("Ada", "Lovelace", "acme.com") == "ada.lovelace@acme.com"
    # punctuation in names is stripped before the local part is built
    assert _person_email("O'Brien", "Smith-Jones", "x.io") == "obrien.smithjones@x.io"


def test_company_domain_slug():
    assert _company_domain("Hooli Inc") == "hooli.com"
    assert _company_domain("Foo Bar, LLC") == "foo-bar.com"
    domain = _company_domain("Globex Worldwide Corporation")
    assert domain.endswith(".com")
    assert " " not in domain
    assert domain == domain.lower()


def test_sample_employee_count_clips_to_range():
    rng = np.random.default_rng(0)
    for _ in range(300):
        assert 150 <= _sample_employee_count(rng, 150, 500) <= 500


# --- determinism -------------------------------------------------------------


def test_sampling_is_deterministic():
    run_a = sample_personas()
    run_b = sample_personas()
    assert run_a == run_b


def test_distinct_seeds_produce_distinct_leads():
    seed_1 = sample_personas(seed=1)
    seed_2 = sample_personas(seed=2)
    assert [lead.lead_id for lead in seed_1] != [lead.lead_id for lead in seed_2]
