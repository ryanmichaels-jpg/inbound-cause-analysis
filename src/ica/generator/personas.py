"""Per-persona sampling: identity, title, company attributes.

See `docs/data-world.md` §6 and `src/ica/taxonomy.py` §7 (persona
company-archetype attributes) for the canonical values this module
samples against.

TODO (read before implementing — sanity check the plan):

Population shares (taxonomy.PERSONA_POPULATION_SHARE, sum to 1.0):
    Maya     0.28   Mid-market RevOps Leader    strong fit
    David    0.22   VP Sales                    strong fit
    Patricia 0.26   Enterprise IT Buyer         medium-weak
    Carlos   0.24   SMB Founder                 weak

Sampling approach: stratified sampling, NOT independent Bernoulli per
lead. For TOTAL_LEADS_DEFAULT=2500 we draw exactly round(2500 * share)
of each persona — Maya 700 / David 550 / Patricia 650 / Carlos 600 — so
counts are deterministic per seed and the downstream cell-size assertions
(Finding 2 cell ~280, Finding 5 cell ~260) hit their margins without RNG
drift. At the default 2500 the shares divide evenly with no remainder;
for other --total-leads values any rounding remainder goes to the largest
bucket (Maya).

Output type: list[PartialLead]. PartialLead is defined in schema.py next
to Lead — the pipeline data contract belongs in the data-contract layer,
not the generator. It carries every field this module populates as
required, and leaves the channel/journey-assigned fields as Optional,
defaulting None. schema.PartialLead.to_lead() is the finalizer: it
asserts the deferred fields have been filled and returns a Lead. Typed
PartialLead is used deliberately over a dict (loses type introspection
across five enrichment stages) and over a Lead with sentinel values (a
forgotten overwrite would silently persist a placeholder into a NOT NULL
column instead of failing loudly at to_lead()).

Fields assigned in THIS module:
- lead_id: deterministic UUID (UUIDv5 over a fixed namespace + the run
  seed + the lead's stratified index). Identity is generated first;
  deterministic so the dataset is reproducible across runs.
- person_first_name / person_last_name / company_name: Faker-generated.
- company_domain: slugified from company_name (lowercased, spaces to
  hyphens, trailing ", inc/llc" stripped).
- person_email: derived — first.last @ company_domain.
- person_seniority: categorical from PERSONA_SENIORITY_WEIGHTS[p].
- person_title: sampled from taxonomy.PERSONA_TITLES[p].
- company_employee_count: integer in PERSONA_COMPANY_SIZE_RANGE[p],
  drawn from a log-normal-ish distribution clipped to the range.
- company_industry: categorical from PERSONA_INDUSTRY_WEIGHTS[p].
- company_revenue_band: derived from employee_count via
  schema.revenue_band_for_employee_count().
- icp_fit_score: schema.compute_icp_fit_score(persona, industry,
  employee_count, seniority, rng). Uses the retuned coefficients from
  this gate; persona means land near doc §6 targets (Maya ~75, David
  ~72, Patricia ~39, Carlos ~26) rather than saturating the 100 clamp.

Fields NOT assigned here (left None on PartialLead):
- created_at — first-touch timestamp; a channel-layer concern, set in
  channels.py.
- created_via_channel — set in channels.py.
- seed_label_theme_primary / seed_label_theme_secondary — set in
  journeys.py.

Non-obvious rules to flag for review:
1. Faker is seeded once globally per generation run (Faker.seed(seed)),
   separate from numpy's Generator. Faker doesn't accept a numpy
   Generator; the two RNGs are kept in lock-step by passing the same
   integer seed.
2. person_title and person_seniority are sampled independently from
   their per-persona pools — NOT cross-constrained. A lead can pair
   e.g. seniority='VP' with a Director-flavored title. Accepted for v1
   (both are persona flavor; pools are written so any title reads
   plausibly for that persona). Flagged in case seniority-keyed title
   sub-pools are wanted instead.
3. person_email collisions are not de-duplicated; irrelevant in v1.

Output: list[PartialLead], persona + identity + firmographics populated,
ready for channels.py and journeys.py to enrich.
"""

import re
import uuid
from typing import TypeVar

import numpy as np
from faker import Faker

from ica.schema import (
    PartialLead,
    compute_icp_fit_score,
    revenue_band_for_employee_count,
)
from ica.taxonomy import (
    DEFAULT_SEED,
    PERSONA_COMPANY_SIZE_RANGE,
    PERSONA_INDUSTRY_WEIGHTS,
    PERSONA_POPULATION_SHARE,
    PERSONA_SENIORITY_WEIGHTS,
    PERSONA_TITLES,
    TOTAL_LEADS_DEFAULT,
    Persona,
)

__all__ = ["sample_personas"]

