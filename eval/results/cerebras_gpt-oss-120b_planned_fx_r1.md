# cerebras_gpt-oss-120b_planned_fx_r1

Queries: 36/36 · accuracy 86.1 % (95 % Wilson 71.3–93.9) · F1 0.898 · abstention 5/5

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| T09 | pt | soil | O que indica uma saturação por bases de 38% e alumínio de 0,9 cmol/dm³ no meu solo? | analyze_soil_report | (none) |
| T13 | en | irrigation | How many hours should I run my drip lines next week to cover the crop water demand? | calculate_irrigation_plan, get_climate_data | get_climate_data |
| T14 | es | irrigation | Calcula la lámina de riego semanal para mi viñedo en esta etapa. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| T17 | es | fertilization | Arma un programa de fertilización de potasio para cerezos con meta de 14 t/ha. | calculate_fertilization_plan | analyze_soil_report |
| T18 | pt | fertilization | Quanto de fósforo e potássio devo aplicar para soja com meta de 4 t/ha? | calculate_fertilization_plan | analyze_soil_report |
