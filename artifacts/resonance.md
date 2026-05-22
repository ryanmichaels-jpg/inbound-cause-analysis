# Resonance extraction report

*CP4 resonance layer — `claude-haiku-4-5-20251001` over 2736 free-text snippets, generated 2026-05-22T00:22:47+00:00.*

## Extraction vs seed labels

Claude's extracted primary theme matched the seed `ground_truth_themes` on **92.3%** of snippets (2524/2736).

| Seed theme | Agreement | n |
| --- | --- | --- |
| compliance_security | 91% | 408 |
| cross_team_alignment | 80% | 109 |
| data_quality | 99% | 275 |
| forecasting_accuracy | 100% | 253 |
| manual_work_reduction | 99% | 541 |
| onboarding_ramp | 90% | 213 |
| pipeline_attribution | 93% | 349 |
| rep_efficiency | 72% | 345 |
| tool_sprawl_consolidation | 100% | 243 |

## Cross-run stability

Across 3 temperature-0 runs, **98.8%** of snippets received the same primary theme in every run (2736 scored).

## Extracted theme mix by persona

- **Mid-market RevOps Leader**: manual_work_reduction (314), pipeline_attribution (147), data_quality (114)
- **VP Sales at growth-stage SaaS**: rep_efficiency (146), forecasting_accuracy (136), manual_work_reduction (127)
- **Enterprise IT Buyer**: compliance_security (267), tool_sprawl_consolidation (172), data_quality (114)
- **SMB Founder**: onboarding_ramp (191), manual_work_reduction (178), rep_efficiency (129)
