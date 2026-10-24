# cerebras_qwen-3-8-27b_planned_fx_r3

Queries: 36/36 · accuracy 94.4 % (95 % Wilson 81.9–98.5) · F1 0.963 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T11 | es | foliar | Mi análisis de hojas dio Mg 0,15% y Mn 18 ppm en uva de mesa. ¿Están bajos? | analyze_foliar_report | analyze_foliar_report, search_inia_biblioteca |
| T25 | en | literature_inia | Look up INIA Chile bulletins on pruning systems for table grapes. | search_inia_biblioteca | search_agris, search_inia_biblioteca, search_openalex |
