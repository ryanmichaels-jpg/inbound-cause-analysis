# ICA — Gate 1: The Data World

This is the locked-meaning spec for Checkpoint 1. No Python touches the repo until this doc is approved and the Gate 2 aha-pattern spec is approved. After both pass, `seed.py` skews are applied on top of the world defined here.

**What's in scope here:** schema (5 tables) · ICP fit derivation · outcome taxonomy · 4 personas · 6 channels · content asset library · theme taxonomy · ground-truth tagging mechanic · volume & time window.

**What's *not* in scope here (→ Gate 2):** the exact numerical magnitude of each aha-pattern skew. This doc defines the world; Gate 2 specifies the deltas applied to it.

---

## 1. Volume & time window

- **Total leads:** 2,500
- **Time window:** 2026-01-01 → 2026-06-30 (6 months)
- **Created_at distribution:** modest +5% MoM growth trend, weekly seasonality (fewer leads weekends).
- **Outcome `days_to_outcome`:** 14–90 days typical, conditional on outcome type. closed_won is slowest; ghosted is fastest.

CLI knob: `--total-leads` (default 2500), `--seed` (default 42), `--start-date`, `--end-date`.

---

## 2. Schema

Five tables. No reference tables yet — enum-like values (persona, channel, theme) are stored as strings; their canonical lists live in code for CP1 and may be promoted to tables in CP2 if joins demand it.

### 2.1 `leads`

| Column | Type | Notes |
|---|---|---|
| `lead_id` | TEXT PK | UUID v4, deterministic from seed |
| `created_at` | TIMESTAMP | within 6-month window |
| `person_first_name` | TEXT | Faker-generated |
| `person_last_name` | TEXT | Faker-generated |
| `person_email` | TEXT | derived: first.last@company_domain |
| `person_title` | TEXT | persona-conditional (e.g., "Director of RevOps") |
| `person_seniority` | TEXT | enum: `IC`, `Manager`, `Sr Manager`, `Director`, `VP`, `C-level` |
| `company_name` | TEXT | Faker company name |
| `company_domain` | TEXT | derived from company_name |
| `company_industry` | TEXT | enum: `SaaS`, `Fintech`, `Martech`, `E-commerce`, `Healthcare`, `Manufacturing`, `Consumer`, `Other` |
| `company_employee_count` | INTEGER | log-normal distribution, persona-conditional |
| `company_revenue_band` | TEXT | enum: `<$5M`, `$5-20M`, `$20-100M`, `$100-500M`, `$500M+` |
| `persona` | TEXT | one of the 4 personas (literal strings, see §6) |
| `icp_fit_score` | INTEGER | 0–100, computed via §3 formula |
| `created_via_channel` | TEXT | first-touch channel; denormalized convenience |
| `seed_label_theme_primary` | TEXT | the theme this lead's journey was generated to express |
| `seed_label_theme_secondary` | TEXT NULL | optional secondary theme (~30% of leads) |

### 2.2 `touchpoints`

| Column | Type | Notes |
|---|---|---|
| `touchpoint_id` | TEXT PK | UUID v4 |
| `lead_id` | TEXT FK | → `leads.lead_id` |
| `ts` | TIMESTAMP | ordered, monotonic per lead |
| `channel` | TEXT | one of 6 channels (literal strings, see §7) |
| `event_type` | TEXT | enum: `page_view`, `content_download`, `form_view`, `form_submit`, `demo_request`, `demo_attended`, `email_open`, `email_click`, `podcast_listen`, `webinar_register`, `webinar_attended` |
| `content_asset_slug` | TEXT NULL | → content library (§8) |
| `utm_source` | TEXT NULL | |
| `utm_medium` | TEXT NULL | |
| `utm_campaign` | TEXT NULL | |
| `utm_content` | TEXT NULL | |
| `referrer_url` | TEXT NULL | |
| `is_first_touch` | BOOLEAN | exactly one TRUE per lead |
| `is_last_touch` | BOOLEAN | exactly one TRUE per lead |

