import json
import os
from typing import Any

from serpapi_client import serpapi_search
from travel_cache import read_cache, write_cache


FLIGHTS_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_FLIGHTS_SECONDS", str(12 * 3600)))


def _load_mock_flights() -> dict[str, Any]:
    path = os.path.join("mock_data", "vuelos_mock.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    mode = os.getenv("TRAVEL_DATA_MODE", "cache").lower().strip()

    query_key = {
        "engine": "google_flights",
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "adults": adults,
    }

    cached = read_cache("flights", query_key, FLIGHTS_CACHE_TTL_SECONDS)

    if mode == "cache" and cached:
        return {
            "source": "cache",
            "query": query_key,
            "options": _normalize_flight_items(cached),
        }

    if mode == "cache" and not cached:
        mock = _load_mock_flights()
        return {
            "source": "mock",
            "query": query_key,
            "options": _normalize_flight_items(mock),
        }

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

    live = serpapi_search(params)
    write_cache("flights", query_key, live)

    return {
        "source": "live",
        "query": query_key,
        "options": _normalize_flight_items(live),
    }


if __name__ == "__main__":
    origin = input("Origen (ej. MAD): ").strip()
    destination = input("Destino (ej. FCO): ").strip()
    departure = input("Fecha salida (YYYY-MM-DD): ").strip()
    ret = input("Fecha vuelta (YYYY-MM-DD, opcional): ").strip()

    result = search_flights(origin, destination, departure, ret)
    print("\n--- VUELOS ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
