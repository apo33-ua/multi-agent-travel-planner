import hashlib
import json
import os
import time
from typing import Any


DEFAULT_CACHE_DIR = os.getenv("TRAVEL_CACHE_DIR", "data/cache")


def _ensure_cache_dir() -> None:
    os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)


def _cache_file_path(namespace: str, params: dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    filename = f"{namespace}_{digest}.json"
    return os.path.join(DEFAULT_CACHE_DIR, filename)


def read_cache(namespace: str, params: dict[str, Any], ttl_seconds: int) -> dict[str, Any] | None:
    _ensure_cache_dir()
    path = _cache_file_path(namespace, params)
    if not os.path.exists(path):
        return None

    age_seconds = time.time() - os.path.getmtime(path)
    if age_seconds > ttl_seconds:
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_cache(namespace: str, params: dict[str, Any], payload: dict[str, Any]) -> None:
    _ensure_cache_dir()
    path = _cache_file_path(namespace, params)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
