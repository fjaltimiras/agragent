# cerebras_gpt-oss-120b_planned_fx_r2

Queries: 36/36 · accuracy 88.9 % (95 % Wilson 74.7–95.6) · F1 0.931 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T11 | es | foliar | Mi análisis de hojas dio Mg 0,15% y Mn 18 ppm en uva de mesa. ¿Están bajos? | analyze_foliar_report | analyze_foliar_report, search_openalex |
| T14 | es | irrigation | Calcula la lámina de riego semanal para mi viñedo en esta etapa. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | analyze_soil_report |
| T30 | pt | multi | Interprete a análise foliar (N 1,7%, K 0,8%) e monte um plano de adubação para 18 t/ha de uva. | analyze_foliar_report, calculate_fertilization_plan | calculate_fertilization_plan |
