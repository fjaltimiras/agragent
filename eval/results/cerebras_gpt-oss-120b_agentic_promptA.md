# cerebras_gpt-oss-120b_agentic_promptA

Queries: 126/126 · accuracy 57.1 % (95 % Wilson 48.4–65.4) · F1 0.698 · abstention 16/16

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| Q07 | en | satellite | What is the average NDVI over my field for the last month? | get_ndvi_data | (none) |
| Q09 | en | soil | Here is my soil analysis: pH 5.8, EC 0.4 dS/m, organic matter 1.2%, P 8 ppm, K 0.15 cmol/kg. Please interpret it. | analyze_soil_report | (none) |
| Q10 | es | soil | Interpreta este análisis de suelo: pH 7.9, CE 2.1 dS/m, materia orgánica 0.8%, P 45 ppm, K 0.6 cmol/kg. | analyze_soil_report | (none) |
| Q11 | en | soil | Interpret soil: pH 6.2, OM 3.5%, N 0.2%, P 25 ppm, K 0.4, Ca 8, Mg 2 cmol/kg. | analyze_soil_report | (none) |
| Q12 | en | foliar | My leaf tissue analysis shows N 1.8%, K 0.6%, Mg 0.18%. Are there any deficiencies? | analyze_foliar_report | (none) |
| Q13 | es | foliar | Analiza este foliar: N 2.2%, P 0.25%, K 1.1%, Fe 45 ppm, Zn 12 ppm. | analyze_foliar_report | (none) |
| Q14 | es | foliar | Tengo clorosis férrica visible. Aquí va el foliar: Fe 30 ppm, Mn 25 ppm, N 2.5%. ¿Qué corrijo? | analyze_foliar_report | (none) |
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | (none) |
| Q16 | es | irrigation | Calcula un plan de riego para mi viñedo en veraison, suelo franco, riego por goteo. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q17 | pt | irrigation | Quanto devo irrigar minha lavoura de milho na fase de meio de estação? | calculate_irrigation_plan, get_climate_data | (none) |
| Q18 | es | irrigation | Mi cultivo de papa está en mid-season, suelo arcilloso, aspersión. ¿Cuánto regar? | calculate_irrigation_plan, get_climate_data | (none) |
| Q19 | en | fertilization | Give me an NPK fertilization plan for a 12 t/ha potato yield target. | calculate_fertilization_plan | (none) |
| Q21 | en | fertilization | How should I split nitrogen applications for a 10 t/ha wheat crop? | calculate_fertilization_plan | (none) |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q35 | en | multi | Interpret my soil analysis (pH 5.5, P 10 ppm, K 0.12 cmol/kg) and then propose a fertilization plan for a 20 t/ha grape target. | analyze_soil_report, calculate_fertilization_plan | (none) |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q44 | es | fertilization | Mi suelo tiene fósforo alto (50 ppm). Ajusta el plan de fertilización para tomate con objetivo 80 t/ha. | calculate_fertilization_plan, analyze_soil_report | (none) |
| Q49 | pt | soil | Interprete esta análise de solo: pH 5,4, MO 1,5%, P 9 ppm, K 0,18 cmol/kg. | analyze_soil_report | (none) |
| Q50 | pt | soil | Minha análise de solo deu pH 7,8 e CE 2,3 dS/m. O que isso significa para a minha cultura? | analyze_soil_report | (none) |
| Q51 | pt | foliar | Análise foliar: N 1,9%, K 0,7%, Mg 0,15%. Há deficiências? | analyze_foliar_report | (none) |
| Q52 | pt | foliar | Tenho clorose nas folhas. Foliar: Fe 28 ppm, Mn 22 ppm, N 2,4%. O que devo corrigir? | analyze_foliar_report | (none) |
| Q53 | pt | irrigation | Quanto devo irrigar meu vinhedo de 5 ha por gotejamento nesta semana? | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q54 | pt | fertilization | Elabore um plano de adubação NPK para uma meta de 15 t/ha de uva. | calculate_fertilization_plan | (none) |
| Q55 | pt | fertilization | Como fracionar a aplicação de nitrogênio para uma lavoura de milho de 10 t/ha? | calculate_fertilization_plan | (none) |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q61 | pt | multi | Interprete minha análise de solo (pH 5,3, P 11 ppm, K 0,14 cmol/kg) e proponha um plano de adubação para meta de 20 t/ha de uva. | analyze_soil_report, calculate_fertilization_plan | calculate_fertilization_plan |
| Q69 | en | satellite | Show me how the NDVI of my field has changed over the past month. | get_ndvi_data | (none) |
| Q71 | pt | satellite | Qual o índice SAVI atual da minha área segundo o Sentinel-2? | get_ndvi_data | (none) |
| Q72 | pt | satellite | Qual o NDWI atual do meu talhão e isso indica estresse hídrico? | get_ndvi_data | (none) |
| Q73 | es | satellite | Compara el NDVI actual de mi viñedo con el de hace dos semanas. | get_ndvi_data | (none) |
| Q75 | en | soil | My soil test reads pH 7.8, EC 2.4 dS/m and 1.1 % organic matter. What does that mean for grapevine? | analyze_soil_report | (none) |
| Q76 | es | soil | Interpreta este análisis de suelo: pH 6.2, MO 2.8 %, P Olsen 22 ppm, K 0.45 cmol/kg, Ca 8.1 cmol/kg, Mg 1.9 cmol/kg. | analyze_soil_report | (none) |
| Q77 | pt | soil | Meu solo tem pH 4,8 e saturação por alumínio de 25 %. Isso é um problema para a videira? | analyze_soil_report | (none) |
| Q78 | pt | soil | A análise de solo deu boro 0,2 ppm, zinco 0,4 ppm e ferro 12 ppm. Há alguma deficiência de micronutrientes que eu deva corrigir? | analyze_soil_report | (none) |
| Q79 | es | soil | ¿Qué implica una conductividad eléctrica de 3.5 dS/m en el suelo de mi viñedo? | analyze_soil_report | (none) |
| Q80 | en | foliar | Leaf analysis at veraison: N 1.6 %, P 0.15 %, K 0.9 %. Is my vineyard deficient? | analyze_foliar_report | (none) |
| Q81 | es | foliar | Análisis foliar: N 2.4 %, K 1.1 %, Mg 0.18 %, Ca 1.9 %. ¿Cómo lo interpreto? | analyze_foliar_report | (none) |
| Q82 | pt | foliar | Minha análise foliar mostra boro em 22 ppm e zinco em 15 ppm. Está adequado? | analyze_foliar_report | (none) |
| Q83 | pt | foliar | Minha análise de pecíolo na floração mostra potássio em 0,7 %. Devo me preocupar? | analyze_foliar_report | (none) |
| Q84 | es | foliar | ¿Un hierro foliar de 60 ppm y un manganeso de 25 ppm están en rango para vid? | analyze_foliar_report | search_inia_biblioteca, search_openalex |
| Q86 | es | irrigation | Calcula el riego para un cultivo de maíz en floración con riego por aspersión. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q88 | pt | irrigation | Elabore um calendário de irrigação para batata em meia estação, irrigação por sulcos, solo arenoso. | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q90 | en | fertilization | What NPK programme do I need for a 20 t/ha grape yield target? | calculate_fertilization_plan | (none) |
| Q91 | es | fertilization | Plan de fertilización para trigo con objetivo de 8 t/ha en un suelo con 15 ppm de fósforo. | analyze_soil_report, calculate_fertilization_plan | (none) |
| Q92 | pt | fertilization | Quanto nitrogênio preciso aplicar para uma meta de 60 t/ha de tomate? | calculate_fertilization_plan | (none) |
| Q93 | en | fertilization | How should I split the nitrogen dose across the season for my vineyard? | calculate_fertilization_plan | (none) |
| Q94 | es | fertilization | Calcula la fertilización NPK para cebolla con una meta de 45 t/ha. | calculate_fertilization_plan | (none) |
| Q95 | pt | fertilization | Qual o plano de adubação para soja com produtividade esperada de 3,5 t/ha? | calculate_fertilization_plan | (none) |
| Q96 | en | faostat | What was Chile's wine grape production over the last five years? | get_faostat_data | get_faostat_data, search_inia_biblioteca |
| Q112 | en | multi | Give me this week's weather and my field's current NDVI, then tell me whether to irrigate. | calculate_irrigation_plan, get_climate_data, get_ndvi_data | get_climate_data, get_ndvi_data |
| Q113 | es | multi | Interpreta mi análisis foliar (N 1.7 %, K 0.8 %) y calcula el plan de fertilización para una meta de 18 t/ha. | analyze_foliar_report, calculate_fertilization_plan | (none) |
| Q116 | es | multi | Dame el pronóstico del clima y un plan de fertilización nitrogenada para uva con meta de 20 t/ha. | calculate_fertilization_plan, get_climate_data | get_climate_data |
| Q117 | pt | multi | Analise meu solo (pH 5,2, P 8 ppm, K 0,15 cmol/kg) e depois calcule a irrigação para videira em meia estação. | analyze_soil_report, calculate_irrigation_plan, get_climate_data | calculate_irrigation_plan, get_climate_data |
| Q118 | es | multi | Analiza mi suelo (pH 6.0, K 0.20 cmol/kg), calcula la fertilización para 22 t/ha de uva y búscame literatura sobre potasio en vid. | analyze_soil_report, calculate_fertilization_plan, search_agris, search_inia_biblioteca, search_openalex | (none) |
