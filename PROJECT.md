# Inbound Cause Analysis (ICA)

> Jesse's RCA pipeline, flipped. Instead of identifying what to *eliminate* in support, ICA identifies what to *amplify* in GTM by analyzing why inbound leads convert and which messages, channels, and content resonate.

A GTM Engineering portfolio piece, structurally parallel to [jesseautomates/case-study-3](https://github.com/jesseautomates/case-study-3) but with the optimization function flipped from "reduce demand" to "amplify what works."

---

## Foundation

**Audience.** Growth-stage SaaS (Series B+) building out their GTM Engineering / Rev Ops function. README voice and the synthetic company are tuned to this segment — a 150–500 person SaaS with a maturing stack, hiring for repeatability and integration depth.

**Time budget.** Weekend sprint (~2 focused days). See *Ruthless cut order* below if time slips.

**Signature move.** **Auto-generated GTM action artifacts** — content briefs, ad copy variants, ICP refinements auto-drafted from the resonance themes the system surfaces. Most portfolio pieces stop at "here's a dashboard." This one ships downstream artifacts that close the loop from insight → action. That's the differentiator.

**Narrative arc.** Contrarian reframe, mirrored from Jesse: *"Most GTM teams optimize tactics — channel mix, copy A/B tests, lead routing rules. The real lever is understanding why people raise their hand, and doing more of that."*

---

## The four "aha" findings the dataset must produce

The synthetic dataset is reverse-engineered from these. If any is missing from the final dashboard, we re-seed.

1. **Channel quality surprise.** A low-volume channel (e.g., a podcast appearance) drives disproportionately high-value pipeline; a high-volume channel (e.g., LinkedIn paid) drives tire-kickers. Classic Pareto reframe.
2. **Message–persona resonance differential.** A specific pain-point claim resonates ~3x harder with one persona (e.g., mid-market ops leaders) than with anyone else.
3. **Multi-touch journey pattern.** A specific sequence ("podcast → blog → demo within 14 days") converts at ~4x the average. Shows the system reconstructs full journeys, not just first/last touch.
4. **ICP fit vs volume mismatch.** The highest-volume campaign brings in ~80% non-ICP leads — expensive volume the system catches.

---

## Architecture (5 stages, mirroring Jesse)

1. **Ingestion.** Synthetic event stream — form fills, demo requests, content downloads. Each event carries attribution (UTM, referrer, first/last touch), enrichment (company, role, industry, size), and qualitative signal (form free-text, "how did you hear about us", simulated sales notes / Gong-style transcript snippets).
2. **Structuring.** Normalize into unified lead records, join touchpoints into journeys, tag with persona + ICP fit score.
3. **Driver identification.** Cluster leads by entry path, surface high-volume drivers.
4. **Resonance analysis (the LLM layer).** Claude extracts the *why* from qualitative fields, clusters into resonance themes, ties themes back to drivers and personas. This is the stage with no equivalent in Jesse's repo and the strongest portfolio differentiator.
5. **Insight + loop-back.** Rank drivers and themes by `volume × pipeline quality`, render to a live dashboard, and emit auto-generated GTM action artifacts.

---

## Stack

- Python (3.11+) for the pipeline
- Anthropic Claude API for the resonance / extraction layer
- SQLite for the local data store
- Streamlit for the dashboard
- Deployed to Streamlit Cloud for a public clickable link
- Repo runs locally with one command (`make demo` or equivalent)

---

## LLM credibility approach

**Theme-stability check across runs.** Run the resonance extraction N times on the same dataset and measure how stable the extracted themes are. Surface a stability score in the dashboard and write the methodology into the README. Realistic in a weekend; shows nondeterminism is taken seriously.

---

## "Would this work on real data?" answer

**Production wiring sketch in the README.** A short section per common source (HubSpot, Salesforce, Marketo, Gong) describing what the connector would look like and what changes vs. the synthetic version. Two sentences each. High credibility for low effort.

---

## Phase 2 (sketched in README, not built)

**Closed-loop measurement.** Track whether the GTM actions ICA recommended actually drove more / better pipeline over the following quarter. Direct parallel to Jesse's Phase 2 ("measure the fix impact").

---

## Deliverables

- Public GitHub repo (one-command local run)
- Live deployed Streamlit demo (clickable from portfolio)
- README in Jesse's voice and structure
- Architecture + process flow diagrams (PNG)
- "Phase 1 ICA Summary" PDF deliverable mirroring Jesse's shape
- (Optional) Loom or written walkthrough

---

## Build sequence

Six checkpoints, each demoable on its own so the project is portfolio-worthy at any stopping point.

1. **Synthetic data generator + schema** — five linked tables (leads, touchpoints, form submissions with free-text, sales notes/transcripts, outcomes), seeded with the four aha findings.
2. **Ingestion + structuring layer** — load, normalize, join, ICP-score.
3. **Driver identification** — cluster by entry path, rank by `volume × quality`.
4. **Resonance analysis layer** — Claude extraction + theme-stability check.
5. **Streamlit dashboard** + auto-generated GTM action artifacts.
6. **Case study writeup** + diagrams + deploy.

---

## Ruthless cut order (if the weekend slips)

The scope is genuinely ambitious for two days. If time runs short, cut in this order:

1. Auto-generated GTM action artifacts → minimal version: 1–2 example artifacts hard-templated from real themes, not fully generated.
2. PDF deliverable → just the README + dashboard.
3. Theme-stability check → acknowledge in README as the planned next step.
4. Loom walkthrough → optional anyway.
5. Trim aha findings from 4 to 2 (keep channel quality surprise + message–persona resonance — they're the most teachable).

---

## Open decisions (not blocking the build)

- Synthetic company name and one-paragraph backstory.
- Specific persona names (e.g., "Maya, VP Ops at a 200-person fintech").
- Exact resonance taxonomy schema — free-form themes or fixed top-level categories?
- Streamlit Cloud account vs alternative if deploy gets messy.
- Whether to include "negative signal" leads (came in, never engaged) in v1 or punt.

---

## Reference

- Source inspiration: [jesseautomates/case-study-3](https://github.com/jesseautomates/case-study-3) — RCA system for support tickets. ICA mirrors its structure (five-stage pipeline, executive deliverable, Phase 1/Phase 2 framing) but inverts the optimization function.
