TOOLS = [
    {
        "name": "get_climate_data",
        "description": (
            "Obtiene datos climáticos actuales y pronóstico para una ubicación geográfica. "
            "Incluye temperatura máxima y mínima, precipitaciones, humedad relativa, velocidad del viento "
            "y evapotranspiración de referencia (ET0 FAO-56 Penman-Monteith). "
            "Usa esta herramienta cuando el usuario pregunte sobre condiciones climáticas, "
            "necesidades de riego o quieras contextualizar recomendaciones con el clima actual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitud decimal de la ubicación (ej: -12.046374 para Lima, Perú)"
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitud decimal de la ubicación (ej: -77.042793 para Lima, Perú)"
                },
                "days_forecast": {
                    "type": "integer",
                    "description": "Número de días de pronóstico a obtener. Por defecto 7 días.",
                    "default": 7
                }
            },
            "required": ["latitude", "longitude"]
        }
    },
    {
        "name": "get_ndvi_data",
        "description": (
            "Obtiene datos de NDVI (Índice de Vegetación de Diferencia Normalizada) y otros índices "
            "de vegetación para un campo, usando imágenes satelitales de Sentinel-2 a través de Sentinel Hub. "
            "El NDVI permite evaluar el estado y vigor del cultivo: valores cercanos a 1.0 indican vegetación "
            "densa y saludable, valores bajos (<0.3) indican estrés, suelo desnudo o cultivo incipiente. "
            "Usa esta herramienta cuando el usuario quiera saber el estado de su cultivo desde el satélite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitud decimal del centro del campo"
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitud decimal del centro del campo"
                },
                "radius_m": {
                    "type": "number",
                    "description": "Radio en metros alrededor del punto central para el análisis. Por defecto 500 metros.",
                    "default": 500
                },
                "date_from": {
                    "type": "string",
                    "description": "Fecha de inicio del período de análisis en formato YYYY-MM-DD"
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha de fin del período de análisis en formato YYYY-MM-DD"
                }
            },
            "required": ["latitude", "longitude", "date_from", "date_to"]
        }
    },
    {
        "name": "analyze_soil_report",
        "description": (
            "Interpreta los parámetros de un análisis de suelo y genera recomendaciones específicas "
            "para el cultivo indicado. Evalúa pH, conductividad eléctrica, materia orgánica, macronutrientes "
            "(N, P, K, Ca, Mg, S) y micronutrientes (B, Cu, Fe, Mn, Zn). Calcula deficiencias, excesos "
            "y desequilibrios. Recomienda enmiendas, fertilizantes y dosis. "
            "Usa esta herramienta cuando el usuario haya proporcionado datos de análisis de suelo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_data": {
                    "type": "object",
                    "description": (
                        "Objeto con los parámetros del análisis de suelo y sus valores. "
                        "Ejemplo: {\"pH\": 6.5, \"CE\": 1.2, \"MO\": 2.3, \"P\": 18, \"K\": 0.35, "
                        "\"Ca\": 8.5, \"Mg\": 2.1, \"N_total\": 0.15}"
                    )
                },
                "crop_type": {
                    "type": "string",
                    "description": "Tipo de cultivo a establecer o en producción (ej: 'tomate', 'maíz', 'papa')"
                }
            },
            "required": ["analysis_data", "crop_type"]
        }
    },
    {
        "name": "analyze_foliar_report",
        "description": (
            "Interpreta los parámetros de un análisis foliar y genera recomendaciones de corrección. "
            "Evalúa niveles de macronutrientes (N, P, K, Ca, Mg, S) y micronutrientes (B, Cu, Fe, Mn, Zn) "
            "en tejido vegetal, comparando con rangos de suficiencia para el cultivo y estadío fenológico. "
            "Identifica deficiencias, toxicidades y desequilibrios. Recomienda aplicaciones foliares "
            "o correcciones al suelo según la urgencia. "
            "Usa esta herramienta cuando el usuario proporcione datos de análisis foliar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_data": {
                    "type": "object",
                    "description": (
                        "Objeto con los parámetros del análisis foliar en porcentaje o ppm. "
                        "Ejemplo: {\"N\": 3.2, \"P\": 0.28, \"K\": 3.5, \"Ca\": 1.8, \"Mg\": 0.45, "
                        "\"S\": 0.35, \"B\": 35, \"Zn\": 28, \"Fe\": 85, \"Mn\": 45, \"Cu\": 8}"
                    )
                },
                "crop_type": {
                    "type": "string",
                    "description": "Tipo de cultivo analizado"
                },
                "growth_stage": {
                    "type": "string",
                    "description": "Estadío fenológico del cultivo (ej: 'vegetativo', 'floración', 'fructificación', 'maduración')"
                }
            },
            "required": ["analysis_data", "crop_type"]
        }
    },
    {
        "name": "calculate_irrigation_plan",
        "description": (
            "Calcula un plan de riego detallado basado en los requerimientos hídricos del cultivo, "
            "tipo de suelo, condiciones climáticas y sistema de riego. Usa coeficientes Kc estándar FAO "
            "para diferentes cultivos y etapas de crecimiento. Calcula la lámina neta y bruta de riego, "
            "frecuencia de aplicación e intervalos de riego. Puede ajustar el plan si se proporcionan "
            "datos de ET0 reales del clima. "
            "Usa esta herramienta cuando el usuario pida un plan o cronograma de riego."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop_type": {
                    "type": "string",
                    "description": "Tipo de cultivo (ej: 'tomate', 'maíz', 'papa', 'cebolla')"
                },
                "growth_stage": {
                    "type": "string",
                    "description": "Estadío de crecimiento: 'inicial', 'desarrollo', 'media_estacion', 'maduracion'"
                },
                "soil_type": {
                    "type": "string",
                    "description": "Tipo de suelo: 'arenoso', 'franco_arenoso', 'franco', 'franco_arcilloso', 'arcilloso'"
                },
                "area_ha": {
                    "type": "number",
                    "description": "Área del campo en hectáreas"
                },
                "et0": {
                    "type": "number",
                    "description": "Evapotranspiración de referencia en mm/día (opcional, si no se proporciona usa valor promedio para la región)"
                },
                "climate_data": {
                    "type": "object",
                    "description": "Datos climáticos opcionales obtenidos de la herramienta get_climate_data"
                },
                "irrigation_system": {
                    "type": "string",
                    "description": "Sistema de riego: 'goteo', 'aspersion', 'surcos', 'inundacion'. Por defecto 'goteo'."
                }
            },
            "required": ["crop_type", "growth_stage", "soil_type", "area_ha"]
        }
    },
    {
        "name": "search_openalex",
        "description": (
            "Busca publicaciones científicas en OpenAlex, la base de datos académica "
            "más grande del mundo con más de 250 millones de trabajos indexados. "
            "Devuelve artículos en acceso abierto con título, autores, año, resumen y DOI. "
            "Cubre todas las áreas agrícolas: cereales, hortalizas, frutales, leguminosas, "
            "pastos, cultivos industriales, manejo de suelos, riego, plagas, enfermedades, etc. "
            "Usa esta herramienta cuando el usuario pida literatura científica internacional, "
            "cuando INIA no tenga publicaciones sobre el tema, o cuando quieras complementar "
            "con investigación de UC Davis, CIMMYT, CIAT, Wageningen u otras instituciones globales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Términos de búsqueda (inglés o español). Ejemplos: "
                        "'nitrogen fertilization wheat Chile', 'drip irrigation tomato yield', "
                        "'soil pH correction lime application'. Sé específico para mejores resultados."
                    )
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número de resultados (1-10). Default 5.",
                    "default": 5
                },
                "year_from": {
                    "type": "integer",
                    "description": "Año mínimo de publicación. Default 2010.",
                    "default": 2010
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_inia_rag",
        "description": (
            "Búsqueda SEMÁNTICA en el corpus indexado de la Biblioteca INIA Chile. "
            "Usa esta herramienta cuando necesites RECUPERAR contenido específico de "
            "los documentos: extractos textuales, datos numéricos, recomendaciones técnicas, "
            "metodologías, resultados de experimentos, etc. A diferencia de "
            "`search_inia_biblioteca` (que solo devuelve metadatos), `search_inia_rag` "
            "devuelve fragmentos de texto reales del documento, ordenados por similitud "
            "semántica con tu consulta. Ideal para citar pasajes específicos o cuando el "
            "usuario pregunta '¿qué dice INIA sobre X?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Consulta en lenguaje natural en español. Sé específico: "
                        "'dosis de nitrógeno en uva de mesa Aconcagua', "
                        "'manejo de oídio en vid orgánica', "
                        "'frecuencia de riego para cerezo en Curicó'."
                    )
                },
                "top_k": {
                    "type": "integer",
                    "description": "Número de fragmentos a retornar (1-10). Default 5.",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_inia_biblioteca",
        "description": (
            "Busca documentos técnicos y científicos en la Biblioteca Digital del INIA Chile "
            "(Instituto de Investigaciones Agropecuarias). Contiene más de 19.000 publicaciones "
            "de acceso libre: boletines técnicos, informativos, fichas de cultivo, revistas "
            "científicas, guías de campo y resultados de investigación agrícola chilena. "
            "Usa esta herramienta cuando el usuario pida bibliografía, referencias técnicas, "
            "estudios sobre un cultivo o manejo específico, o cuando quieras fundamentar una "
            "recomendación con investigación científica oficial de Chile."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Términos de búsqueda en español. Puedes usar palabras clave específicas "
                        "como 'riego vid valparaíso', 'fertilización nitrogenada trigo', "
                        "'manejo plagas arándano', 'portainjertos uva de mesa'."
                    )
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número máximo de documentos a retornar. Por defecto 5, máximo 10.",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_agris",
        "description": (
            "Busca publicaciones agrícolas en AGRIS (FAO), la base de datos bibliográfica "
            "agrícola más grande del mundo con 16.5 millones de registros desde 1975. "
            "Indexa 258 idiomas y más de 2,000 proveedores de datos de 100+ países. "
            "Ventaja frente a OpenAlex: incluye literatura gris, informes técnicos, boletines "
            "y publicaciones locales latinoamericanas no indexadas en revistas académicas. "
            "Usa esta herramienta cuando necesites literatura regional latinoamericana, "
            "informes técnicos nacionales, o cuando OpenAlex no devuelva resultados relevantes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Términos de búsqueda en español o inglés. Ejemplos: "
                        "'fertilización nitrógeno vid Chile', 'irrigation grapevine drip', "
                        "'manejo plagas tomate'. Sé específico para mejores resultados."
                    )
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número de resultados (1-10). Default 5.",
                    "default": 5
                },
                "year_from": {
                    "type": "integer",
                    "description": "Año mínimo de publicación. Default sin límite.",
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_faostat_data",
        "description": (
            "Obtiene estadísticas agrícolas oficiales de FAOSTAT (FAO): producción, "
            "rendimiento (hg/ha) y superficie cosechada para cualquier cultivo y país, "
            "con series históricas desde 1961 hasta el año más reciente disponible. "
            "Cubre 245 países y más de 200 cultivos. "
            "Usa esta herramienta cuando el usuario pregunte por benchmarks de rendimiento, "
            "producción nacional o mundial de un cultivo, comparaciones entre países, "
            "o tendencias históricas de producción agrícola."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop": {
                    "type": "string",
                    "description": (
                        "Nombre del cultivo en inglés. Ejemplos: 'grapes', 'wheat', "
                        "'maize', 'tomatoes', 'apples', 'rice', 'soybeans', 'blueberries', "
                        "'cherries', 'avocados', 'walnuts'."
                    )
                },
                "country": {
                    "type": "string",
                    "description": (
                        "País o región. Ejemplos: 'chile', 'argentina', 'world', "
                        "'brazil', 'peru', 'mexico', 'colombia', 'usa'. Default 'world'."
                    ),
                    "default": "world"
                },
                "element": {
                    "type": "string",
                    "description": (
                        "Métrica: 'yield' (rendimiento en hg/ha), "
                        "'production' (producción en toneladas), "
                        "'area' (superficie cosechada en ha). Default 'yield'."
                    ),
                    "enum": ["yield", "production", "area"],
                    "default": "yield"
                },
                "year_from": {
                    "type": "integer",
                    "description": "Año inicial del rango. Default 2015.",
                    "default": 2015
                },
                "year_to": {
                    "type": "integer",
                    "description": "Año final del rango. Default 2023.",
                    "default": 2023
                }
            },
            "required": ["crop"]
        }
    },
    {
        "name": "calculate_fertilization_plan",
        "description": (
            "Calcula un programa de fertilización completo basado en los requerimientos nutricionales "
            "del cultivo, objetivo de rendimiento y análisis de suelo disponible. Determina las dosis "
            "de N-P-K y micronutrientes necesarias, y las distribuye en aplicaciones (presiembra, base, "
            "cobertera, foliar). Considera el tipo de fertilizantes disponibles y ajusta según "
            "los resultados del análisis de suelo si están disponibles. "
            "Usa esta herramienta cuando el usuario pida un programa o plan de fertilización."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop_type": {
                    "type": "string",
                    "description": "Tipo de cultivo"
                },
                "yield_target": {
                    "type": "number",
                    "description": "Objetivo de rendimiento en toneladas por hectárea"
                },
                "soil_analysis": {
                    "type": "object",
                    "description": "Datos del análisis de suelo para ajustar las recomendaciones"
                },
                "area_ha": {
                    "type": "number",
                    "description": "Área del campo en hectáreas"
                },
                "irrigation_type": {
                    "type": "string",
                    "description": "Tipo de sistema de riego para determinar si incluir fertirrigación: 'goteo', 'aspersion', 'gravedad'"
                },
                "cycle_days": {
                    "type": "integer",
                    "description": "Duración del ciclo del cultivo en días"
                }
            },
            "required": ["crop_type"]
        }
    }
]
