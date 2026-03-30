import os
from datetime import date, datetime
from typing import Dict

import requests

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
FORECAST_MAX_DAYS = 5


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {var_name}. "
            f"Definela antes de ejecutar el script."
        )
    return value


def fetch_weather_data(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    params = {
        "q": ciudad,
        "appid": openweather_api_key,
        "units": "metric",
        "lang": "es",
    }

    try:
        response = requests.get(OPENWEATHER_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"No se pudo obtener el clima de {ciudad} desde OpenWeather: {exc}"
        ) from exc

    data = response.json()
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})

    return {
        "ciudad": data.get("name", ciudad),
        "descripcion": weather.get("description", "sin descripcion"),
        "temp": main.get("temp", "N/D"),
        "feels_like": main.get("feels_like", "N/D"),
        "humedad": main.get("humidity", "N/D"),
        "viento": wind.get("speed", "N/D"),
    }


def fetch_forecast_data(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    params = {
        "q": ciudad,
        "appid": openweather_api_key,
        "units": "metric",
        "lang": "es",
    }

    try:
        response = requests.get(OPENWEATHER_FORECAST_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"No se pudo obtener el forecast de {ciudad} desde OpenWeather: {exc}"
        ) from exc

    data = response.json()
    items = data.get("list", [])
    if not items:
        raise RuntimeError("OpenWeather no devolvio puntos de forecast.")

    city_info = data.get("city", {})
    return {
        "ciudad": city_info.get("name", ciudad),
        "items": items,
    }


def _parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"Fecha invalida '{value}'. Usa formato YYYY-MM-DD."
        ) from exc


def _select_forecast_for_date(items: list[dict], target: date) -> dict:
    same_day = []
    for item in items:
        dt_txt = item.get("dt_txt")
        if not dt_txt:
            continue
        try:
            dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if dt.date() == target:
            same_day.append((item, dt))

    if same_day:
        target_hour = 12
        best_item, _best_dt = min(same_day, key=lambda pair: abs(pair[1].hour - target_hour))
        return best_item

    raise RuntimeError(
        "No hay bloques de forecast exactos para la fecha solicitada."
    )
def weather_summary(weather_data: dict) -> str:
    return (
        f"Clima actual en {weather_data['ciudad']}: {weather_data['descripcion']}. "
        f"Temperatura {weather_data['temp']}C, sensacion termica {weather_data['feels_like']}C, "
        f"humedad {weather_data['humedad']}%, viento {weather_data['viento']} m/s."
    )


def forecast_summary(ciudad: str, fecha_objetivo: date, item: dict) -> str:
    main = item.get("main", {})
    weather = item.get("weather", [{}])[0]
    wind = item.get("wind", {})
    dt_txt = item.get("dt_txt", "hora no disponible")

    return (
        f"Forecast para {ciudad} el {fecha_objetivo.isoformat()} (bloque {dt_txt}): "
        f"{weather.get('description', 'sin descripcion')}. "
        f"Temperatura {main.get('temp', 'N/D')}C, sensacion termica {main.get('feels_like', 'N/D')}C, "
        f"humedad {main.get('humidity', 'N/D')}%, viento {wind.get('speed', 'N/D')} m/s."
    )


def fallback_no_real_weather(ciudad: str, fecha_objetivo: date, days_ahead: int) -> str:
    return (
        f"No hay clima real fiable para {ciudad} en la fecha {fecha_objetivo.isoformat()} "
        f"(faltan {days_ahead} dias). OpenWeather en este plan ofrece forecast detallado hasta "
        f"{FORECAST_MAX_DAYS} dias. Recomendacion: reconsultar clima 7-10 dias antes del viaje."
    )


def run_climate_agent(ciudad: str, fecha_objetivo: str = "") -> str:
    """
    Agente meteorologico especializado con 3 modos:
    - modo_actual: si no se pasa fecha.
    - modo_forecast: si fecha objetivo esta dentro de 5 dias.
    - fallback: si fecha objetivo esta mas lejos y no hay clima real disponible.
    """
    openweather_api_key = _require_env("OPENWEATHER_API_KEY")

    if not fecha_objetivo.strip():
        weather_data = fetch_weather_data(ciudad, openweather_api_key)
        return "[modo_actual]\n" + weather_summary(weather_data)

    target = _parse_iso_date(fecha_objetivo)
    days_ahead = (target - date.today()).days

    if days_ahead < 0:
        raise RuntimeError(
            f"La fecha objetivo {fecha_objetivo} es pasada. Indica una fecha futura o vacia."
        )

    if days_ahead <= FORECAST_MAX_DAYS:
        forecast_data = fetch_forecast_data(ciudad, openweather_api_key)
        item = _select_forecast_for_date(forecast_data["items"], target)
        summary = forecast_summary(forecast_data["ciudad"], target, item)
        return "[modo_forecast]\n" + summary

    return "[modo_sin_clima_real_disponible]\n" + fallback_no_real_weather(
        ciudad,
        target,
        days_ahead,
    )


if __name__ == "__main__":
    print("Iniciando agente meteorologico...\n")

    ciudad = input("Ciudad destino: ").strip()
    fecha_objetivo = input("Fecha objetivo (YYYY-MM-DD, opcional): ").strip()

    if not ciudad:
        raise SystemExit("Debes indicar una ciudad.")

    clima = run_climate_agent(ciudad, fecha_objetivo)

    print("\n--- REPORTE DE CLIMA ---")
    print(clima)