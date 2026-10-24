# cerebras_qwen-3-8-27b_planned_fx_r1

Queries: 36/36 · accuracy 94.4 % (95 % Wilson 81.9–98.5) · F1 0.973 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T13 | en | irrigation | How many hours should I run my drip lines next week to cover the crop water demand? | calculate_irrigation_plan, get_climate_data | (none) |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
