# Agent tool-selection cases

Total queries: 63 | successes: 8 | failures: 55


## Representative success cases

| ID | Lang | Category | Query | Expected | Selected |
|----|------|----------|-------|----------|----------|
| Q38 | en | out_of_scope | Hello, who are you and what can you do? | (abstain) | (none) |

## Failure cases (all)

| ID | Lang | Category | Query | Expected | Selected | Issue |
|----|------|----------|-------|----------|----------|-------|
| Q01 | en | climate | What is the weather forecast for my field this week? | get_climate_data | (none) | missing coverage |
| Q02 | es | climate | ¿Va a helar en los próximos días en mi viñedo? | get_climate_data | (none) | missing coverage |
| Q03 | pt | climate | Qual é a previsão de chuva para os próximos 7 dias no meu campo? | get_climate_data | (none) | missing coverage |
| Q04 | en | climate | Show me the reference evapotranspiration forecast for my coordinates. | get_climate_data | (none) | missing coverage |
| Q05 | en | satellite | Show me the current NDVI of my field. | get_ndvi_data | (none) | missing coverage |
| Q06 | es | satellite | ¿Cómo está el vigor vegetativo de mi parcela según el satélite? | get_ndvi_data | (none) | missing coverage |
| Q07 | en | satellite | What is the average NDVI over my field for the last month? | get_ndvi_data | (none) | missing coverage |
| Q08 | es | satellite | ¿Hay zonas de bajo vigor en mi parcela este mes según las imágenes Sentinel-2? | get_ndvi_data | (none) | missing coverage |
| Q09 | en | soil | Here is my soil analysis: pH 5.8, EC 0.4 dS/m, organic matter 1.2%, P 8 ppm, K 0.15 cmol/kg. Please interpret it. | analyze_soil_report | (none) | missing coverage |
| Q10 | es | soil | Interpreta este análisis de suelo: pH 7.9, CE 2.1 dS/m, materia orgánica 0.8%, P 45 ppm, K 0.6 cmol/kg. | analyze_soil_report | (none) | missing coverage |
| Q11 | en | soil | Interpret soil: pH 6.2, OM 3.5%, N 0.2%, P 25 ppm, K 0.4, Ca 8, Mg 2 cmol/kg. | analyze_soil_report | (none) | missing coverage |
| Q12 | en | foliar | My leaf tissue analysis shows N 1.8%, K 0.6%, Mg 0.18%. Are there any deficiencies? | analyze_foliar_report | (none) | missing coverage |
| Q13 | es | foliar | Analiza este foliar: N 2.2%, P 0.25%, K 1.1%, Fe 45 ppm, Zn 12 ppm. | analyze_foliar_report | (none) | missing coverage |
| Q14 | es | foliar | Tengo clorosis férrica visible. Aquí va el foliar: Fe 30 ppm, Mn 25 ppm, N 2.5%. ¿Qué corrijo? | analyze_foliar_report | (none) | missing coverage |
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q16 | es | irrigation | Calcula un plan de riego para mi viñedo en veraison, suelo franco, riego por goteo. | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q17 | pt | irrigation | Quanto devo irrigar minha lavoura de milho na fase de meio de estação? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q18 | es | irrigation | Mi cultivo de papa está en mid-season, suelo arcilloso, aspersión. ¿Cuánto regar? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q19 | en | fertilization | Give me an NPK fertilization plan for a 12 t/ha potato yield target. | calculate_fertilization_plan | (none) | missing coverage |
| Q20 | es | fertilization | Plan de fertilización para uva de mesa, objetivo 25 t/ha. | calculate_fertilization_plan | (none) | missing coverage |
| Q21 | en | fertilization | How should I split nitrogen applications for a 10 t/ha wheat crop? | calculate_fertilization_plan | (none) | missing coverage |
| Q22 | en | literature_openalex | Find recent peer-reviewed scientific papers on deficit irrigation in grapevine. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q23 | es | literature_openalex | Busca estudios científicos sobre el índice NDRE y el contenido de nitrógeno en vid. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q24 | en | literature_openalex | Find peer-reviewed studies reporting YOLO-based grape cluster detection accuracy. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q25 | es | literature_inia | ¿Qué recomienda el INIA sobre el manejo del riego en cerezos en Chile? Dame extractos. | search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q26 | es | literature_inia | Busca boletines técnicos del INIA sobre control de oídio en vid. | search_inia_biblioteca, search_inia_rag | (none) | missing coverage |
| Q27 | es | literature_inia | Recupera las dosis de riego recomendadas por el INIA para arándanos, con cifras. | search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q28 | en | literature_agris | Search the FAO AGRIS database for literature on integrated pest management in vineyards. | search_agris, search_openalex | (none) | missing coverage |
| Q29 | es | literature_agris | Busca en AGRIS de la FAO publicaciones sobre fertilización nitrogenada en maíz. | search_agris, search_openalex | (none) | missing coverage |
| Q30 | en | faostat | What was Chile's grape production and yield over the last 10 years? | get_faostat_data | (none) | missing coverage |
| Q31 | es | faostat | ¿Cuál es la superficie cosechada de maíz en Brasil según la FAO? | get_faostat_data | (none) | missing coverage |
| Q32 | en | faostat | Give me wheat yield trends in Argentina from FAO statistics. | get_faostat_data | (none) | missing coverage |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q34 | en | multi | Check the weather and then give me an irrigation plan for my drip-irrigated vineyard. | get_climate_data, calculate_irrigation_plan | (none) | missing coverage |
| Q35 | en | multi | Interpret my soil analysis (pH 5.5, P 10 ppm, K 0.12 cmol/kg) and then propose a fertilization plan for a 20 t/ha grape target. | analyze_soil_report, calculate_fertilization_plan | (none) | missing coverage |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q37 | en | multi | Compare my grape yield potential against national FAO statistics and find papers on improving vineyard yield. | get_faostat_data, search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q44 | es | fertilization | Mi suelo tiene fósforo alto (50 ppm). Ajusta el plan de fertilización para tomate con objetivo 80 t/ha. | calculate_fertilization_plan, analyze_soil_report | (none) | missing coverage |
| Q45 | en | literature_inia | Search the INIA Chile digital library for documents about cover crops in vineyards. | search_inia_biblioteca, search_inia_rag | (none) | missing coverage |
| Q46 | pt | climate | Qual é a previsão de geada para o meu vinhedo nos próximos dias? | get_climate_data | (none) | missing coverage |
| Q47 | pt | satellite | Mostre o NDVI atual da minha parcela. | get_ndvi_data | (none) | missing coverage |
| Q48 | pt | satellite | Existem zonas de baixo vigor no meu talhão segundo as imagens Sentinel-2 deste mês? | get_ndvi_data | (none) | missing coverage |
| Q49 | pt | soil | Interprete esta análise de solo: pH 5,4, MO 1,5%, P 9 ppm, K 0,18 cmol/kg. | analyze_soil_report | (none) | missing coverage |
| Q50 | pt | soil | Minha análise de solo deu pH 7,8 e CE 2,3 dS/m. O que isso significa para a minha cultura? | analyze_soil_report | (none) | missing coverage |
| Q51 | pt | foliar | Análise foliar: N 1,9%, K 0,7%, Mg 0,15%. Há deficiências? | analyze_foliar_report | (none) | missing coverage |
| Q52 | pt | foliar | Tenho clorose nas folhas. Foliar: Fe 28 ppm, Mn 22 ppm, N 2,4%. O que devo corrigir? | analyze_foliar_report | (none) | missing coverage |
| Q53 | pt | irrigation | Quanto devo irrigar meu vinhedo de 5 ha por gotejamento nesta semana? | calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q54 | pt | fertilization | Elabore um plano de adubação NPK para uma meta de 15 t/ha de uva. | calculate_fertilization_plan | (none) | missing coverage |
| Q55 | pt | fertilization | Como fracionar a aplicação de nitrogênio para uma lavoura de milho de 10 t/ha? | calculate_fertilization_plan | (none) | missing coverage |
| Q56 | pt | literature_openalex | Encontre artigos científicos recentes sobre irrigação com déficit em videira. | search_openalex, search_agris, search_inia_rag, search_inia_biblioteca | (none) | missing coverage |
| Q57 | pt | literature_agris | Busque na base AGRIS da FAO publicações sobre manejo integrado de pragas em vinhedos. | search_agris, search_openalex | (none) | missing coverage |
| Q58 | pt | faostat | Qual foi a produção e o rendimento de uva no Brasil nos últimos 10 anos segundo a FAO? | get_faostat_data | (none) | missing coverage |
| Q59 | pt | faostat | Mostre a tendência de rendimento de soja na Argentina pelas estatísticas da FAO. | get_faostat_data | (none) | missing coverage |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | (none) | missing coverage |
| Q61 | pt | multi | Interprete minha análise de solo (pH 5,3, P 11 ppm, K 0,14 cmol/kg) e proponha um plano de adubação para meta de 20 t/ha de uva. | analyze_soil_report, calculate_fertilization_plan | (none) | missing coverage |
