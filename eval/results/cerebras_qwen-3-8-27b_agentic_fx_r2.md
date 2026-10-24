# cerebras_qwen-3-8-27b_agentic_fx_r2

Queries: 36/36 · accuracy 86.1 % (95 % Wilson 71.3–93.9) · F1 0.932 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T06 | pt | satellite | Mostre a evolução do NDVI do meu talhão nos últimos três meses. | get_ndvi_data | (none) |
| T08 | es | soil | Tengo un análisis de suelo con sodio intercambiable de 9% y CE 2,8 dS/m. ¿Es un problema? | analyze_soil_report | analyze_soil_report, search_inia_biblioteca |
| T15 | pt | irrigation | Preciso de um plano de irrigação para as próximas duas semanas no meu vinhedo. | calculate_irrigation_plan, get_climate_data | (none) |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | (none) |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_agris, search_inia_biblioteca |
