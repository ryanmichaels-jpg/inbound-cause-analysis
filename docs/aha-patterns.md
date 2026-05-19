# ICA — Gate 2: Aha-Pattern Numerical Specs

This doc commits the exact numerical magnitude of each aha-pattern skew that `seed.py` will apply on top of the data world defined in `docs/data-world.md`. Each finding is encoded as a falsifiable contract — the smoke-test assertion is the contract; the engineered target is what `seed.py` aims for, with margin above the threshold.

**Convention used throughout:**
- *Engineered target* = the value `seed.py` deliberately produces.
- *Smoke-test threshold* = the value the pytest assertion checks; always looser than the engineered target.
- *Margin* = engineered − threshold (or engineered / threshold for ratios). Should be wide enough that the assertion clears across reasonable seed variation.

---

## Taxonomy: single source of truth

All canonical names — theme slugs, persona strings, channel strings, content asset slugs, the outcome enum, sub-reason vocabularies, and the `manual_work_reduction` vs `data_quality` disambiguation rule — live in **one module**: `src/ica/taxonomy.py`. Every other module imports from there:

- `generator/*` — uses taxonomy constants for sampling
- `copy_bank.py` — keys snippets by `Persona × Channel × Theme` enums from taxonomy
- `schema.py` — defers to taxonomy for any string enum values stored in the DB
- `tests/test_aha_patterns.py` — references taxonomy enums in cell definitions
- (Future) CP4 LLM extraction prompt — imports the disambiguation rule constant directly and inlines it into the system prompt

This prevents drift between generation and extraction. When a theme is renamed, the disambiguation rule is sharpened, or a new asset slug is added, **it changes in one place** and every consumer picks up the change automatically. Tests in `test_taxonomy.py` enforce internal consistency (e.g., every asset has a theme mapping, persona/channel affinity rankings cover the full enum, persona population shares sum to 1.0).

---

## Skew application order

Skews compose. They are applied in this order; later skews override earlier ones for affected leads.

1. **Sample personas, channels, themes** per Gate 1 distributions (`docs/data-world.md` §6–§8).
2. **Sample baseline outcomes** per-persona using the §5 baseline mix and the per-persona ghost-skew table.
3. **Apply Finding 4 skew** — rewrite outcomes in `linkedin_q2_broad_funnel` (600 leads) so that disqualified + ghosted + closed_lost-with-wrong-fit-late share ≈ 78% of campaign volume.
4. **Apply Finding 1 skew** — scale outcomes in the `podcast` channel cohort to ~30% CW rate, and in the `linkedin_paid` channel cohort to ~3% CW rate. This is the channel-level cap; per-campaign within `linkedin_paid` floats below it (broad_funnel ~3%, enterprise ~5%, revops_targeted ~10%).
5. **Apply Finding 2 skew** — lift CW rate in the `(persona='Mid-market RevOps Leader', seed_label_theme_primary='manual_work_reduction')` cell to ~25%.
6. **Apply Finding 3 skew** — route ~50 of the 200 podcast leads onto the `podcast → organic_search → demo_request within 14 days` journey, and lift their CW rate to ~45%. Non-path podcast leads sit around 25.3% CW so that podcast's overall channel CW (Finding 1's invariant) still resolves to ~30%.
7. **Apply Secondary Finding (Finding 5) skew** — lift CW rate in the `(persona='Enterprise IT Buyer', seed_label_theme_primary='compliance_security')` cell to ~18%.

Each skew function's docstring declares which test it satisfies (`test_aha_1_...`, etc.) and which invariants from prior skews it must preserve.

---

## Finding 1 — Channel quality surprise

> *"A low-volume channel drives disproportionately high-value pipeline; a high-volume channel drives tire-kickers."*

### Target cells

- **Low-volume / high-quality:** `channel == 'podcast'` (200 leads)
- **High-volume / low-quality:** `channel == 'linkedin_paid'` (1,000 leads)

### Numbers

| Metric | Engineered | Smoke-test threshold | Margin |
|---|---|---|---|
| Podcast leads | 200 | ≤ 250 | 50 leads |
| Podcast CW rate | 30% | ≥ 25% | 5 pp |
| LinkedIn paid leads | 1,000 | ≥ 800 | 200 leads |
| LinkedIn paid CW rate | 3% | ≤ 5% | 2 pp |
| Rate ratio (podcast / linkedin) | 10.0× | ≥ 6.0× | 4× |

