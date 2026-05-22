# Resonance extraction report

*CP4 resonance layer — `claude-haiku-4-5-20251001` over 2736 free-text snippets, generated 2026-05-22T01:10:05+00:00.*

## Extraction vs seed labels

Claude's extracted primary theme matched the seed `ground_truth_themes` on **94.1%** of snippets (2574/2736).

| Seed theme | Agreement | n |
| --- | --- | --- |
| compliance_security | 88% | 408 |
| cross_team_alignment | 82% | 109 |
| data_quality | 100% | 275 |
| forecasting_accuracy | 100% | 253 |
| manual_work_reduction | 90% | 541 |
| onboarding_ramp | 89% | 213 |
| pipeline_attribution | 97% | 349 |
| rep_efficiency | 99% | 345 |
| tool_sprawl_consolidation | 100% | 243 |

## Cross-run stability

Across 3 temperature-0 runs, **99.1%** of snippets received the same primary theme in every run (2736 scored).

## Extracted theme mix by persona

- **Mid-market RevOps Leader**: manual_work_reduction (298), pipeline_attribution (153), data_quality (115)
- **VP Sales at growth-stage SaaS**: rep_efficiency (202), forecasting_accuracy (136), pipeline_attribution (120)
- **Enterprise IT Buyer**: compliance_security (259), tool_sprawl_consolidation (180), data_quality (115)
- **SMB Founder**: rep_efficiency (204), onboarding_ramp (190), manual_work_reduction (104)
