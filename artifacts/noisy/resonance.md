# Resonance extraction report

*CP4 resonance layer — `claude-haiku-4-5-20251001` over 2039 free-text snippets, generated 2026-05-25T14:04:17+00:00.*

*v1.5 methodology: empty-text fields excluded from extraction. 697 of 2736 qualitative fields (25.5%) were blank (noise-layer missingness) and skipped.*

## Extraction vs seed labels

Claude's extracted primary theme matched the seed `ground_truth_themes` on **94.4%** of snippets (1925/2039).

| Seed theme | Agreement | n |
| --- | --- | --- |
| compliance_security | 90% | 308 |
| cross_team_alignment | 86% | 85 |
| data_quality | 99% | 210 |
| forecasting_accuracy | 100% | 196 |
| manual_work_reduction | 89% | 394 |
| onboarding_ramp | 94% | 160 |
| pipeline_attribution | 94% | 252 |
| rep_efficiency | 100% | 253 |
| tool_sprawl_consolidation | 100% | 181 |

## Cross-run stability

Across 3 temperature-0 runs, **99.2%** of snippets received the same primary theme in every run (2036 scored).

## Extracted theme mix by persona

- **Mid-market RevOps Leader**: manual_work_reduction (223), pipeline_attribution (110), data_quality (86)
- **VP Sales at growth-stage SaaS**: rep_efficiency (149), forecasting_accuracy (103), pipeline_attribution (88)
- **Enterprise IT Buyer**: compliance_security (203), tool_sprawl_consolidation (137), data_quality (87)
- **SMB Founder**: onboarding_ramp (150), rep_efficiency (141), manual_work_reduction (72)
