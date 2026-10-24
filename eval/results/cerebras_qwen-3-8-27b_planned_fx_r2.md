# cerebras_qwen-3-8-27b_planned_fx_r2

Queries: 36/36 · accuracy 94.4 % (95 % Wilson 81.9–98.5) · F1 0.963 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | calculate_fertilization_plan, search_inia_biblioteca, search_openalex |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_agris, search_inia_biblioteca |