### 2.3 `form_submissions`

| Column | Type | Notes |
|---|---|---|
| `submission_id` | TEXT PK | UUID v4 |
| `lead_id` | TEXT FK | → `leads.lead_id` |
| `touchpoint_id` | TEXT FK | → `touchpoints.touchpoint_id` (the `form_submit` event) |
| `ts` | TIMESTAMP | matches touchpoint.ts |
| `form_type` | TEXT | enum: `demo_request`, `newsletter_signup`, `content_download`, `contact_sales`, `comparison_page_cta`, `webinar_register` |
| `free_text_question` | TEXT | the prompt shown (form-type-specific) |
| `free_text_answer` | TEXT | `copy_bank.py` output, keyed by `(persona, channel, theme)` |
| `ground_truth_themes` | JSON | array of theme strings, primary first, optional secondary |

### 2.4 `sales_notes`

| Column | Type | Notes |
|---|---|---|
| `note_id` | TEXT PK | UUID v4 |
| `lead_id` | TEXT FK | → `leads.lead_id` |
| `ts` | TIMESTAMP | post-form-submit, pre-outcome |
| `kind` | TEXT | enum: `rep_note`, `call_transcript_snippet` |
| `author` | TEXT | enum: `sdr`, `ae`, `sales_engineer` |
| `text` | TEXT | `copy_bank.py` output |
| `ground_truth_themes` | JSON | array of theme strings |

Not every lead has sales_notes. Generally only leads that reached SQL/Opp (closed_won, closed_lost, disqualified-after-call, some ghosted-after-call) carry notes. Pure nurture and pure form-only ghosts may have zero notes.

### 2.5 `outcomes`

| Column | Type | Notes |
|---|---|---|
| `lead_id` | TEXT PK FK | one outcome per lead |
| `outcome` | TEXT | enum: `closed_won`, `closed_lost`, `disqualified`, `ghosted`, `nurture` |
| `sub_reason` | TEXT NULL | see §5 |
| `pipeline_value_usd` | INTEGER NULL | non-null for `closed_won` and `closed_lost` |
| `resolved_at` | TIMESTAMP | when the outcome was reached (lead "closed" in whatever terminal sense applies to its outcome category) |
| `days_to_outcome` | INTEGER | derived: days from `leads.created_at` to `resolved_at`. Convenience denormalization so velocity queries don't always need a date diff. |

**Note on intermediate stage transitions:** The current four findings can be answered from `leads.created_at` + `outcomes.resolved_at` + the touchpoint stream. Stage-by-stage timestamps (MQL/SQL/Opp) are not in the CP1 schema. If a downstream finding ever requires them, they can be added either as additional columns on `outcomes` or as a separate `stage_transitions` table; for now we mark stage progression implicitly through touchpoint `event_type` values (e.g., `demo_attended` ≈ SQL).

### 2.6 FK diagram

```
leads (lead_id) ──┬──< touchpoints (lead_id)
                  │         ▲
                  │         │ touchpoint_id
                  ├──< form_submissions (lead_id, touchpoint_id ──┘)
                  ├──< sales_notes (lead_id)
                  └──── outcomes (lead_id, 1:1)
```

---

## 3. ICP fit derivation

`leads.icp_fit_score` is computed deterministically at generation from observable lead/company attributes plus a small noise term. The same formula is re-implemented in CP2's structuring step as a sanity check.