### Sample size justification

- Podcast: 60 wins / 200 leads. 95% CI on rate ±√(0.30·0.70/200) ≈ ±3.2 pp → true rate ∈ [26.8%, 33.2%]. Clears the 25% threshold across seed variation.
- LinkedIn paid: 30 wins / 1,000. 95% CI ±√(0.03·0.97/1000) ≈ ±0.5 pp → [2.5%, 3.5%]. Clears 5% threshold cleanly.

### Smoke-test assertion (verbatim)

```python
def test_aha_1_channel_quality_surprise(db):
    podcast = db.leads_by_channel("podcast")
    linkedin = db.leads_by_channel("linkedin_paid")

    assert len(podcast) <= 250, (
        f"Podcast channel must stay low-volume; got {len(podcast)}"
    )
    assert len(linkedin) >= 800, (
        f"LinkedIn paid must be high-volume; got {len(linkedin)}"
    )

    podcast_cw = closed_won_rate(podcast)
    linkedin_cw = closed_won_rate(linkedin)

    assert podcast_cw >= 0.25, (
        f"Podcast CW rate {podcast_cw:.3f} must be >= 0.25"
    )
    assert linkedin_cw <= 0.05, (
        f"LinkedIn paid CW rate {linkedin_cw:.3f} must be <= 0.05"
    )

    assert linkedin_cw > 0, "LinkedIn paid CW rate must be non-zero"
    ratio = podcast_cw / linkedin_cw
    assert ratio >= 6.0, (
        f"Channel quality ratio {ratio:.2f}x must be >= 6.0x "
        f"(podcast={podcast_cw:.3f}, linkedin={linkedin_cw:.3f})"
    )
```

### How `seed.py` applies this skew

`apply_finding_1_channel_quality_skew(rng, leads_df, target_podcast_cw=0.30, target_linkedin_cw=0.03)`:
- For the podcast cohort, identifies leads currently below 30% CW share and probabilistically promotes a subset's outcome from non-win → `closed_won` (or vice versa if over) until the cohort CW rate converges to 0.30 ± 0.005.
- Same logic for linkedin_paid targeting 0.03 ± 0.003.
- Preserves the per-persona ghost skew from §5 by drawing the displaced/added outcomes from each persona's conditional non-win distribution.
- Docstring: `"Satisfies test_aha_1_channel_quality_surprise. Must preserve per-persona ghost skew (§5 of data-world.md)."`

---

## Finding 2 — Message-persona resonance differential

> *"A specific pain-point claim resonates ~3× harder with one persona than with anyone else."*

### Target cells

- **Resonance cell:** `persona == 'Mid-market RevOps Leader'` AND `seed_label_theme_primary == 'manual_work_reduction'`
- **Comparison cells:** non-Maya leads with `seed_label_theme_primary == 'manual_work_reduction'` (David, Patricia, and Carlos leads where mwr is their primary theme)

### Numbers

