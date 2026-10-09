# Agent tool-selection cases

Total queries: 5 | successes: 1 | failures: 4


## Representative success cases

| ID | Lang | Category | Query | Expected | Selected |
|----|------|----------|-------|----------|----------|
| Q03 | pt | climate | Qual é a previsão de chuva para os próximos 7 dias no meu campo? | get_climate_data | get_climate_data |

## Failure cases (all)

| ID | Lang | Category | Query | Expected | Selected | Issue |
|----|------|----------|-------|----------|----------|-------|
| Q01 | en | climate | What is the weather forecast for my field this week? | get_climate_data | (none) | missing coverage |
| Q02 | es | climate | ¿Va a helar en los próximos días en mi viñedo? | get_climate_data | (none) | missing coverage |
| Q04 | en | climate | Show me the reference evapotranspiration forecast for my coordinates. | get_climate_data | (none) | missing coverage |
| Q05 | en | satellite | Show me the current NDVI of my field. | get_ndvi_data | (none) | missing coverage |