```
base = 50

# Company size match (target: 150-500 employees, growth-stage SaaS)
if 150 <= employee_count <= 500:    score += 20
elif 50 <= employee_count < 150:    score += 5
elif 500 < employee_count <= 1500:  score += 0
elif employee_count < 50:           score -= 15
elif employee_count > 1500:         score -= 10

# Industry fit
if industry in {'SaaS', 'Fintech', 'Martech'}:        score += 10
elif industry in {'E-commerce', 'Healthcare'}:        score += 0
else:                                                 score -= 10  # Manufacturing/Consumer/Other

# Seniority fit (target buyer: Director / VP)
if seniority in {'Director', 'VP'}:  score += 10
elif seniority == 'Sr Manager':       score += 5
elif seniority == 'C-level':          score -= 5
elif seniority == 'IC':               score -= 10

# Persona adjustment (encodes "this persona archetype is our buyer")
persona_bonus = {
  'Mid-market RevOps Leader': +10,
  'VP Sales at growth-stage SaaS': +8,
  'Enterprise IT Buyer': -5,
  'SMB Founder': -10,
}[persona]
score += persona_bonus

# Noise
score += int(rng.normal(0, 3))

# Clamp
score = max(0, min(100, score))
```

Fit class derived from score:

| Class | Range |
|---|---|
| Strong | 70–100 |
| Medium | 40–69 |
| Weak | 0–39 |

---

## 4. Theme taxonomy

Nine themes. Each is a slug used in `ground_truth_themes` arrays and in copy-bank keying.

| Theme slug | Description |
|---|---|
| `manual_work_reduction` | Reducing time spent on repetitive *process steps* that don't require data fixes (list-building, status updates, handoffs, copy-paste between systems). **The pain is *the work*.** |
| `data_quality` | Improving the *correctness and completeness* of stored records (dedup, blank fields, stale contacts, enrichment of missing attributes). **The pain is *the data*.** |
| `tool_sprawl_consolidation` | Reducing tool count; integrating disparate systems |
| `pipeline_attribution` | Knowing which channels/campaigns actually drive pipeline |
| `forecasting_accuracy` | More reliable revenue forecasts |
| `rep_efficiency` | Making AEs/SDRs more productive in their selling motion (call quality, talk tracks, follow-up cadence) |
| `cross_team_alignment` | Sales ↔ marketing/ops alignment |
| `onboarding_ramp` | Reducing new-hire ramp time |
| `compliance_security` | SOC2, SSO, data residency, GDPR / security review; vendor procurement requirements. **Primary Patricia theme.** |

**Disambiguation rule (manual_work_reduction vs data_quality):**
These are the closest pair and the most likely to be confused by the LLM in CP4. Copy-bank vocabulary is intentionally distinct:

- `manual_work_reduction` snippets use: *"burning N hours/week," "copy-paste," "manual list-building," "rep time on admin," "ops backlog," "I do this by hand every Monday"*
- `data_quality` snippets use: *"dupes," "blank fields," "stale contacts," "bad data," "enrichment gaps," "the CRM is a mess"*

When a snippet legitimately spans both (e.g., "we spend hours every week fixing dupes"), the **primary** tag is the *goal* (`data_quality` — what they want to fix), and the **secondary** is the *symptom* (`manual_work_reduction` — the time-cost of the problem). This rule is encoded in `copy_bank.py` and reproduced in the CP4 LLM extraction prompt so the taxonomy is unambiguous on both sides.

**Ground-truth tagging mechanic:**
- Every `form_submissions.free_text_answer` and `sales_notes.text` row carries a `ground_truth_themes` JSON array.
- Primary theme = the slug the copy-bank entry was keyed by.
- Secondary theme is set ~30% of rows where the snippet legitimately bridges two themes (e.g., a comment connecting `manual_work_reduction` to `rep_efficiency`).
- These are **generation-time labels**, not human-validated gold standard. README will state this explicitly.
- Purpose: enables an LLM-recall eval in CP4 (precision/recall against seeded labels), as a stronger companion to the theme-stability check.

---

## 5. Outcome taxonomy

Baseline mix, dataset-wide, before aha-pattern skews:

