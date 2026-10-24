# cerebras_qwen-3-8-27b_agentic_fx_r1

Queries: 36/36 · accuracy 91.7 % (95 % Wilson 78.2–97.1) · F1 0.944 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | (none) |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| T29 | es | multi | Con el clima de esta semana, calcula el riego y busca en el INIA recomendaciones de riego deficitario en vid. | calculate_irrigation_plan, get_climate_data, search_inia_biblioteca | (none) |
