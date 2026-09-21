import json
import os
from datetime import date, datetime
from typing import Dict

import requests

from travel_cache import read_cache, write_cache

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPENWEATHER_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
FORECAST_MAX_DAYS = 5

# El nombre de algunas ciudades es ambiguo en OpenWeather (existe "Roma" en
# Italia, en Australia y en EE. UU.). Para esos casos fijamos el pais preferido
# y evitamos que el geocoding resuelva a la ciudad equivocada.
PAIS_PREFERIDO = {
    "roma": "IT", "rome": "IT",
    "paris": "FR", "parís": "FR",
    "londres": "GB", "london": "GB",
    "milan": "IT", "milán": "IT",
    "valencia": "ES",
    "santiago": "ES",
    "cordoba": "ES", "córdoba": "ES",
}

CURRENT_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_WEATHER_CURRENT_SECONDS", str(30 * 60)))
FORECAST_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_WEATHER_FORECAST_SECONDS", str(3 * 3600)))


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {var_name}. "
            f"Definela antes de ejecutar el script."
        )
    return value


def _data_mode() -> str:
    return os.getenv("TRAVEL_DATA_MODE", "cache").lower().strip()


def _load_mock_weather() -> Dict[str, object]:
    path = os.path.join("mock_data", "clima_mock.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolver_coordenadas(ciudad: str, openweather_api_key: str) -> tuple[float, float, str, str]:
    """Resuelve el nombre de la ciudad a coordenadas con la Geocoding API.

    Devuelve (lat, lon, nombre, pais). Si el nombre es ambiguo (p. ej. 'Roma')
    se prioriza el pais definido en PAIS_PREFERIDO; en otro caso, el primer
    resultado que devuelve OpenWeather.
    """
    response = requests.get(
        OPENWEATHER_GEOCODE_URL,
        params={"q": ciudad, "limit": 5, "appid": openweather_api_key},
        timeout=15,
    )
    response.raise_for_status()
    resultados = response.json()
    if not resultados:
        raise RuntimeError(f"OpenWeather no encontro la ciudad '{ciudad}'.")

    preferido = PAIS_PREFERIDO.get(ciudad.strip().lower())
    elegido = resultados[0]
    if preferido:
        for r in resultados:
            if r.get("country") == preferido:
                elegido = r
                break

    return (
        elegido["lat"],
        elegido["lon"],
        elegido.get("name", ciudad),
        elegido.get("country", ""),
    )


def _fetch_weather_live(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    lat, lon, nombre, _pais = _resolver_coordenadas(ciudad, openweather_api_key)
    params = {
        "lat": lat,
        "lon": lon,
        "appid": openweather_api_key,
        "units": "metric",
        "lang": "es",
    }
    response = requests.get(OPENWEATHER_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})
    return {
        "ciudad": data.get("name") or nombre,
        "descripcion": weather.get("description", "sin descripcion"),
        "temp": main.get("temp", "N/D"),
        "feels_like": main.get("feels_like", "N/D"),
        "humedad": main.get("humidity", "N/D"),
        "viento": wind.get("speed", "N/D"),
    }


def fetch_weather_data(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    """Obtiene clima actual con patron Live/Cache/Mock (RNF-02)."""
    mode = _data_mode()
    cache_key = {"endpoint": "current", "ciudad": ciudad.strip().lower()}

    if mode == "mock":
        mock = _load_mock_weather()
        return {**mock["mock_current"], "_source": "mock"}

    cached = read_cache("weather", cache_key, CURRENT_CACHE_TTL_SECONDS)

    if mode == "cache":
        if cached:
            return {**cached, "_source": "cache"}
        mock = _load_mock_weather()
        return {**mock["mock_current"], "_source": "mock"}

    # mode == "live": intenta API, degrada a cache (incluso obsoleta) y luego mock
    try:
        live = _fetch_weather_live(ciudad, openweather_api_key)
        write_cache("weather", cache_key, live)
        return {**live, "_source": "live"}
    except requests.RequestException:
        if cached:
            return {**cached, "_source": "cache-degraded"}
        # leer cache obsoleta como ultimo recurso antes del mock
        stale = read_cache("weather", cache_key, ttl_seconds=10**9)
        if stale:
            return {**stale, "_source": "cache-stale"}
        mock = _load_mock_weather()
        return {**mock["mock_current"], "_source": "mock-degraded"}


def _fetch_forecast_live(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    lat, lon, nombre, _pais = _resolver_coordenadas(ciudad, openweather_api_key)
    params = {
        "lat": lat,
        "lon": lon,
        "appid": openweather_api_key,
        "units": "metric",
        "lang": "es",
    }
    response = requests.get(OPENWEATHER_FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    items = data.get("list", [])
    if not items:
        raise RuntimeError("OpenWeather no devolvio puntos de forecast.")
    city_info = data.get("city", {})
    return {"ciudad": city_info.get("name") or nombre, "items": items}


def fetch_forecast_data(ciudad: str, openweather_api_key: str) -> Dict[str, object]:
    """Obtiene forecast con patron Live/Cache/Mock (RNF-02)."""
    mode = _data_mode()
    cache_key = {"endpoint": "forecast", "ciudad": ciudad.strip().lower()}

    if mode == "mock":
        mock = _load_mock_weather()
        return {**mock["mock_forecast"], "_source": "mock"}

    cached = read_cache("weather", cache_key, FORECAST_CACHE_TTL_SECONDS)

    if mode == "cache":
        if cached:
            return {**cached, "_source": "cache"}
        mock = _load_mock_weather()
        return {**mock["mock_forecast"], "_source": "mock"}

    try:
        live = _fetch_forecast_live(ciudad, openweather_api_key)
        write_cache("weather", cache_key, live)
        return {**live, "_source": "live"}
    except (requests.RequestException, RuntimeError):
        if cached:
            return {**cached, "_source": "cache-degraded"}
        stale = read_cache("weather", cache_key, ttl_seconds=10**9)
        if stale:
            return {**stale, "_source": "cache-stale"}
        mock = _load_mock_weather()
        return {**mock["mock_forecast"], "_source": "mock-degraded"}


def _parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"Fecha invalida '{value}'. Usa formato YYYY-MM-DD."
        ) from exc


def _select_forecast_for_date(items: list[dict], target: date) -> dict:
    """Selecciona el bloque de forecast mas cercano a la fecha objetivo.

    Prioriza misma fecha al mediodia; si no hay, se queda con el bloque
    mas proximo en el tiempo. Asi se evita reventar el grafo cuando la API
    o el mock no contienen exactamente la fecha solicitada.
    """
    parsed: list[tuple[dict, datetime]] = []
    for item in items:
        dt_txt = item.get("dt_txt")
        if not dt_txt:
            continue
        try:
            dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        parsed.append((item, dt))

    if not parsed:
        raise RuntimeError("Sin bloques de forecast utilizables en la respuesta.")

    same_day = [pair for pair in parsed if pair[1].date() == target]
    if same_day:
        return min(same_day, key=lambda pair: abs(pair[1].hour - 12))[0]

    # Fallback: bloque mas cercano en el tiempo
    target_dt = datetime.combine(target, datetime.min.time()).replace(hour=12)
    return min(parsed, key=lambda pair: abs((pair[1] - target_dt).total_seconds()))[0]


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
    Agente meteorologico con 3 modos:
    - modo_actual: si no se pasa fecha.
    - modo_forecast: si fecha objetivo esta dentro de 5 dias.
    - fallback: si fecha objetivo esta mas lejos.

    Datos servidos via patron Live/Cache/Mock segun TRAVEL_DATA_MODE.
    En modo 'mock' la API key no es necesaria.
    """
    mode = _data_mode()
    if mode == "mock":
        openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "MOCK")
    else:
        openweather_api_key = _require_env("OPENWEATHER_API_KEY")

    if not fecha_objetivo.strip():
        weather_data = fetch_weather_data(ciudad, openweather_api_key)
        source = weather_data.pop("_source", "live")
        return f"[modo_actual | fuente:{source}]\n" + weather_summary(weather_data)

    target = _parse_iso_date(fecha_objetivo)
    days_ahead = (target - date.today()).days

    if days_ahead < 0:
        raise RuntimeError(
            f"La fecha objetivo {fecha_objetivo} es pasada. Indica una fecha futura o vacia."
        )

    if days_ahead <= FORECAST_MAX_DAYS:
        forecast_data = fetch_forecast_data(ciudad, openweather_api_key)
        source = forecast_data.pop("_source", "live")
        item = _select_forecast_for_date(forecast_data["items"], target)
        summary = forecast_summary(forecast_data["ciudad"], target, item)
        return f"[modo_forecast | fuente:{source}]\n" + summary

    return "[modo_sin_clima_real_disponible]\n" + fallback_no_real_weather(
        ciudad,
        target,
        days_ahead,
    )


if __name__ == "__main__":
    import argparse
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Agente meteorologico")
    parser.add_argument("ciudad", help="Ciudad destino (ej. Roma)")
    parser.add_argument("--fecha", default="", dest="fecha_objetivo", metavar="YYYY-MM-DD", help="Fecha objetivo (opcional)")
    args = parser.parse_args()

    clima = run_climate_agent(args.ciudad, args.fecha_objetivo)

    print("\n--- REPORTE DE CLIMA ---")
    print(clima)
