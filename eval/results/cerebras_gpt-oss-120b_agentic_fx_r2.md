# cerebras_gpt-oss-120b_agentic_fx_r2

Queries: 36/36 · accuracy 66.7 % (95 % Wilson 50.3–79.8) · F1 0.791 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T05 | es | satellite | ¿Qué índice de vegetación tiene hoy mi parcela y está dentro de lo normal para esta época? | get_ndvi_data | get_ndvi_data, search_openalex |
| T07 | en | soil | My soil test says pH 8.1, organic matter 0.9%, P Olsen 6 ppm and K 120 ppm. What does it mean? | analyze_soil_report | (none) |
| T08 | es | soil | Tengo un análisis de suelo con sodio intercambiable de 9% y CE 2,8 dS/m. ¿Es un problema? | analyze_soil_report | (none) |
| T09 | pt | soil | O que indica uma saturação por bases de 38% e alumínio de 0,9 cmol/dm³ no meu solo? | analyze_soil_report | (none) |
| T11 | es | foliar | Mi análisis de hojas dio Mg 0,15% y Mn 18 ppm en uva de mesa. ¿Están bajos? | analyze_foliar_report | (none) |
| T13 | en | irrigation | How many hours should I run my drip lines next week to cover the crop water demand? | calculate_irrigation_plan, get_climate_data | (none) |
| T15 | pt | irrigation | Preciso de um plano de irrigação para as próximas duas semanas no meu vinhedo. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| T16 | en | fertilization | What nitrogen rate should I apply for a 25 t/ha table-grape target? | calculate_fertilization_plan | (none) |
| T17 | es | fertilization | Arma un programa de fertilización de potasio para cerezos con meta de 14 t/ha. | calculate_fertilization_plan | (none) |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | (none) |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| T30 | pt | multi | Interprete a análise foliar (N 1,7%, K 0,8%) e monte um plano de adubação para 18 t/ha de uva. | analyze_foliar_report, calculate_fertilization_plan | (none) |
