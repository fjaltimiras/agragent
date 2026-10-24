# cerebras_gpt-oss-120b_planned

Queries: 126/126 · accuracy 86.5 % (95 % Wilson 79.5–91.4) · F1 0.929 · abstention 16/16

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q21 | en | fertilization | How should I split nitrogen applications for a 10 t/ha wheat crop? | calculate_fertilization_plan | (none) |
| Q27 | es | literature_inia | Recupera las dosis de riego recomendadas por el INIA para arándanos, con cifras. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q35 | en | multi | Interpret my soil analysis (pH 5.5, P 10 ppm, K 0.12 cmol/kg) and then propose a fertilization plan for a 20 t/ha grape target. | analyze_soil_report, calculate_fertilization_plan | calculate_fertilization_plan |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q49 | pt | soil | Interprete esta análise de solo: pH 5,4, MO 1,5%, P 9 ppm, K 0,18 cmol/kg. | analyze_soil_report | (none) |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q69 | en | satellite | Show me how the NDVI of my field has changed over the past month. | get_ndvi_data | (none) |
| Q72 | pt | satellite | Qual o NDWI atual do meu talhão e isso indica estresse hídrico? | get_ndvi_data | (none) |
| Q73 | es | satellite | Compara el NDVI actual de mi viñedo con el de hace dos semanas. | get_ndvi_data | (none) |
| Q77 | pt | soil | Meu solo tem pH 4,8 e saturação por alumínio de 25 %. Isso é um problema para a videira? | analyze_soil_report | (none) |
| Q78 | pt | soil | A análise de solo deu boro 0,2 ppm, zinco 0,4 ppm e ferro 12 ppm. Há alguma deficiência de micronutrientes que eu deva corrigir? | analyze_soil_report | (none) |
| Q79 | es | soil | ¿Qué implica una conductividad eléctrica de 3.5 dS/m en el suelo de mi viñedo? | analyze_soil_report | (none) |
| Q93 | en | fertilization | How should I split the nitrogen dose across the season for my vineyard? | calculate_fertilization_plan | (none) |
| Q112 | en | multi | Give me this week's weather and my field's current NDVI, then tell me whether to irrigate. | calculate_irrigation_plan, get_climate_data, get_ndvi_data | get_climate_data, get_ndvi_data |
| Q113 | es | multi | Interpreta mi análisis foliar (N 1.7 %, K 0.8 %) y calcula el plan de fertilización para una meta de 18 t/ha. | analyze_foliar_report, calculate_fertilization_plan | analyze_foliar_report |
