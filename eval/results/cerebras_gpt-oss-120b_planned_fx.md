# cerebras_gpt-oss-120b_planned_fx

Queries: 126/126 · accuracy 92.1 % (95 % Wilson 86.0–95.6) · F1 0.957 · abstention 16/16

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| Q15 | en | irrigation | How much should I irrigate my 5 ha drip-irrigated tomato field this week? | calculate_irrigation_plan, get_climate_data | get_climate_data |
| Q25 | es | literature_inia | ¿Qué recomienda el INIA sobre el manejo del riego en cerezos en Chile? Dame extractos. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q27 | es | literature_inia | Recupera las dosis de riego recomendadas por el INIA para arándanos, con cifras. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q36 | es | multi | Analiza mi suelo (pH 5.0, baja materia orgánica) y dime qué publicaciones científicas hay sobre enmiendas calcáreas. | analyze_soil_report, search_openalex, search_agris, search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q61 | pt | multi | Interprete minha análise de solo (pH 5,3, P 11 ppm, K 0,14 cmol/kg) e proponha um plano de adubação para meta de 20 t/ha de uva. | analyze_soil_report, calculate_fertilization_plan | calculate_fertilization_plan |
| Q94 | es | fertilization | Calcula la fertilización NPK para cebolla con una meta de 45 t/ha. | calculate_fertilization_plan | analyze_soil_report |
| Q105 | es | literature_inia | ¿Qué recomienda el INIA sobre la fertilización nitrogenada en vid de mesa? Dame extractos. | search_inia_biblioteca | search_inia_biblioteca, search_openalex |
| Q112 | en | multi | Give me this week's weather and my field's current NDVI, then tell me whether to irrigate. | calculate_irrigation_plan, get_climate_data, get_ndvi_data | get_climate_data, get_ndvi_data |
