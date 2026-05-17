import json
import os
from typing import Any

from serpapi_client import serpapi_search
from travel_cache import read_cache, write_cache


FLIGHTS_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_FLIGHTS_SECONDS", str(12 * 3600)))


def _data_mode() -> str:
    return os.getenv("TRAVEL_DATA_MODE", "cache").lower().strip()


#Cargar mock local
def _load_mock_flights() -> dict[str, Any]:
    path = os.path.join("mock_data", "vuelos_mock.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


#Transformar datos de SerpApi a formato simple
def _normalize_flight_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for group in ("best_flights", "other_flights"):
        for item in data.get(group, [])[:5]:
            flights = item.get("flights", [])
            first = flights[0] if flights else {}
            items.append(
                {
                    "airline": first.get("airline", "N/D"),
                    "price": item.get("price", "N/D"),
                    "duration": item.get("total_duration", "N/D"),
                    "stops": item.get("layovers") or [],
                }
            )

    if not items and data.get("mock_options"):
        return data["mock_options"]

    return items[:5]


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = "",
    adults: int = 1,
) -> dict[str, Any]:
    """Busca vuelos via Live/Cache/Mock (RNF-02).

    Modos:
    - mock: solo devuelve datos simulados.
    - cache: lee cache fresca; si no hay, cae a mock.
    - live: llama a SerpApi; si falla degrada a cache fresca,
            luego a cache obsoleta y por ultimo a mock.
    """
    mode = _data_mode()

    query_key = {
        "engine": "google_flights",
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "adults": adults,
    }

    if mode == "mock":
        mock = _load_mock_flights()
        return {"source": "mock", "query": query_key, "options": _normalize_flight_items(mock)}

    cached = read_cache("flights", query_key, FLIGHTS_CACHE_TTL_SECONDS)

    if mode == "cache":
        if cached:
            return {"source": "cache", "query": query_key, "options": _normalize_flight_items(cached)}
        mock = _load_mock_flights()
        return {"source": "mock", "query": query_key, "options": _normalize_flight_items(mock)}

    # mode == "live": intenta API y degrada en cascada
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "type": 1 if return_date else 2,
        "adults": adults,
        "currency": "EUR",
        "hl": "es",
        "gl": "es",
    }
    if return_date:
        params["return_date"] = return_date

    try:
        live = serpapi_search(params)
        write_cache("flights", query_key, live)
        return {"source": "live", "query": query_key, "options": _normalize_flight_items(live)}
    except RuntimeError:
        if cached:
            return {"source": "cache-degraded", "query": query_key, "options": _normalize_flight_items(cached)}
        stale = read_cache("flights", query_key, ttl_seconds=10**9)
        if stale:
            return {"source": "cache-stale", "query": query_key, "options": _normalize_flight_items(stale)}
        mock = _load_mock_flights()
        return {"source": "mock-degraded", "query": query_key, "options": _normalize_flight_items(mock)}


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Agente de vuelos")
    parser.add_argument("origen", help="IATA origen (ej. MAD)")
    parser.add_argument("destino", help="IATA destino (ej. FCO)")
    parser.add_argument("salida", metavar="YYYY-MM-DD", help="Fecha de salida")
    parser.add_argument("--vuelta", default="", metavar="YYYY-MM-DD", help="Fecha de vuelta (opcional)")
    parser.add_argument("--adultos", type=int, default=1)
    args = parser.parse_args()

    result = search_flights(args.origen, args.destino, args.salida, args.vuelta, args.adultos)
    print("\n--- VUELOS ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
