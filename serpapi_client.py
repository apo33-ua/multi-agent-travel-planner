import os
from typing import Any

import requests


SERPAPI_URL = "https://serpapi.com/search.json"


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {var_name}. Definela antes de ejecutar."
        )
    return value


def serpapi_search(params: dict[str, Any]) -> dict[str, Any]:
    api_key = _require_env("SERPAPI_API_KEY")
    payload = dict(params)
    payload["api_key"] = api_key

    try:
        response = requests.get(SERPAPI_URL, params=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Error consultando SerpApi: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"SerpApi devolvio una respuesta no JSON (status {response.status_code})."
        ) from exc

    if response.status_code >= 400:
        message = data.get("error") or f"HTTP {response.status_code}"
        raise RuntimeError(f"SerpApi error: {message}")

    if data.get("error"):
        raise RuntimeError(f"SerpApi devolvio error: {data['error']}")

    return data
