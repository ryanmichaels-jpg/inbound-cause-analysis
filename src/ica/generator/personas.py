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
