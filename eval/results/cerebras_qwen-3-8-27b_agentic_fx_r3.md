# cerebras_qwen-3-8-27b_agentic_fx_r3

Queries: 36/36 · accuracy 83.3 % (95 % Wilson 68.1–92.1) · F1 0.890 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T08 | es | soil | Tengo un análisis de suelo con sodio intercambiable de 9% y CE 2,8 dS/m. ¿Es un problema? | analyze_soil_report | (none) |
| T16 | en | fertilization | What nitrogen rate should I apply for a 25 t/ha table-grape target? | calculate_fertilization_plan | calculate_fertilization_plan, search_inia_biblioteca |
| T17 | es | fertilization | Arma un programa de fertilización de potasio para cerezos con meta de 14 t/ha. | calculate_fertilization_plan | (none) |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | (none) |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_agris, search_inia_biblioteca, search_openalex |
| T30 | pt | multi | Interprete a análise foliar (N 1,7%, K 0,8%) e monte um plano de adubação para 18 t/ha de uva. | analyze_foliar_report, calculate_fertilization_plan | (none) |
