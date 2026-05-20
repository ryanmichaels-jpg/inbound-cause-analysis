"""Outcome assignment and the aha-pattern skew sequence.

outcomes.py is the last and largest skew module. It consumes the finalized
lead set (after channels.py and journeys.py) plus the touchpoints, and
produces the outcomes table rows and the sales_notes rows. It runs the
full skew sequence — baseline outcomes, then F4 -> F1 -> F2 -> F3 -> F5.

Sources: docs/data-world.md §1, §2.4, §2.5, §5, §6; docs/aha-patterns.md
(Findings 1-5, the skew-application order, §11); src/ica/taxonomy.py
(BASELINE_OUTCOME_MIX, PERSONA_GHOST_SHARE_OF_NON_WINS, CHANNEL_BASELINE_
CW_RATE, BROAD_FUNNEL_PERSONA_OUTCOMES, BROAD_FUNNEL_WFL_FRACTION_OF_LOST,
the F1-F5 target constants, sub-reason vocabularies).

TODO (planning header — review before any implementation). Each decision
is tagged DICTATED (locked-doc, cited) or PROPOSED (a v1 design choice).

== What outcomes.py produces ==
- outcomes table rows (one per lead): outcome, sub_reason, pipeline_value_usd,
  resolved_at, days_to_outcome [DICTATED §2.5].
- sales_notes rows for the leads that reached SQL/Opp [DICTATED §2.4, and
  the copy_bank module boundary].
NOT here: touchpoints / form_submissions (journeys.py). seed.py orchestrates
the call order and writes the DB; outcomes.py owns the skew logic. (The
stale placeholder said "skews live in seed.py" — corrected: the
apply_finding_* functions are outcomes.py's, seed.py only sequences them.)

== Correction to the brief: F4 is NOT fully done in channels.py ==
channels.py set broad_funnel's persona mix (55/30/10/5) and personas.py
set ICP scores — that satisfies F4's ICP-ratio component. But F4's
bad-outcome-share component (~78%) is an OUTCOME rewrite — aha-patterns.md
skew-order step 3, using taxonomy.BROAD_FUNNEL_PERSONA_OUTCOMES. No
outcomes exist until this module. So outcomes.py DOES run F4 (step 3).
[DICTATED — aha-patterns.md skew order + §11.]

== Skew sequence — DICTATED order, all in outcomes.py ==
aha-patterns.md "skew-application order": later skews override earlier
ones for affected leads; each later skew compensates within the enclosing
earlier cell to preserve the earlier invariant.

Step 2 — baseline outcomes (Item 7, 6). Per-persona sampling from
  BASELINE_OUTCOME_MIX (closed_won 6 / closed_lost 10 / disqualified 25 /
  ghosted 24 / nurture 35) [DICTATED §5], with the ghosted share of each
  persona's non-wins set by PERSONA_GHOST_SHARE_OF_NON_WINS (Maya 12 /
  David 18 / Patricia 30 / Carlos 38) [DICTATED §5]. Lead-level, in this
  module. PROPOSED: the non-won non-ghosted remainder splits into
  closed_lost / disqualified / nurture by the §5 proportions renormalized,
  nudged by persona outcome-lean (§6: Maya -> lost/nurture, Patricia ->
  disqualified, Carlos -> ghosted/disqualified) and ICP fit (weak fit ->
  disqualified). The exact nudge weights are a v1 choice.

Step 3 — F4 broad_funnel outcome rewrite. Rewrite the 600
  linkedin_q2_broad_funnel leads' outcomes per BROAD_FUNNEL_PERSONA_OUTCOMES
  (per-persona won/lost/disq/ghost/nurture) [DICTATED §11]; closed_lost
  sub_reason is wrong_fit_late at BROAD_FUNNEL_WFL_FRACTION_OF_LOST per
  persona. Target: bad share (disq + ghost + lost-wrong_fit_late) >= 65%,
  engineered ~78% [DICTATED aha-patterns F4].

Step 4 — F1 channel-CW skew (Item 1). Scale each channel cohort's
  closed_won rate to CHANNEL_BASELINE_CW_RATE — podcast 0.30, linkedin_paid
  0.03 are the engineered, smoke-tested values [DICTATED aha-patterns F1 +
  taxonomy PODCAST/LINKEDIN_PAID_TARGET_CW_RATE]; organic_search 0.07,
  newsletter 0.06, webinar 0.05, comparison_page 0.09 are the other four
  per-channel rates [taxonomy CHANNEL_BASELINE_CW_RATE]. Promote/demote
  outcomes within each cohort to converge; preserve the per-persona ghost
  skew when drawing displaced outcomes [DICTATED aha-patterns F1].

Steps 5 & 7 — F2 and F5 persona-theme CW lifts (Items 2, 4). F2: lift the
  (Maya, manual_work_reduction) cell — 280 leads — to F2_TARGET_CELL_CW_RATE
  = 0.25 absolute [DICTATED aha-patterns F2]. F5: lift the (Patricia,
  compliance_security) cell — 260 leads — to F5_TARGET_CELL_CW_RATE = 0.18
  absolute [DICTATED aha-patterns F5]. Both probabilistically promote
  non-win outcomes in-cell to closed_won until the cell rate converges.

Step 6 — F3 path CW lift (Item 3). 0.45 is the ABSOLUTE closed_won rate
  for the 50 path leads, not a lift on baseline [DICTATED aha-patterns F3 —
  "~22 wins / 50"]. F3 also rebalances the 150 non-path podcast leads to
  ~25.3% so the podcast channel mean stays 30% (F1's invariant): 50*0.45 +
  150*0.253 ≈ 60 = 0.30*200 [DICTATED aha-patterns F3].

== Item 5 — composition, worked example ==
PROPOSED composition model: skews run F4 -> F1 -> F2 -> F3 -> F5; each
skew, when it engineers its cell, COMPENSATES within the enclosing earlier
cell to preserve that cell's rate (F3's explicit non-path rebalance is the
template; F2/F5 apply the same — promote in-cell, compensate the rest of
the affected channel cohort). A lead in multiple cells is governed by the
LAST skew that touches it.
Worked example — Maya x mwr, on the F3 path (so podcast first-touch),
non-broad-funnel: F4 skips it (not broad_funnel); F1 places it in the
podcast cohort (channel CW 0.30); F2 would lift it as a (Maya, mwr) cell
member; F3 runs last and governs it as a path lead -> CW probability 0.45.
F2's cell-25% is then hit by the non-path Maya x mwr leads; F1's podcast
0.30 holds via F3's non-path compensation.

== Items 8 — dataset-level distribution ==
BASELINE_OUTCOME_MIX is the pre-skew baseline (closed_won 6%). Post-skew
the dataset closed_won rises to ~7.1% [DICTATED aha-patterns F3] — which
equals the volume-weighted CHANNEL_BASELINE_CW_RATE. The other four
outcome shares absorb the difference. Verification will confirm the final
dataset mix lands near §5 within tolerance, with CW ~7.1%.

== Item 9 — other locked-doc items ==
- pipeline_value_usd: non-null only for closed_won (log-normal $40k-$200k)
  and closed_lost ($30k-$150k); NULL otherwise [DICTATED §2.5].
- resolved_at = created_at + days_to_outcome; days_to_outcome 14-90,
  conditional on outcome (closed_won slowest, ghosted fastest) [DICTATED
  §1]. PROPOSED: per-outcome day ranges within 14-90.
- sub_reason: sampled from the per-outcome vocabulary (CLOSED_LOST_/
  DISQUALIFIED_/NURTURE_SUB_REASONS); NULL for closed_won and ghosted
  [DICTATED §2.5, §5].
- sales_notes only for leads that reached SQL/Opp — closed_won,
  closed_lost, disqualified-after-call, some ghosted-after-call; pure
  nurture / form-only ghosts get none [DICTATED §2.4]. PROPOSED: "reached
  SQL/Opp" is read from outcome + whether the lead has a demo_request /
  demo_attended touchpoint. sales_notes text via copy_bank.sales_note;
  ground_truth_themes from the returned Snippet.
- The §5-vs-CHANNEL_BASELINE tension: §5 says 6% baseline CW; the
  volume-weighted CHANNEL_BASELINE_CW_RATE is ~7.1%. Read as: §5's 6% is
  the pre-skew baseline mix (step 2), the channel skew (step 4) moves
  per-channel CW to CHANNEL_BASELINE_CW_RATE, netting ~7.1% — consistent
  with aha-patterns F3. Surfaced as a PROPOSED reconciliation.

== What outcomes.py does NOT do ==
- No touchpoints / form_submissions / leads-table fields.
- No DB writes — seed.py orchestrates and persists.
- No new taxonomy values — all targets imported.

Output: outcomes table rows + sales_notes rows; every lead has an outcome
that satisfies the five aha-pattern smoke tests (the CP1 contract).
"""
