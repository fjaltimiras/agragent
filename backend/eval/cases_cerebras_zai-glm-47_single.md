# Agent tool-selection cases

Total queries: 63 | successes: 49 | failures: 14


## Representative success cases

| ID | Lang | Category | Query | Expected | Selected |
|----|------|----------|-------|----------|----------|
| Q01 | en | climate | What is the weather forecast for my field this week? | get_climate_data | get_climate_data |
| Q05 | en | satellite | Show me the current NDVI of my field. | get_ndvi_data | get_ndvi_data |
| Q09 | en | soil | Here is my soil analysis: pH 5.8, EC 0.4 dS/m, organic matter 1.2%, P 8 ppm, K 0.15 cmol/kg. Please interpret it. | analyze_soil_report | analyze_soil_report |
| Q12 | en | foliar | My leaf tissue analysis shows N 1.8%, K 0.6%, Mg 0.18%. Are there any deficiencies? | analyze_foliar_report | analyze_foliar_report |
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | calculate_irrigation_plan, get_climate_data |
| Q20 | es | fertilization | Plan de fertilización para uva de mesa, objetivo 25 t/ha. | calculate_fertilization_plan | calculate_fertilization_plan |
| Q22 | en | literature_openalex | Find recent peer-reviewed scientific papers on deficit irrigation in grapevine. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | search_openalex |
| Q25 | es | literature_inia | ¿Qué recomienda el INIA sobre el manejo del riego en cerezos en Chile? Dame extractos. | search_inia_rag, search_inia_biblioteca | search_inia_rag |
| Q28 | en | literature_agris | Search the FAO AGRIS database for literature on integrated pest management in vineyards. | search_agris, search_openalex | search_agris |
| Q30 | en | faostat | What was Chile's grape production and yield over the last 10 years? | get_faostat_data | get_faostat_data |
| Q35 | en | multi | Interpret my soil analysis (pH 5.5, P 10 ppm, K 0.12 cmol/kg) and then propose a fertilization plan for a 20 t/ha grape target. | analyze_soil_report, calculate_fertilization_plan | analyze_soil_report, calculate_fertilization_plan |
| Q38 | en | out_of_scope | Hello, who are you and what can you do? | (abstain) | (none) |

## Failure cases (all)

| ID | Lang | Category | Query | Expected | Selected | Issue |
|----|------|----------|-------|----------|----------|-------|
| Q08 | es | satellite | ¿Hay zonas de bajo vigor en mi parcela este mes según las imágenes Sentinel-2? | get_ndvi_data | (none) | missing coverage |
| Q16 | es | irrigation | Calcula un plan de riego para mi viñedo en veraison, suelo franco, riego por goteo. | calculate_irrigation_plan, get_climate_data | get_climate_data | missing coverage |
| Q17 | pt | irrigation | Quanto devo irrigar minha lavoura de milho na fase de meio de estação? | calculate_irrigation_plan, get_climate_data | get_climate_data | missing coverage |
| Q18 | es | irrigation | Mi cultivo de papa está en mid-season, suelo arcilloso, aspersión. ¿Cuánto regar? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q19 | en | fertilization | Give me an NPK fertilization plan for a 12 t/ha potato yield target. | calculate_fertilization_plan | (none) | missing coverage |
| Q21 | en | fertilization | How should I split nitrogen applications for a 10 t/ha wheat crop? | calculate_fertilization_plan | search_inia_rag | missing coverage |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data | missing coverage |
| Q34 | en | multi | Check the weather and then give me an irrigation plan for my drip-irrigated vineyard. | get_climate_data, calculate_irrigation_plan | get_climate_data | missing coverage |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | search_inia_rag, search_openalex | missing coverage |
| Q47 | pt | satellite | Mostre o NDVI atual da minha parcela. | get_ndvi_data | (none) | missing coverage |
| Q53 | pt | irrigation | Quanto devo irrigar meu vinhedo de 5 ha por gotejamento nesta semana? | calculate_irrigation_plan, get_climate_data | get_climate_data | missing coverage |
| Q54 | pt | fertilization | Elabore um plano de adubação NPK para uma meta de 15 t/ha de uva. | calculate_fertilization_plan | calculate_fertilization_plan, search_inia_rag | extraneous tool |
| Q55 | pt | fertilization | Como fracionar a aplicação de nitrogênio para uma lavoura de milho de 10 t/ha? | calculate_fertilization_plan | calculate_fertilization_plan, search_inia_biblioteca, search_openalex | extraneous tool |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data | missing coverage |
