import json
import os
from typing import Any

from serpapi_client import serpapi_search
from travel_cache import read_cache, write_cache


HOTELS_CACHE_TTL_SECONDS = int(os.getenv("TRAVEL_CACHE_TTL_HOTELS_SECONDS", str(24 * 3600)))


def _data_mode() -> str:
    return os.getenv("TRAVEL_DATA_MODE", "cache").lower().strip()


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
    """Busca hoteles via Live/Cache/Mock (RNF-02).

    Modos:
    - mock: solo devuelve datos simulados.
    - cache: lee cache fresca; si no hay, cae a mock.
    - live: llama a SerpApi; si falla degrada a cache fresca,
            luego a cache obsoleta y por ultimo a mock.
    """
    mode = _data_mode()

    query_key = {
        "engine": "google_hotels",
        "destination": destination,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": adults,
    }

    if mode == "mock":
        mock = _load_mock_hotels()
        return {"source": "mock", "query": query_key, "options": _normalize_hotel_items(mock)}

    cached = read_cache("hotels", query_key, HOTELS_CACHE_TTL_SECONDS)

    if mode == "cache":
        if cached:
            return {"source": "cache", "query": query_key, "options": _normalize_hotel_items(cached)}
        mock = _load_mock_hotels()
        return {"source": "mock", "query": query_key, "options": _normalize_hotel_items(mock)}

    # mode == "live": API con degradacion en cascada
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

    try:
        live = serpapi_search(params)
        write_cache("hotels", query_key, live)
        return {"source": "live", "query": query_key, "options": _normalize_hotel_items(live)}
    except RuntimeError:
        if cached:
            return {"source": "cache-degraded", "query": query_key, "options": _normalize_hotel_items(cached)}
        stale = read_cache("hotels", query_key, ttl_seconds=10**9)
        if stale:
            return {"source": "cache-stale", "query": query_key, "options": _normalize_hotel_items(stale)}
        mock = _load_mock_hotels()
        return {"source": "mock-degraded", "query": query_key, "options": _normalize_hotel_items(mock)}


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Agente de hoteles")
    parser.add_argument("destino", help="Ciudad destino (ej. Roma)")
    parser.add_argument("check_in", metavar="CHECK-IN", help="Fecha check-in (YYYY-MM-DD)")
    parser.add_argument("check_out", metavar="CHECK-OUT", help="Fecha check-out (YYYY-MM-DD)")
    parser.add_argument("--adultos", type=int, default=2)
    args = parser.parse_args()

    result = search_hotels(args.destino, args.check_in, args.check_out, args.adultos)
    print("\n--- HOTELES ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
