"""Fixtures compartidos entre todos los tests del proyecto."""
import os
import sys

import pytest

# Asegura que el raiz del proyecto esté en el path para todos los tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Fuerza modo mock globalmente para que ningún test llame a APIs externas
os.environ.setdefault("TRAVEL_DATA_MODE", "mock")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")


@pytest.fixture()
def base_state() -> dict:
    """Estado mínimo válido del supervisor para tests de nodos."""
    return {
        "ciudad": "Roma",
        "contexto_viaje": "fin de semana cultural",
        "objetivo_usuario": "ver el Coliseo",
        "origen_iata": "MAD",
        "destino_iata": "FCO",
        "fecha_inicio": "2026-06-15",
        "fecha_fin": "2026-06-18",
        "presupuesto_total_eur": 800.0,
        "adultos": 2,
    }


@pytest.fixture()
def vuelos_mock() -> list[dict]:
    return [
        {"airline": "Iberia", "price": "250", "duration": 145, "stops": []},
        {"airline": "Ryanair", "price": "180", "duration": 140, "stops": []},
        {"airline": "Vueling", "price": "320", "duration": 150, "stops": []},
    ]


@pytest.fixture()
def hoteles_mock() -> list[dict]:
    return [
        {"name": "Hotel Roma Centro", "rating": 4.2, "price_per_night": "90", "total_rate": "270", "type": "Hotel"},
        {"name": "Hostal Trastevere", "rating": 3.8, "price_per_night": "55", "total_rate": "165", "type": "Hostel"},
        {"name": "Grand Hotel de la Minerve", "rating": 4.9, "price_per_night": "400", "total_rate": "1200", "type": "Hotel"},
    ]
