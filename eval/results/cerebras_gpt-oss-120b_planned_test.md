# cerebras_gpt-oss-120b_planned_test

Queries: 36/36 · accuracy 91.7 % (95 % Wilson 78.2–97.1) · F1 0.955 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T09 | pt | soil | O que indica uma saturação por bases de 38% e alumínio de 0,9 cmol/dm³ no meu solo? | analyze_soil_report | (none) |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | (none) |
| T29 | es | multi | Con el clima de esta semana, calcula el riego y busca en el INIA recomendaciones de riego deficitario en vid. | calculate_irrigation_plan, get_climate_data, search_inia_biblioteca | get_climate_data, search_inia_biblioteca |