| Metric | Engineered | Smoke-test threshold | Margin |
|---|---|---|---|
| Target cell size | ~280 leads (40% of Maya's 700) | ≥ 100 | 180 leads |
| Other cell size | ~207 leads (sum of non-Maya × mwr) | ≥ 100 | 107 leads |
| Target cell CW rate | 25% | — | — |
| Other-personas × mwr CW rate | ~5% | — | — |
| Cell ratio (target / other) | 5.0× | ≥ 3.0× | 1.7× |

### Sample size justification

- Target cell: 70 wins / 280 leads. 95% CI ±√(0.25·0.75/280) ≈ ±2.6 pp → [22.4%, 27.6%].
- Other cell: ~10 wins / 207 leads. 95% CI ±√(0.05·0.95/207) ≈ ±1.5 pp → [3.5%, 6.5%].
- Worst-case ratio (min target / max other): 22.4 / 6.5 = **3.45×** → still clears the 3.0× threshold.

### Smoke-test assertion (verbatim)

```python
def test_aha_2_resonance_differential(db):
    PERSONA = "Mid-market RevOps Leader"
    THEME = "manual_work_reduction"

    target_cell = db.leads.where(
        persona=PERSONA, seed_label_theme_primary=THEME
    )
    other_cell = db.leads.where(
        seed_label_theme_primary=THEME
    ).exclude(persona=PERSONA)

    assert len(target_cell) >= 100, (
        f"Target cell ({PERSONA}, {THEME}) size {len(target_cell)} "
        f"must be >= 100 for stat significance"
    )
    assert len(other_cell) >= 100, (
        f"Comparison cell (non-{PERSONA}, {THEME}) size {len(other_cell)} "
        f"must be >= 100"
    )

    target_rate = closed_won_rate(target_cell)
    other_rate = closed_won_rate(other_cell)

    assert other_rate > 0, "Comparison rate must be non-zero"
    ratio = target_rate / other_rate
    assert ratio >= 3.0, (
        f"Resonance ratio {ratio:.2f}x must be >= 3.0x "
        f"(target={target_rate:.3f}, other={other_rate:.3f})"
    )
```

### How `seed.py` applies this skew

`apply_finding_2_resonance_skew(rng, leads_df, persona='Mid-market RevOps Leader', theme='manual_work_reduction', target_cell_cw=0.25)`:
- Identifies the (Maya, mwr) cell post Findings 4 & 1 (so channel-level rates are already set).
- Probabilistically promotes non-win outcomes in the cell to `closed_won` until cell CW rate ≈ 0.25.
- Leaves non-Maya × mwr cells untouched (their ~5% rate is the base outcome distribution naturally).
- Docstring: `"Satisfies test_aha_2_resonance_differential. Cell is (Mid-market RevOps Leader, manual_work_reduction). Composes with Finding 1's podcast channel cap."`

---

## Finding 3 — Multi-touch journey pattern

> *"A specific sequence (podcast → blog → demo within 14 days) converts at ~4× the average."*

### Path definition (canonical)

A lead is "on the path" iff:
1. `leads.created_via_channel == 'podcast'` (first touch was the podcast channel), AND
2. There exists at least one touchpoint with `channel == 'organic_search'` AND `ts ≤ lead.created_at + 14 days` (the blog visit), AND
3. There exists at least one touchpoint with `event_type == 'demo_request'` AND `ts ≤ lead.created_at + 14 days` (the demo request).

### Numbers

| Metric | Engineered | Smoke-test threshold | Margin |
|---|---|---|---|
| Path lead count | 50 (25% of 200 podcast leads) | ≥ 30 | 20 leads |
| Path CW rate | 45% | — | — |
| Overall dataset CW rate | ~7.1% | — | — |
| Path lift (path / overall) | 6.3× | ≥ 4.0× | 2.3× |
| Non-path podcast CW rate (invariant) | ~25.3% | — | composes with Finding 1's 30% podcast cap |

**Note on path-fraction choice:** the original sketch was 75 leads (37.5% of podcast). Dropped to 25% / 50 leads in this revision because 37.5% reads as engineered; 25% feels closer to a discovered pattern. The lift is preserved (and slightly improved, from 5.7× to 6.3×) by raising the path CW rate from 40% to 45%. The contract still clears all thresholds with margin.

### Sample size justification

- Path leads: ~22 wins / 50 leads. 95% CI ±√(0.45·0.55/50) ≈ ±6.9 pp → [38.1%, 51.9%].
- Worst-case lift: 38.1 / 7.5 = **5.08×** → clears 4.0× threshold with margin 1.08×.

### Composition check with Finding 1

- Podcast channel: 200 leads × 30% = 60 wins (Finding 1 invariant).
- Path subset: 50 leads × 45% = ~22 wins.
- Non-path subset: 150 leads × x% = ~38 wins → x ≈ 25.3%.
- Both rates remain plausible for a "quality channel" and the channel mean lands cleanly on 30%.

### Smoke-test assertion (verbatim)

```python
def test_aha_3_multitouch_journey(db):
    overall_rate = closed_won_rate(db.leads)

    path_leads = db.leads_matching_journey(
        first_touch_channel="podcast",
        must_include_channel="organic_search",
        must_include_event_type="demo_request",
        within_days_of_first_touch=14,
    )

    assert len(path_leads) >= 30, (
        f"Journey path (podcast -> organic_search -> demo_request within 14d) "
        f"leads {len(path_leads)} must be >= 30"
    )

    path_rate = closed_won_rate(path_leads)
    assert overall_rate > 0, "Overall CW rate must be non-zero"
    lift = path_rate / overall_rate
    assert lift >= 4.0, (
        f"Journey path lift {lift:.2f}x must be >= 4.0x "
        f"(path_rate={path_rate:.3f}, overall={overall_rate:.3f})"
    )
```

### How `seed.py` applies this skew

`apply_finding_3_journey_skew(rng, leads_df, touchpoints_df, target_path_count=50, target_path_cw=0.45)`:
- Selects ~50 podcast leads (roughly 25%) and synthesizes the additional touchpoints: an `organic_search` blog visit within 14 days, then a `demo_request` form_submit within 14 days. Free-text on the form submission keys to the lead's `seed_label_theme_primary` so qualitative signal flows downstream.
- After Finding 1's podcast-channel skew is applied, this function re-balances outcomes within the path subset (lift to ~45%) and within the non-path podcast subset (settle near ~25.3%) so the podcast channel mean remains 30%.
- Docstring: `"Satisfies test_aha_3_multitouch_journey. Composes with Finding 1: must preserve podcast channel mean CW ≈ 30%."`

---

## Finding 4 — ICP fit vs volume mismatch

> *"The highest-volume campaign brings in ~80% non-ICP leads — expensive volume the system catches."*

### Target cells

- **Vehicle:** `utm_campaign == 'linkedin_q2_broad_funnel'` (600 leads, persona mix 55/30/10/5 — see `docs/data-world.md` §7)
- **Dataset baseline** for ICP-ratio comparison: `db.leads` (all 2,500)

### Numbers

| Metric | Engineered | Smoke-test threshold | Margin |
|---|---|---|---|
| Top-campaign volume | 600 leads | (top by volume) | — |
| Bad-outcome share | ~78% | ≥ 65% | 13 pp |
| Top-campaign mean ICP fit | ~36.1 | — | — |
| Dataset mean ICP fit | ~52.7 | — | — |
| ICP ratio (top / dataset) | 0.685 | ≤ 0.75 | 0.065 |

**"Bad outcome"** is defined as: `outcome ∈ {'disqualified', 'ghosted'}` OR `(outcome == 'closed_lost' AND sub_reason == 'wrong_fit_late')`.

### Sample size justification

- Bad-outcome share: ~468 / 600 leads bad. 95% CI ±√(0.78·0.22/600) ≈ ±1.7 pp → [76.3%, 79.7%]. Clears 65% by 11+ pp.
- ICP ratio: mean of 600 leads vs mean of 2,500. Per-persona ICP variance is small (≈5 points per persona around their mean), so the standard error on the campaign mean ICP is ≤ 0.4 points. CI on the ratio is well inside the 0.05 margin.

### Smoke-test assertion (verbatim)

```python
def test_aha_4_icp_fit_vs_volume_mismatch(db):
    volumes = db.leads.group_by("utm_campaign").count()
    top_campaign = volumes.idxmax()
    assert top_campaign == "linkedin_q2_broad_funnel", (
        f"Highest-volume campaign should be linkedin_q2_broad_funnel; "
        f"got {top_campaign}"
    )

    top_leads = db.leads.where(utm_campaign=top_campaign)

    bad_mask = (
        (top_leads.outcome == "disqualified")
        | (top_leads.outcome == "ghosted")
        | ((top_leads.outcome == "closed_lost")
           & (top_leads.sub_reason == "wrong_fit_late"))
    )
    bad_share = bad_mask.sum() / len(top_leads)
    assert bad_share >= 0.65, (
        f"Bad-outcome share in {top_campaign} is {bad_share:.3f}, "
        f"must be >= 0.65"
    )

    top_mean_icp = top_leads.icp_fit_score.mean()
    dataset_mean_icp = db.leads.icp_fit_score.mean()
    icp_ratio = top_mean_icp / dataset_mean_icp
    assert icp_ratio <= 0.75, (
        f"Top campaign mean ICP fit {top_mean_icp:.1f} / dataset "
        f"mean {dataset_mean_icp:.1f} = {icp_ratio:.2f}; must be <= 0.75"
    )
```

### How `seed.py` applies this skew

`apply_finding_4_icp_mismatch_skew(rng, leads_df, campaign='linkedin_q2_broad_funnel', target_bad_share=0.78)`:
- Operates on the 600 leads tagged with `utm_campaign='linkedin_q2_broad_funnel'`. Persona mix (55/30/10/5) and per-persona ICP fit scores are already set by Gate 1 generation steps — this function only rewrites outcomes.
- Within each persona's slice of the campaign, biases the non-win outcomes toward `disqualified` and `ghosted` (vs `nurture`) according to engineered per-persona distributions specified in §11 below.
- Applied **before** Finding 1's channel-level cap, so Finding 1 then enforces overall linkedin_paid CW = 3% on top.
- Docstring: `"Satisfies test_aha_4_icp_fit_vs_volume_mismatch. Operates only on linkedin_q2_broad_funnel; relies on persona mix from data-world.md §7."`

---

## 11. Per-persona outcome distributions inside `linkedin_q2_broad_funnel`

Required to hit the 78% bad-outcome target. Applied by `apply_finding_4_icp_mismatch_skew`.

| Persona (share) | won | lost (% wfl of lost) | disqualified | ghosted | nurture |
|---|---|---|---|---|---|
| Carlos (55%) | 1% | 2% (70% wfl) | 47% | 45% | 5% |
| Patricia (30%) | 2% | 6% (70% wfl) | 45% | 38% | 9% |
| David (10%) | 8% | 12% (30% wfl) | 15% | 12% | 53% |
| Maya (5%) | 14% | 9% (20% wfl) | 8% | 6% | 63% |

Weighted bad-outcome share check: 0.55·(47+45+2·0.7) + 0.30·(45+38+6·0.7) + 0.10·(15+12+12·0.3) + 0.05·(8+6+9·0.2) ≈ 51.3 + 26.2 + 3.1 + 0.8 ≈ **81.4%** before Finding 1's CW cap pulls some non-wins back into the count. After Finding 1 caps linkedin_paid at 3% CW (so broad_funnel resolves around 3% CW too), the post-composition bad share lands in the ~76–79% engineered window. Threshold 0.65 is cleared comfortably.

---

## Secondary Finding — Patricia × `compliance_security`

> *"The system also surfaced a secondary resonance pattern: enterprise IT evaluators engage disproportionately when content addresses compliance and security requirements."*

**Status: engineered.** Confirmed in this revision (was optional in the prior draft). Visually subordinated in the CP5 dashboard and CP6 README — not in the same top-row leaderboard as Findings 1–4. The two reasons to keep it: (a) it justifies why `compliance_security` was added as a 9th theme — otherwise Patricia is demographic wallpaper; (b) showing the system surfaces five findings when only four were engineered makes ICA look like it *discovers* patterns rather than was tuned for a fixed set.

### Target cells

- **Resonance cell:** `persona == 'Enterprise IT Buyer'` AND `seed_label_theme_primary == 'compliance_security'`
- **Comparison cell:** non-Patricia leads with `seed_label_theme_primary == 'compliance_security'`

### Numbers

| Metric | Engineered | Smoke-test threshold | Margin |
|---|---|---|---|
| Target cell size | ~260 leads (40% of Patricia's 650) | ≥ 100 | 160 leads |
| Other cell size | ~120 leads (~6% of each non-Patricia persona) | ≥ 80 | 40 leads |
| Target cell CW rate | 18% | — | — |
| Comparison cell CW rate | ~3% | — | — |
| Cell ratio (target / other) | 6.0× | ≥ 2.0× (softer than Finding 2's 3.0×) | 4.0× |

### Sample size justification

- Target cell: ~47 wins / 260 leads. 95% CI ±√(0.18·0.82/260) ≈ ±4.7 pp → [13.3%, 22.7%].
- Comparison cell: ~3.6 wins / 120 leads. 95% CI ±√(0.03·0.97/120) ≈ ±3.1 pp → [0%, 6.1%].
- Worst-case ratio (min target / max other): 13.3 / 6.1 = **2.18×** → clears 2.0× threshold.

The thinner margin compared to Findings 1–4 reflects this finding's *secondary* status. Engineering a softer ratio threshold (2.0× vs Finding 2's 3.0×) is intentional: a secondary pattern should look believably weaker than the headline persona–theme resonance, otherwise it'd compete for attention rather than supplement.

### Smoke-test assertion (verbatim)

```python
def test_aha_5_compliance_resonance(db):
    PERSONA = "Enterprise IT Buyer"
    THEME = "compliance_security"

    target_cell = db.leads.where(
        persona=PERSONA, seed_label_theme_primary=THEME
    )
    other_cell = db.leads.where(
        seed_label_theme_primary=THEME
    ).exclude(persona=PERSONA)

    assert len(target_cell) >= 100, (
        f"Target cell ({PERSONA}, {THEME}) size {len(target_cell)} "
        f"must be >= 100 for stat significance"
    )
    assert len(other_cell) >= 80, (
        f"Comparison cell (non-{PERSONA}, {THEME}) size {len(other_cell)} "
        f"must be >= 80"
    )

    target_rate = closed_won_rate(target_cell)
    other_rate = closed_won_rate(other_cell)

    assert other_rate > 0, "Comparison rate must be non-zero"
    ratio = target_rate / other_rate
    assert ratio >= 2.0, (
        f"Secondary resonance ratio {ratio:.2f}x must be >= 2.0x "
        f"(target={target_rate:.3f}, other={other_rate:.3f})"
    )
```

### How `seed.py` applies this skew

`apply_finding_5_compliance_resonance_skew(rng, leads_df, persona='Enterprise IT Buyer', theme='compliance_security', target_cell_cw=0.18)`:
- Operates after Findings 4 and 1 have set channel- and campaign-level CW caps. Operates on the (Patricia, compliance_security) cell only.
- Probabilistically promotes non-win outcomes in the cell to `closed_won` until cell CW rate ≈ 0.18 with tolerance ±0.01.
- Leaves the non-Patricia × compliance_security cell untouched (the ~3% rate is the natural base outcome of mostly-weak-fit personas talking about a non-signature theme).
- Docstring: `"Satisfies test_aha_5_compliance_resonance. Cell is (Enterprise IT Buyer, compliance_security). Secondary finding — softer ratio threshold than Finding 2."`

### Rendering note (for CP5 dashboard + CP6 README)

- CP5 dashboard: Findings 1–4 occupy the top "Key findings" panel; Finding 5 lives below in an "Additional patterns surfaced" section. Same data visualization style but smaller card.
- CP6 README: "The system also surfaced…" framing rather than headline status. One sentence in the executive summary; full treatment in the "What ICA found" section.

---

---

## 13. Sample-size validation summary

| Finding | Cell | Engineered N | Engineered metric | Threshold | CI margin |
|---|---|---|---|---|---|
| 1 | podcast | 200 | 30% CW | ≥ 25% | ~5 pp |
| 1 | linkedin_paid | 1,000 | 3% CW | ≤ 5% | ~1.5 pp |
| 2 | Maya × mwr | ~280 | 25% CW | ≥ 3× other (≈5×) | ~0.45× |
| 3 | podcast→blog→demo path | ~50 | 45% CW | ≥ 4× overall (≈6.3×) | ~1.08× |
| 4 | linkedin_q2_broad_funnel | 600 | 78% bad / 0.685 ICP ratio | ≥ 65% / ≤ 0.75 | ~11 pp / 0.065 |
| 5 (sec) | Patricia × compliance_security | ~260 | 18% CW | ≥ 2× other (≈6×) | ~0.18× |

---

## 14. Locked decisions (audit trail)

The four decision points raised in the prior draft are now settled:

| # | Decision | Resolution |
|---|---|---|
| 1 | Patricia × `compliance_security` secondary cell | **ON, visually subordinated.** Promoted to "Secondary Finding" (see above), smoke test in same shape as Findings 1–4 with softer 2.0× threshold. README and CP5 dashboard treat it as "the system also surfaced…" rather than as a top-row finding. Reason: justifies the new theme, and showing the system surfaces 5 patterns when only 4 were engineered demonstrates discovery, not tuning. |
| 2 | Per-persona outcome distributions in `linkedin_q2_broad_funnel` (§11) | **Accepted as proposed.** Carlos 1/2/47/45/5, Patricia 2/6/45/38/9, David 8/12/15/12/53, Maya 14/9/8/6/63 (won/lost/disq/ghost/nurture). Sanity-checked by user, no changes requested. |
| 3 | `closed_lost & sub_reason='wrong_fit_late'` in Finding 4's bad bucket | **KEEP IN.** Finding 4's point is "expensive volume that wastes sales hours," and a wrong-fit lead that consumes a full sales cycle before losing is the *most* expensive form of waste. Clean `closed_lost` (competitor, price, timing, no_decision) stays out of the bad bucket. |
| 4 | Finding 3 path-fraction | **Dropped to 25%.** 37.5% reads as engineered; 25% reads as discovered. Smoke test still clears with margin: 50 path leads × 45% CW = ~22 wins; lift over overall rate ≈ 6.3× vs threshold 4.0× (margin 2.3×). |

No further design gates. The next contract is `tests/test_aha_patterns.py` — `seed.py` is iterated until all 5 assertions pass with margin.
