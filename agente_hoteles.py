import json
import os
from typing import Any

from serpapi_client import serpapi_search
from travel_cache import read_cache, write_cache


HOTELS_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_HOTELS_SECONDS", str(24 * 3600)))


def _load_mock_hotels() -> dict[str, Any]:
    path = os.path.join("mock_data", "hoteles_mock.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_hotel_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    properties = data.get("properties", [])
    items: list[dict[str, Any]] = []

    for item in properties[:8]:
        items.append(
            {
                "name": item.get("name", "N/D"),
                "rating": item.get("overall_rating", "N/D"),
                "price_per_night": item.get("rate_per_night", {}).get("lowest", "N/D"),
                "total_rate": item.get("total_rate", {}).get("lowest", "N/D"),
                "type": item.get("type", "N/D"),
            }
        )

    if not items and data.get("mock_options"):
        return data["mock_options"]

    return items[:6]


def search_hotels(
    destination: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
) -> dict[str, Any]:
    mode = os.getenv("TRAVEL_DATA_MODE", "cache").lower().strip()

    query_key = {
        "engine": "google_hotels",
        "destination": destination,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
    }

    cached = read_cache("hotels", query_key, HOTELS_CACHE_TTL_SECONDS)

    if mode == "cache" and cached:
        return {
            "source": "cache",
            "query": query_key,
            "options": _normalize_hotel_items(cached),
        }

    if mode == "cache" and not cached:
        mock = _load_mock_hotels()
        return {
            "source": "mock",
            "query": query_key,
            "options": _normalize_hotel_items(mock),
        }

    params = {
        "engine": "google_hotels",
        "q": destination,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
        "currency": "EUR",
        "hl": "es",
        "gl": "es",
    }

    live = serpapi_search(params)
    write_cache("hotels", query_key, live)

    return {
        "source": "live",
        "query": query_key,
        "options": _normalize_hotel_items(live),
    }


if __name__ == "__main__":
    destination = input("Destino (ej. Roma): ").strip()
    check_in = input("Check-in (YYYY-MM-DD): ").strip()
    check_out = input("Check-out (YYYY-MM-DD): ").strip()

    result = search_hotels(destination, check_in, check_out)
    print("\n--- HOTELES ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
