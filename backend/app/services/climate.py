import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def get_climate_data(latitude: float, longitude: float, days: int = 7) -> dict:
    """
    Fetch current and forecast climate data from Open-Meteo API.
    Returns structured dict with location, current conditions, 7-day forecast, and aggregates.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "et0_fao_evapotranspiration",
            "windspeed_10m_max",
            "relative_humidity_2m_max",
            "relative_humidity_2m_min",
        ],
        "hourly": [
            "temperature_2m",
            "precipitation",
            "relative_humidity_2m",
        ],
        "forecast_days": min(days, 16),
        "timezone": "auto",
        "wind_speed_unit": "kmh",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})
        times = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        et0_list = daily.get("et0_fao_evapotranspiration", [])
        wind = daily.get("windspeed_10m_max", [])
        hum_max = daily.get("relative_humidity_2m_max", [])
        hum_min = daily.get("relative_humidity_2m_min", [])

        forecast = []
        for i, date in enumerate(times):
            day_data = {
                "date": date,
                "temp_max_c": temp_max[i] if i < len(temp_max) else None,
                "temp_min_c": temp_min[i] if i < len(temp_min) else None,
                "precipitation_mm": precip[i] if i < len(precip) else None,
                "et0_mm": et0_list[i] if i < len(et0_list) else None,
                "wind_max_kmh": wind[i] if i < len(wind) else None,
                "humidity_max_pct": hum_max[i] if i < len(hum_max) else None,
                "humidity_min_pct": hum_min[i] if i < len(hum_min) else None,
            }
            forecast.append(day_data)

        # Aggregate totals
        total_et0 = sum(v for v in et0_list if v is not None)
        total_precip = sum(v for v in precip if v is not None)

        # Current conditions (first day)
        current = {}
        if forecast:
            first = forecast[0]
            current = {
                "date": first["date"],
                "temp_max_c": first["temp_max_c"],
                "temp_min_c": first["temp_min_c"],
                "temp_avg_c": (
                    round((first["temp_max_c"] + first["temp_min_c"]) / 2, 1)
                    if first["temp_max_c"] is not None and first["temp_min_c"] is not None
                    else None
                ),
                "precipitation_mm": first["precipitation_mm"],
                "et0_mm": first["et0_mm"],
                "wind_max_kmh": first["wind_max_kmh"],
                "humidity_max_pct": first["humidity_max_pct"],
                "humidity_min_pct": first["humidity_min_pct"],
            }

        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": data.get("timezone", "UTC"),
                "elevation_m": data.get("elevation"),
            },
            "current_conditions": current,
            "forecast": forecast,
            "summary": {
                "days_requested": days,
                "total_et0_mm": round(total_et0, 2),
                "total_precipitation_mm": round(total_precip, 2),
                "water_deficit_mm": round(total_et0 - total_precip, 2),
                "avg_temp_max_c": (
                    round(sum(v for v in temp_max if v is not None) / len([v for v in temp_max if v is not None]), 1)
                    if any(v is not None for v in temp_max) else None
                ),
                "avg_et0_daily_mm": round(total_et0 / len(et0_list), 2) if et0_list else None,
            },
            "units": {
                "temperature": "°C",
                "precipitation": "mm",
                "et0": "mm/día",
                "wind": "km/h",
                "humidity": "%",
            },
            "data_source": "Open-Meteo (ERA5 + IFS)",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Open-Meteo API HTTP error: {e.response.status_code} - {e.response.text}")
        return {
            "error": True,
            "message": f"Error al consultar datos climáticos: HTTP {e.response.status_code}",
            "location": {"latitude": latitude, "longitude": longitude},
        }
    except httpx.RequestError as e:
        logger.error(f"Open-Meteo API request error: {str(e)}")
        return {
            "error": True,
            "message": "No se pudo conectar al servicio climático. Verifica tu conexión a internet.",
            "location": {"latitude": latitude, "longitude": longitude},
        }
    except Exception as e:
        logger.error(f"Unexpected error fetching climate data: {str(e)}")
        return {
            "error": True,
            "message": f"Error inesperado al obtener datos climáticos: {str(e)}",
            "location": {"latitude": latitude, "longitude": longitude},
        }
