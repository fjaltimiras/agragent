# Agent tool-selection cases

Total queries: 63 | successes: 46 | failures: 17


## Representative success cases

| ID | Lang | Category | Query | Expected | Selected |
|----|------|----------|-------|----------|----------|
| Q01 | en | climate | What is the weather forecast for my field this week? | get_climate_data | get_climate_data |
| Q05 | en | satellite | Show me the current NDVI of my field. | get_ndvi_data | get_ndvi_data |
| Q09 | en | soil | Here is my soil analysis: pH 5.8, EC 0.4 dS/m, organic matter 1.2%, P 8 ppm, K 0.15 cmol/kg. Please interpret it. | analyze_soil_report | analyze_soil_report |
| Q12 | en | foliar | My leaf tissue analysis shows N 1.8%, K 0.6%, Mg 0.18%. Are there any deficiencies? | analyze_foliar_report | analyze_foliar_report |
| Q16 | es | irrigation | Calcula un plan de riego para mi viñedo en veraison, suelo franco, riego por goteo. | calculate_irrigation_plan, get_climate_data | calculate_irrigation_plan |
| Q19 | en | fertilization | Give me an NPK fertilization plan for a 12 t/ha potato yield target. | calculate_fertilization_plan | calculate_fertilization_plan |
| Q24 | en | literature_openalex | Find peer-reviewed studies reporting YOLO-based grape cluster detection accuracy. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | search_openalex |
| Q27 | es | literature_inia | Recupera las dosis de riego recomendadas por el INIA para arándanos, con cifras. | search_inia_rag, search_inia_biblioteca | search_inia_rag |
| Q28 | en | literature_agris | Search the FAO AGRIS database for literature on integrated pest management in vineyards. | search_agris, search_openalex | search_agris |
| Q30 | en | faostat | What was Chile's grape production and yield over the last 10 years? | get_faostat_data | get_faostat_data |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | calculate_irrigation_plan, get_ndvi_data |
| Q38 | en | out_of_scope | Hello, who are you and what can you do? | (abstain) | (none) |

## Failure cases (all)

| ID | Lang | Category | Query | Expected | Selected | Issue |
|----|------|----------|-------|----------|----------|-------|
| Q04 | en | climate | Show me the reference evapotranspiration forecast for my coordinates. | get_climate_data | (none) | missing coverage |
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q18 | es | irrigation | Mi cultivo de papa está en mid-season, suelo arcilloso, aspersión. ¿Cuánto regar? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q21 | en | fertilization | How should I split nitrogen applications for a 10 t/ha wheat crop? | calculate_fertilization_plan | (none) | missing coverage |
| Q22 | en | literature_openalex | Find recent peer-reviewed scientific papers on deficit irrigation in grapevine. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q23 | es | literature_openalex | Busca estudios científicos sobre el índice NDRE y el contenido de nitrógeno en vid. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q25 | es | literature_inia | ¿Qué recomienda el INIA sobre el manejo del riego en cerezos en Chile? Dame extractos. | search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q26 | es | literature_inia | Busca boletines técnicos del INIA sobre control de oídio en vid. | search_inia_biblioteca, search_inia_rag | (none) | missing coverage |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q37 | en | multi | Compare my grape yield potential against national FAO statistics and find papers on improving vineyard yield. | get_faostat_data, search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q52 | pt | foliar | Tenho clorose nas folhas. Foliar: Fe 28 ppm, Mn 22 ppm, N 2,4%. O que devo corrigir? | analyze_foliar_report | (none) | missing coverage |
| Q53 | pt | irrigation | Quanto devo irrigar meu vinhedo de 5 ha por gotejamento nesta semana? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q54 | pt | fertilization | Elabore um plano de adubação NPK para uma meta de 15 t/ha de uva. | calculate_fertilization_plan | (none) | missing coverage |
| Q55 | pt | fertilization | Como fracionar a aplicação de nitrogênio para uma lavoura de milho de 10 t/ha? | calculate_fertilization_plan | (none) | missing coverage |
| Q56 | pt | literature_openalex | Encontre artigos científicos recentes sobre irrigação com déficit em videira. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q61 | pt | multi | Interprete minha análise de solo (pH 5,3, P 11 ppm, K 0,14 cmol/kg) e proponha um plano de adubação para meta de 20 t/ha de uva. | analyze_soil_report, calculate_fertilization_plan | (none) | missing coverage |
