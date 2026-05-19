"""Per-persona sampling: name, title, company attributes.

See `docs/data-world.md` § 6 and `src/ica/taxonomy.py` § 7 (persona
company-archetype attributes) for the canonical values this module
samples against.

TODO (read before implementing — sanity check the plan):

Population shares (taxonomy.PERSONA_POPULATION_SHARE, must sum to 1.0):
    Maya     0.28   Mid-market RevOps Leader    strong fit
    David    0.22   VP Sales                    strong fit
    Patricia 0.26   Enterprise IT Buyer         medium-weak
    Carlos   0.24   SMB Founder                 weak

Sampling approach: stratified sampling, NOT independent Bernoulli per
lead. For TOTAL_LEADS_DEFAULT=2500 we draw exactly round(2500 * share)
of each persona so the counts are deterministic per seed and the
downstream cell-size assertions (Finding 2 cell ~280 leads, Finding 5
cell ~260 leads) hit their margins without RNG drift. Rounding error
goes into the largest bucket (Maya).

Per-persona attributes sampled from taxonomy:
- company_employee_count: integer in PERSONA_COMPANY_SIZE_RANGE[p],
  drawn from a log-normal-ish distribution clipped to the range.
- company_industry: categorical from PERSONA_INDUSTRY_WEIGHTS[p].
- person_seniority: categorical from PERSONA_SENIORITY_WEIGHTS[p].
- company_revenue_band: derived from employee_count via
  schema.revenue_band_for_employee_count().
- person_first/last_name + company_name: Faker-generated, seeded.
- person_email: derived from name + a slugified company_domain.
- icp_fit_score: schema.compute_icp_fit_score(persona, industry,
  employee_count, seniority, rng).

Non-obvious rules to flag for review:
1. Faker is seeded once globally per generation run (Faker.seed(seed)).
   This is separate from numpy's rng. Faker doesn't accept a numpy
   Generator; we keep the two RNGs in lock-step by passing the same
   integer seed.
2. company_domain is slugified from company_name (lowercased, spaces
   to hyphens, ", inc/llc" stripped). person_email is first.last @
   company_domain. Realistic enough; no email collisions matter in v1.
3. created_via_channel and seed_label_theme_primary/_secondary are NOT
   assigned in this module — they're set later in channels.py and
   journeys.py. This module produces personas + companies + identities
   only.

Output of this module: list of partial-Lead records ready for the
channel/journey layers to enrich with first-touch channel and theme.
"""
