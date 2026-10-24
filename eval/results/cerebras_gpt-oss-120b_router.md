# cerebras_gpt-oss-120b_router

Queries: 126/126 · accuracy 97.6 % (95 % Wilson 93.2–99.2) · F1 0.988 · abstention 16/16

## Failures

| ID | Lang | Category | Query | Expected | Selected |
|---|---|---|---|---|---|
| Q33 | en | multi | What is my field's current NDVI, and based on the weather should I irrigate this week? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q60 | pt | multi | Qual é o NDVI atual do meu campo e, considerando o clima, devo irrigar esta semana? | get_ndvi_data, calculate_irrigation_plan, get_climate_data | get_climate_data, get_ndvi_data |
| Q112 | en | multi | Give me this week's weather and my field's current NDVI, then tell me whether to irrigate. | calculate_irrigation_plan, get_climate_data, get_ndvi_data | get_climate_data, get_ndvi_data |