| Outcome | Baseline share | Pipeline value | Has sub-reason |
|---|---|---|---|
| `closed_won` | 6% | > 0 (log-normal, $40k–$200k) | optional |
| `closed_lost` | 10% | > 0 (opp value, $30k–$150k) | yes |
| `disqualified` | 25% | 0 | yes |
| `ghosted` | 24% | 0 | no |
| `nurture` | 35% | 0 | yes |

Sub-reason values:

- **`closed_lost`:** `price`, `competitor_chosen`, `timing`, `no_decision`, `wrong_fit_late`
- **`disqualified`:** `no_budget`, `no_authority`, `out_of_icp_segment`, `wrong_industry`, `company_too_small`, `student_or_competitor`
- **`nurture`:** `too_early`, `waiting_on_budget`, `evaluating_in_6mo`, `champion_changed_role`

**Ghosted distribution skew** (per-persona, share of that persona's non-won outcomes that resolve as ghosted):

| Persona | Ghost share of non-wins |
|---|---|
| Maya (Mid-market RevOps Leader) | 12% |
| David (VP Sales) | 18% |
| Patricia (Enterprise IT Buyer) | 30% |
| Carlos (SMB Founder) | 38% |

Strong-fit personas that don't close are more likely to be `closed_lost` or `nurture` — they engaged, didn't buy. Weak-fit personas ghost.

---

## 6. Personas

Four personas. Population shares sum to 100%.

### 6.1 Maya Chen — Director of RevOps

- **Role:** Director of Revenue Operations
- **Company archetype:** 200–400 person B2B SaaS, $30–80M ARR, ops team of 3–6
- **ICP fit class:** **Strong** (avg score ~75)
- **Channel propensity (ranked):** podcast > organic_search > comparison_page > newsletter > webinar > linkedin_paid
- **Theme propensity (ranked):** **manual_work_reduction** *(signature — Finding 2 cell)* > pipeline_attribution > data_quality > tool_sprawl_consolidation > forecasting_accuracy
- **Language tics:** specific, metric-driven ("we're burning ~12 hours/week on manual list-building"); references current stack by name; talks about reps and AEs by role
- **Outcome lean:** highest closed_won rate; rarely ghosts; if doesn't buy, goes to closed_lost or nurture
- **Population share:** **28%**

### 6.2 David Park — VP of Sales

- **Role:** VP Sales / Head of Sales
- **Company archetype:** 150–500 person growth-stage SaaS
- **ICP fit class:** **Strong** (avg score ~72)
- **Channel propensity (ranked):** linkedin_paid > webinar > podcast > organic_search > newsletter > comparison_page
- **Theme propensity (ranked):** **rep_efficiency** > forecasting_accuracy > pipeline_attribution > manual_work_reduction > cross_team_alignment
- **Language tics:** number-driven, urgency-tinged ("we need to hit Q3 number"); talks about reps and quotas; less in the weeds than Maya
- **Outcome lean:** strong closed_won, but with more closed_lost than Maya (price-sensitive at the VP level)
- **Population share:** **22%**

### 6.3 Patricia Holloway — Enterprise IT Buyer

- **Role:** Director / VP of IT or IT Procurement
- **Company archetype:** 2000+ person enterprise across various industries
- **ICP fit class:** **Medium-Weak** (avg score ~38)
- **Channel propensity (ranked):** linkedin_paid > comparison_page > organic_search > webinar > newsletter > podcast
- **Theme propensity (ranked):** **compliance_security** *(signature)* > tool_sprawl_consolidation > data_quality > cross_team_alignment > forecasting_accuracy
- **Language tics:** procurement-flavored ("vendor evaluation," "security review," "SSO requirements," "SOC2 report," "DPA"); slow; cautious
- **Outcome lean:** disqualifies often (wrong segment), ghosts moderately, occasionally closed_won with high pipeline value
- **Population share:** **26%**

### 6.4 Carlos Reyes — SMB Founder

- **Role:** Founder / Solo operator
- **Company archetype:** <30 person seed-stage startup
- **ICP fit class:** **Weak** (avg score ~25)
- **Channel propensity (ranked):** linkedin_paid > organic_search > newsletter > podcast > webinar > comparison_page
- **Theme propensity (ranked):** **onboarding_ramp** > rep_efficiency > manual_work_reduction > pipeline_attribution > data_quality
- **Language tics:** scrappy ("just trying to figure out our first reps"); hopeful; thin context
- **Outcome lean:** highest ghost rate; most common disqualify; closed_won is rare and low-value
- **Population share:** **24%**

---

## 7. Channels

Six channels, all clearly inbound. Total = 2,500 leads.

| Channel | Target leads | Baseline CW rate | Persona affinity (strongest → weakest) | Role |
|---|---|---|---|---|
| `podcast` | 200 | ~30% (engineered) | [Maya, David, Carlos, Patricia] | Low-volume, high-quality. **Finding 1 winner.** Also vehicle for **Finding 3** journey. |
| `linkedin_paid` | 1,000 | ~3% (engineered) | [Carlos, Patricia, David, Maya] | High-volume, low-quality. **Findings 1 + 4 loser.** |
| `organic_search` | 400 | ~8% | [Maya, David, Patricia, Carlos] | Medium baseline |
| `newsletter` | 300 | ~7% | [Maya, David, Carlos, Patricia] | Customer/community email newsletter |
| `webinar` | 300 | ~6% | [David, Maya, Patricia, Carlos] | Medium baseline |
| `comparison_page` | 300 | ~10% | [Maya, David, Patricia, Carlos] | **Replaced cold outbound.** Mid-funnel, high-intent (G2/comparison content) |

**How affinity rankings are consumed by the generator:** for each lead, the generator samples a persona first (per population shares in §6), then samples a channel conditioned on that persona's *inverse* channel-affinity (the persona's ranked channel preferences in §6). The constraint solver targets both per-channel volume (this table's "Target leads" column) and per-persona population share simultaneously. Affinity rankings are qualitative weights; exact within-channel persona proportions emerge from the joint distribution.

**Within-channel campaign mix — `linkedin_paid`:**

| Campaign (= `utm_campaign`) | Leads | Persona mix (within campaign) |
|---|---|---|
| `linkedin_q2_broad_funnel` | 600 | Carlos 40%, Patricia 35%, David 15%, Maya 10% — **deliberately more non-ICP than channel baseline** |
| `linkedin_q2_enterprise` | 250 | Patricia 60%, David 15%, Maya 15%, Carlos 10% |
| `linkedin_q2_revops_targeted` | 150 | Maya 55%, David 25%, Carlos 12%, Patricia 8% |

The broad-funnel campaign is engineered to skew more non-ICP than the linkedin_paid channel as a whole. This is where Finding 4's tension lives — the highest-volume single campaign produces predominantly wrong-fit leads despite costing the most. The exact non-ICP outcome percentage in this campaign is committed in Gate 2.

UTM mapping per channel:

| Channel | utm_source | utm_medium |
|---|---|---|
| `podcast` | `<podcast_name>` (per-episode) | `audio` |
| `linkedin_paid` | `linkedin` | `cpc` |
| `organic_search` | `google` | `organic` |
| `newsletter` | `newsletter` | `email` |
| `webinar` | `webinar` | `event` |
| `comparison_page` | `g2` / `capterra` / `direct` | `referral` / `organic` |

`utm_campaign` is per content asset (see §8). The **Finding 4 vehicle** is `linkedin_q2_broad_funnel` — the highest-volume single campaign.

---

## 8. Content asset library

16 named assets across 6 channels.

### Podcast episodes — channel = `podcast`

| slug | title | theme | target persona |
|---|---|---|---|
| `ops-podcast-ep-42` | Cutting Manual Work in RevOps | `manual_work_reduction` | Maya |
| `saas-growth-pod-17` | Forecasting in Growth-Stage SaaS | `forecasting_accuracy` | David |
| `go-to-market-show-09` | Pipeline Attribution in 2026 | `pipeline_attribution` | Maya |

### Blog posts — channel = `organic_search`

| slug | title | theme | target persona |
|---|---|---|---|
| `blog-revops-manual-toil` | The RevOps Manual Toil Audit | `manual_work_reduction` | Maya |
| `blog-tool-sprawl-2026` | The 2026 GTM Tool Sprawl Problem | `tool_sprawl_consolidation` | Patricia |
| `blog-attribution-honest` | Honest Attribution: What B2B Marketers Get Wrong | `pipeline_attribution` | Maya, David |
| `blog-forecast-models` | Forecast Models That Don't Lie | `forecasting_accuracy` | David |
| `blog-crm-cleanup` | The Quarterly CRM Cleanup Playbook | `data_quality` | Maya |
| `blog-compliance-vendor-checklist` | The Enterprise GTM Vendor Compliance Checklist | `compliance_security` | Patricia |

### LinkedIn ad campaigns — channel = `linkedin_paid`

| slug (= `utm_campaign`) | theme | target persona | leads |
|---|---|---|---|
| `linkedin_q2_broad_funnel` | (generic / mixed) | broad — Carlos & Patricia heavy | **600 ← Finding 4 vehicle** |
| `linkedin_q2_enterprise` | `tool_sprawl_consolidation` | Patricia | 250 |
| `linkedin_q2_revops_targeted` | `manual_work_reduction` | Maya | 150 |

### Webinars — channel = `webinar`

| slug | title | theme | target persona |
|---|---|---|---|
| `webinar-attribution-deepdive` | Attribution Deep-Dive | `pipeline_attribution` | Maya, David |
| `webinar-rep-efficiency-panel` | Rep Efficiency Panel | `rep_efficiency` | David |

### Newsletter editions — channel = `newsletter`

- Programmatically generated: `newsletter-2026-01` … `newsletter-2026-06`. Each issue features one rotating theme.

### Comparison page — channel = `comparison_page`

| slug | theme | target persona |
|---|---|---|
| `comparison-vs-competitor-x` | (mixed, mostly `tool_sprawl_consolidation` + `pipeline_attribution`) | Maya, David |

---

## 9. Finding 2 — the named resonance cell

Per your directive, the resonance-differential target is committed in this doc, not discovered later:

```
PERSONA = 'Mid-market RevOps Leader'   (Maya)
THEME   = 'manual_work_reduction'
```

Maya × `manual_work_reduction` will have ~3x the closed_won rate of `manual_work_reduction` on any other persona. Gate 2's Finding 2 assertion will reference these literal strings, not a quantifier.

---

## 10. What's still TBD → Gate 2

The exact numerical magnitude of each aha-pattern skew:

| Finding | Gate 2 spec |
|---|---|
| 1 — Channel quality surprise | Exact podcast CW rate vs linkedin_paid CW rate; rate ratio target |
| 2 — Resonance differential | Baseline vs lifted CW rate inside the Maya × `manual_work_reduction` cell |
| 3 — Multi-touch journey | How many of the 200 podcast leads take the `podcast → blog → demo` path; rate lift on that path |
| 4 — ICP fit vs volume mismatch | Exact non-ICP % inside `linkedin_q2_broad_funnel`; mean ICP fit score in that bucket |

Plus the smoke-test assertion text (verbatim) for each.

**Optional Gate 2 add — Patricia × `compliance_security` secondary cell:** the `compliance_security` theme is defined in §4 and Patricia carries it as her signature in §6, but the cell is *not* artificially lifted by default. Engineering a modest secondary resonance differential here (e.g., ~2x lift, less than Maya's signature 3x) would give the CP5 dashboard a second pattern to render and makes Patricia legible beyond demographic role. **Default: not engineered.** Decide in Gate 2 — opt in adds a fifth assertion to the smoke-test suite; opt out keeps the four-finding contract clean.
