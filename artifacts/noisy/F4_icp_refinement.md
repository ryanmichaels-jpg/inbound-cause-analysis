# ICP Refinement Brief: linkedin_q2_broad_funnel Segment

> The linkedin_q2_broad_funnel campaign generated the highest lead volume (586) but an 80% bad-outcome rate and a mean ICP fit score of 37 vs. 53 dataset-wide, signaling the targeting criteria must be tightened before any further spend.

*Icp Refinement — generated from Finding F4 by `claude-sonnet-4-6` on 2026-05-25T14:03:45+00:00.*

With 80% of 586 leads ending as disqualified, ghosted, or wrong-fit, roughly 469 leads consumed pipeline capacity without revenue return. The mean ICP fit of 37 sits 16 points below the dataset average of 53, confirming this is a systematic targeting problem, not a conversion or messaging problem. The buyer quotes surface two recurring operational pain themes — manual list-building consuming ~12 hours per week and an inability to explain forecast gaps after the quarter closes — which are specific, measurable pains that can be encoded as positive ICP signals. Refining firmographic and technographic filters around these signals before the next campaign flight will reduce wasted SDR hours and improve fit scores toward the dataset benchmark.

## Problem Statement

linkedin_q2_broad_funnel is the largest campaign by volume (586 leads) but produces the worst outcomes: 80% bad-outcome share and a mean ICP fit score of 37 against a dataset-wide mean of 53. Continuing to run broad targeting into this audience wastes SDR capacity and suppresses overall pipeline quality.

## Positive ICP Signals to Add (Inclusion Criteria)

- PAIN SIGNAL 1 — Manual ops overhead: Prospect's team references manual list-building, copy-paste workflows between tools, or ops staff spending significant time on administrative tasks rather than strategic work. Proxy indicators: job postings for 'RevOps Analyst' or 'Marketing Ops' citing tool consolidation; tech stack includes 3+ point solutions with no stated integration layer.
- PAIN SIGNAL 2 — Forecast accuracy gap: Prospect's org misses quarterly commit numbers and lacks a documented post-mortem process. Proxy indicators: VP/Director of Sales or RevOps title with tenure under 18 months (inherited broken process); company has missed public or stated revenue targets in the last two quarters.
- ROLE SIGNAL: Primary buyer persona should hold an operational or revenue accountability title (RevOps, Sales Ops, VP Sales, CRO) — not a generic 'Business Development' or 'Growth' title, which likely drove fit score dilution in the broad campaign.
- SIZE SIGNAL: Prioritize companies with a dedicated ops function of at least 2 FTEs (consistent with the quote referencing 'two ops folks'), indicating enough organizational maturity to have budget authority and enough pain to act.

## Negative ICP Signals to Add (Exclusion Criteria)

- Companies with fewer than 2 ops-aligned headcount — pain exists but budget authority and urgency are typically absent.
- Accounts already using an integrated RevOps platform (e.g., a full Salesforce + integrated MAP + BI stack) — the manual workflow pain is unlikely to resonate.
- Leads sourced from broad interest audiences (e.g., LinkedIn Audience Expansion, lookalike tiers 3+) without firmographic pre-filtering — this is the likely root cause of the fit score gap and should be disabled at the campaign level.

## Recommended LinkedIn Campaign Targeting Changes

- Swap 'broad funnel' audience for a job-function filter of: Sales Operations, Revenue Operations, Marketing Operations — combined with seniority of Manager and above.
- Layer in company size filter aligned to the ops headcount proxy: target companies with 50–500 employees where a dedicated ops function is plausible but not yet fully systematized.
- Disable LinkedIn Audience Expansion for this campaign to prevent the algorithm from drifting into low-fit segments.
- Add a negative audience list of current customers and accounts already in active pipeline to avoid wasting impressions on non-addressable contacts.

## ICP Fit Score Target

The immediate goal is to move mean ICP fit from 37 toward the dataset average of 53 within the next campaign flight. A secondary goal of 58–60 is appropriate once exclusion lists and tighter targeting are validated over one full campaign cycle. RevOps should flag any net-new leads from this campaign below a fit score of 45 for immediate review before SDR assignment.

## Suggested Qualification Questions (SDR / Form)

- How many hours per week does your ops team spend on list-building or data prep before a campaign launches?
- When you miss a quarterly number, how quickly can you identify the root cause — and what tools are you using to do that?
- How many separate tools does your team touch to move a lead from first touch to closed-won?

## Owner & Timeline

Owner: Demand Gen (campaign targeting changes) + RevOps (ICP scoring model update). Target: Targeting changes applied before next LinkedIn campaign flight. ICP scoring criteria updated in CRM within 5 business days so SDRs can apply the new framework to any residual leads still in queue from the original campaign.
