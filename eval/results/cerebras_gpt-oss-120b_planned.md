# cerebras_gpt-oss-120b_planned

Queries: 126/126 · accuracy 91.3 % (95 % Wilson 85.0–95.1) · F1 0.957 · abstention 16/16

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_biblioteca | search_openalex |
| Q52 | pt | foliar | Tenho clorose nas folhas. Foliar: Fe 28 ppm, Mn 22 ppm, N 2,4%. O que devo corrigir? | analyze_foliar_report | analyze_foliar_report, search_openalex |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q61 | pt | multi | Interprete minha análise de solo (pH 5,3, P 11 ppm, K 0,14 cmol/kg) e proponha um plano de adubação para meta de 20 t/ha de uva. | analyze_soil_report, calculate_fertilization_plan | calculate_fertilization_plan |
| Q77 | pt | soil | Meu solo tem pH 4,8 e saturação por alumínio de 25 %. Isso é um problema para a videira? | analyze_soil_report | (none) |
| Q82 | pt | foliar | Minha análise foliar mostra boro em 22 ppm e zinco em 15 ppm. Está adequado? | analyze_foliar_report | analyze_foliar_report, search_openalex |
| Q93 | en | fertilization | How should I split the nitrogen dose across the season for my vineyard? | calculate_fertilization_plan | (none) |
| Q96 | en | faostat | What was Chile's wine grape production over the last five years? | get_faostat_data | get_faostat_data, search_openalex |
| Q99 | en | faostat | Compare wheat yields between Chile and France using FAO statistics. | get_faostat_data | get_faostat_data, search_openalex |
| Q112 | en | multi | Give me this week's weather and my field's current NDVI, then tell me whether to irrigate. | calculate_irrigation_plan, get_climate_data, get_ndvi_data | get_climate_data, get_ndvi_data |
