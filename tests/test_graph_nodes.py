"""Tests de integración de nodos del grafo LangGraph en modo mock."""
from contextlib import contextmanager, ExitStack
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from supervisor_viajes import (
    _flights_node,
    _hotels_node,
    _router_node,
    _weather_node,
    run_supervisor_structured,
)

LLM_MOCK_RESPONSE = ("gemini-2.5-flash", "Respuesta sintetizada de prueba.")

# Módulos que importan invoke_with_fallback directamente con 'from llm_gemini import ...'
# — hay que parchear la referencia local de cada módulo, no la del módulo origen.
_LLM_PATCH_TARGETS = [
    "supervisor_viajes.invoke_with_fallback",
    "agente_turistico.invoke_with_fallback",
]


@contextmanager
def patch_llm(response=LLM_MOCK_RESPONSE):
    """Parchea invoke_with_fallback en todos los módulos que lo importan."""
    with ExitStack() as stack:
        for target in _LLM_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=response))
        yield


class TestRouterNode:
    def test_sin_fecha_activa_clima(self):
        state = {"ciudad": "Roma", "contexto_viaje": "", "objetivo_usuario": ""}
        result = _router_node(state)
        assert result["modo_planificacion"] == "sin-fecha"
        assert result["usar_clima"] is True

    def test_corto_plazo_activa_clima(self):
        fecha = (date.today() + timedelta(days=5)).isoformat()
        state = {
            "ciudad": "Roma",
            "contexto_viaje": "",
            "objetivo_usuario": "",
            "fecha_inicio": fecha,
            "presupuesto_total_eur": 0,
        }
        result = _router_node(state)
        assert result["modo_planificacion"] == "corto-plazo"
        assert result["usar_clima"] is True

    def test_anticipado_omite_clima(self):
        fecha = (date.today() + timedelta(days=30)).isoformat()
        state = {
            "ciudad": "Roma",
            "contexto_viaje": "",
            "objetivo_usuario": "",
            "fecha_inicio": fecha,
            "presupuesto_total_eur": 0,
        }
        result = _router_node(state)
        assert result["modo_planificacion"] == "anticipado"
        assert result["usar_clima"] is False

    def test_presupuesto_activa_vuelos_hoteles(self):
        state = {
            "ciudad": "Roma",
            "contexto_viaje": "",
            "objetivo_usuario": "",
            "presupuesto_total_eur": 800.0,
        }
        result = _router_node(state)
        assert result["usar_vuelos_hoteles"] is True

    def test_sin_presupuesto_ni_keywords_desactiva_vuelos(self):
        state = {
            "ciudad": "Roma",
            "contexto_viaje": "solo quiero ver museos",
            "objetivo_usuario": "turismo cultural",
            "presupuesto_total_eur": 0,
        }
        result = _router_node(state)
        assert result["usar_vuelos_hoteles"] is False


class TestFlightsNode:
    def test_sin_fecha_inicio_devuelve_lista_vacia(self):
        state = {"ciudad": "Roma", "fecha_inicio": "", "fecha_fin": "2026-06-18", "adultos": 2}
        result = _flights_node(state)
        assert result["opciones_vuelos"] == []

    def test_con_fecha_devuelve_opciones_mock(self):
        state = {
            "ciudad": "Roma",
            "fecha_inicio": "2026-06-15",
            "fecha_fin": "2026-06-18",
            "origen_iata": "MAD",
            "destino_iata": "FCO",
            "adultos": 2,
        }
        result = _flights_node(state)
        assert isinstance(result["opciones_vuelos"], list)
        assert len(result["opciones_vuelos"]) > 0

    def test_error_externo_devuelve_error_dict(self):
        state = {
            "ciudad": "Roma",
            "fecha_inicio": "2026-06-15",
            "fecha_fin": "2026-06-18",
            "origen_iata": "MAD",
            "destino_iata": "FCO",
            "adultos": 2,
        }
        with patch("supervisor_viajes.search_flights", side_effect=RuntimeError("API caída")):
            result = _flights_node(state)
        assert "error" in result["opciones_vuelos"][0]


class TestHotelsNode:
    def test_sin_fecha_fin_devuelve_lista_vacia(self):
        state = {"ciudad": "Roma", "fecha_inicio": "2026-06-15", "fecha_fin": "", "adultos": 2}
        result = _hotels_node(state)
        assert result["opciones_hoteles"] == []

    def test_con_fechas_devuelve_opciones_mock(self):
        state = {
            "ciudad": "Roma",
            "fecha_inicio": "2026-06-15",
            "fecha_fin": "2026-06-18",
            "adultos": 2,
        }
        result = _hotels_node(state)
        assert isinstance(result["opciones_hoteles"], list)
        assert len(result["opciones_hoteles"]) > 0


class TestWeatherNode:
    def test_clima_ok_en_modo_mock(self):
        state = {"ciudad": "Roma", "fecha_inicio": ""}
        result = _weather_node(state)
        assert "reporte_clima" in result
        # La API puede devolver el nombre en inglés ("Rome") o en español ("Roma")
        reporte = result["reporte_clima"].lower()
        assert "rom" in reporte

    def test_clima_error_no_propaga_excepcion(self):
        state = {"ciudad": "Roma", "fecha_inicio": ""}
        with patch("supervisor_viajes.run_climate_agent", side_effect=RuntimeError("fallo OpenWeather")):
            result = _weather_node(state)
        assert "reporte_clima" in result
        assert "No se pudo obtener" in result["reporte_clima"]


class TestFullGraphMock:
    def test_run_structured_ok_scenario(self):
        with patch_llm():
            result = run_supervisor_structured(
                ciudad="Roma",
                contexto_viaje="viaje cultural",
                fecha_inicio="2026-06-15",
                fecha_fin="2026-06-18",
                presupuesto_total_eur=800.0,
                adultos=2,
            )
        assert result["presupuesto"]["auditoria"]["decision"] == "ok"
        assert len(result["vuelos"]) > 0
        assert len(result["hoteles"]) > 0
        assert result["supervisor_modelo"] == "gemini-2.5-flash"

    def test_run_structured_sin_presupuesto(self):
        with patch_llm():
            result = run_supervisor_structured(
                ciudad="Roma",
                contexto_viaje="solo turismo",
                fecha_inicio="2026-06-15",
                fecha_fin="2026-06-18",
                presupuesto_total_eur=0,
                adultos=2,
            )
        assert result["presupuesto"]["auditoria"]["decision"] == "sin-datos"

    def test_run_structured_presupuesto_insuficiente(self):
        with patch_llm():
            result = run_supervisor_structured(
                ciudad="Roma",
                fecha_inicio="2026-06-15",
                fecha_fin="2026-06-18",
                presupuesto_total_eur=10.0,
                adultos=2,
            )
        assert result["presupuesto"]["auditoria"]["decision"] == "solo-sugerencias-fuera-presupuesto"
        assert len(result["presupuesto"]["acciones_sugeridas"]) >= 3

    def test_routing_fields_present(self):
        with patch_llm():
            result = run_supervisor_structured(ciudad="Roma")
        routing = result["routing"]
        assert "modo_planificacion" in routing
        assert "usar_clima" in routing
        assert "usar_vuelos_hoteles" in routing
        assert "motivo_ruta" in routing

    def test_respuesta_markdown_no_vacia(self):
        with patch_llm():
            result = run_supervisor_structured(ciudad="Roma")
        assert len(result["respuesta_markdown"]) > 0