# Fixed namespace so lead_id is reproducible across runs and machines.
_LEAD_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "ica.inbound-cause-analysis")

# Company-name -> domain slug helpers.
_DOMAIN_PUNCT = re.compile(r"[^a-z0-9\s-]")
_DOMAIN_SUFFIX = re.compile(r"\b(inc|llc|ltd|plc|group)\b")
_DOMAIN_SPACES = re.compile(r"\s+")
_DOMAIN_DASHES = re.compile(r"-+")
_EMAIL_PUNCT = re.compile(r"[^a-z0-9]")

_K = TypeVar("_K")


def _persona_counts(total_leads: int) -> dict[Persona, int]:
    """Deterministic per-persona counts; any rounding remainder goes to Maya."""
    counts = {p: round(total_leads * PERSONA_POPULATION_SHARE[p]) for p in Persona}
    counts[Persona.MAYA] += total_leads - sum(counts.values())
    return counts


def _sample_categorical(rng: np.random.Generator, weights: dict[_K, float]) -> _K:
    """Pick one key from a {key: weight} mapping. Weights normalized defensively."""
    keys = list(weights.keys())
    probs = np.array([weights[k] for k in keys], dtype=float)
    probs /= probs.sum()
    return keys[int(rng.choice(len(keys), p=probs))]


def _sample_employee_count(rng: np.random.Generator, lo: int, hi: int) -> int:
    """Log-normal-ish headcount centered on the geometric mean of [lo, hi],
    clipped to the range."""
    log_lo, log_hi = np.log(lo), np.log(hi)
    mu = (log_lo + log_hi) / 2.0
    sigma = (log_hi - log_lo) / 4.0  # range spans ~+/-2 sigma before clipping
    value = int(round(float(np.exp(rng.normal(mu, sigma)))))
    return int(np.clip(value, lo, hi))


def _company_domain(company_name: str) -> str:
    """Slugify a Faker company name into a `<slug>.com` domain."""
    slug = company_name.lower()
    slug = _DOMAIN_PUNCT.sub("", slug)
    slug = _DOMAIN_SUFFIX.sub("", slug)
    slug = _DOMAIN_SPACES.sub("-", slug.strip())
    slug = _DOMAIN_DASHES.sub("-", slug).strip("-")
    return f"{slug or 'company'}.com"


def _person_email(first: str, last: str, domain: str) -> str:
    first_slug = _EMAIL_PUNCT.sub("", first.lower())
    last_slug = _EMAIL_PUNCT.sub("", last.lower())
    return f"{first_slug}.{last_slug}@{domain}"


def _sample_one(
    persona: Persona,
    index: int,
    seed: int,
    rng: np.random.Generator,
    fake: Faker,
) -> PartialLead:
    seniority = _sample_categorical(rng, PERSONA_SENIORITY_WEIGHTS[persona])
    titles = PERSONA_TITLES[persona]
    title = titles[int(rng.integers(len(titles)))]
    industry = _sample_categorical(rng, PERSONA_INDUSTRY_WEIGHTS[persona])
    lo, hi = PERSONA_COMPANY_SIZE_RANGE[persona]
    employee_count = _sample_employee_count(rng, lo, hi)
    revenue_band = revenue_band_for_employee_count(employee_count)

    first_name = fake.first_name()
    last_name = fake.last_name()
    company_name = fake.company()
    domain = _company_domain(company_name)
    email = _person_email(first_name, last_name, domain)

    icp = compute_icp_fit_score(persona, industry, employee_count, seniority, rng)
    lead_id = str(uuid.uuid5(_LEAD_ID_NAMESPACE, f"{seed}:{index}"))

    return PartialLead(
        lead_id=lead_id,
        person_first_name=first_name,
        person_last_name=last_name,
        person_email=email,
        person_title=title,
        person_seniority=seniority,
        company_name=company_name,
        company_domain=domain,
        company_industry=industry,
        company_employee_count=employee_count,
        company_revenue_band=revenue_band,
        persona=persona,
        icp_fit_score=icp,
    )


def sample_personas(
    seed: int = DEFAULT_SEED,
    total_leads: int = TOTAL_LEADS_DEFAULT,
) -> list[PartialLead]:
    """Stratified-sample `total_leads` PartialLead records across the four
    personas, honoring taxonomy.PERSONA_POPULATION_SHARE.

    created_at, created_via_channel, and seed_label_theme_* are left unset
    for channels.py and journeys.py to fill.
    """
    rng = np.random.default_rng(seed)
    Faker.seed(seed)
    fake = Faker()

    counts = _persona_counts(total_leads)
    leads: list[PartialLead] = []
    index = 0
    for persona in Persona:
        for _ in range(counts[persona]):
            leads.append(_sample_one(persona, index, seed, rng, fake))
            index += 1
    return leads
