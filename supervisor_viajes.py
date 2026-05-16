from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, TypedDict

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agente_clima import FORECAST_MAX_DAYS, run_climate_agent
from agente_hoteles import search_hotels
from agente_turistico import run_tourism_agent
from agente_vuelos import search_flights
from llm_gemini import invoke_with_fallback

logger = logging.getLogger(__name__)

#Umbral corto plazo
SHORT_TERM_DAYS = 14

#Defino los campo que viajan por el grafo
class SupervisorState(TypedDict, total=False):
    ciudad: str
    contexto_viaje: str
    objetivo_usuario: str
    origen_iata: str
    destino_iata: str
    presupuesto_total_eur: float
    adultos: int
    fecha_inicio: str
    fecha_fin: str
    horizonte_dias: int | None
    modo_planificacion: str
    usar_clima: bool
    usar_vuelos_hoteles: bool
    usar_turismo: bool
    motivo_ruta: str
    reporte_clima: str
    propuesta_turistica: str
    opciones_vuelos: list[dict[str, Any]]
    opciones_hoteles: list[dict[str, Any]]
    combinaciones_presupuesto: list[dict[str, Any]]
    combinaciones_excluidas: list[dict[str, Any]]
    auditoria_presupuesto: dict[str, Any]
    acciones_sugeridas: list[str]
    respuesta_final: str
    supervisor_modelo: str


CITY_TO_IATA = {
    "roma": "FCO",
    "londres": "LON",
    "oslo": "OSL",
    "madrid": "MAD",
    "paris": "PAR",
    "barcelona": "BCN",
}

# Cache en memoria para evitar invocar al LLM mas de una vez por ciudad
_IATA_LLM_CACHE: dict[str, str] = {}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"Fecha invalida '{value}'. Usa formato YYYY-MM-DD."
        ) from exc


def _to_float(value: Any) -> float | None:
    """Convierte cadenas monetarias heterogeneas a float.

    Soporta formatos europeos (1.250,75) y anglosajones (1,250.75) detectando
    el separador decimal como el ultimo simbolo de puntuacion presente.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = re.sub(r"[^0-9.,]", "", value.strip().replace("\u00a0", " "))
    if not cleaned:
        return None

    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")

    if last_dot == -1 and last_comma == -1:
        try:
            return float(cleaned)
        except ValueError:
            return None

    decimal_pos = max(last_dot, last_comma)
    integer_part = cleaned[:decimal_pos].replace(".", "").replace(",", "") or "0"
    decimal_part = cleaned[decimal_pos + 1:]

    # Si solo aparece un tipo de separador y la "decimal" tiene >2 digitos,
    # en realidad era separador de miles (ej. "1.250" en formato europeo).
    if (last_dot == -1 or last_comma == -1) and len(decimal_part) > 2:
        try:
            return float(integer_part + decimal_part)
        except ValueError:
            return None

    try:
        return float(f"{integer_part}.{decimal_part}")
    except ValueError:
        return None


def _resolve_iata_with_llm(ciudad: str) -> str | None:
    """RF-02: delega al LLM la inferencia del codigo IATA principal."""
    key = ciudad.strip().lower()
    if not key:
        return None
    if key in _IATA_LLM_CACHE:
        return _IATA_LLM_CACHE[key]

    try:
        _model, content = invoke_with_fallback(
            [
                SystemMessage(
                    content=(
                        "Eres un experto en codigos IATA de aeropuertos. "
                        "Devuelve EXCLUSIVAMENTE el codigo IATA principal de 3 letras "
                        "del aeropuerto que sirve a la ciudad indicada. Si no existe o "
                        "no estas seguro, responde con la palabra DESCONOCIDO. "
                        "Sin justificacion, sin frases, sin puntuacion adicional."
                    )
                ),
                HumanMessage(content=f"Ciudad: {ciudad}"),
            ]
        )
    except Exception:
        return None

    match = re.search(r"\b([A-Z]{3})\b", (content or "").upper())
    if not match:
        return None
    code = match.group(1)
    if code == "DES":  # primeras 3 letras de DESCONOCIDO
        return None
    _IATA_LLM_CACHE[key] = code
    return code


def _resolve_destination_iata(ciudad: str, destino_iata: str) -> str:
    if destino_iata.strip():
        return destino_iata.strip().upper()
    key = ciudad.strip().lower()
    if key in CITY_TO_IATA:
        return CITY_TO_IATA[key]
    inferred = _resolve_iata_with_llm(ciudad)
    if inferred:
        return inferred
    return ciudad[:3].upper()


def _needs_flights_hotels(state: SupervisorState) -> bool:
    text = (
        f"{state.get('contexto_viaje', '')} "
        f"{state.get('objetivo_usuario', '')}"
    ).lower()
    budget = state.get("presupuesto_total_eur", 0) or 0

    keywords = ["presupuesto", "vuelo", "hotel", "alojamiento", "organizar", "planificar"]
    return budget > 0 or any(word in text for word in keywords)


def _needs_tourism(state: SupervisorState) -> bool:
    """Devuelve False solo cuando la intencion es exclusivamente de precios/logistica.

    Activar turismo por defecto es la decision conservadora: una propuesta
    cultural enriquece cualquier plan. Solo se omite si el usuario senala
    explicitamente que solo quiere precios o busqueda de vuelos/hoteles.
    """
    text = (
        f"{state.get('contexto_viaje', '')} "
        f"{state.get('objetivo_usuario', '')}"
    ).lower()

    price_only = ["solo precio", "solo vuelo", "solo hotel", "buscar vuelo",
                  "buscar hotel", "cuanto cuesta", "comparar precio"]
    cultural = ["turismo", "visitar", "monumentos", "cultura", "que ver",
                "que hacer", "restaurante", "itinerario", "plan"]

    has_cultural = any(k in text for k in cultural)
    has_price_only = any(k in text for k in price_only)

    # Si pide explicitamente turismo, siempre activar
    if has_cultural:
        return True
    # Si pide explicitamente solo precios sin interes cultural, omitir
    if has_price_only:
        return False
    # Por defecto: activar (enriquece la respuesta)
    return True


def _build_budget_combinations(
    vuelos: list[dict[str, Any]],
    hoteles: list[dict[str, Any]],
    presupuesto: float,
) -> dict[str, Any]:
    """RF-10 + RF-11 + RF-12: cruza vuelos x hoteles, marca cada combinacion
    con excluded_by_budget y devuelve auditoria completa."""
    combos: list[dict[str, Any]] = []

    for vuelo in vuelos[:6]:
        precio_vuelo = _to_float(vuelo.get("price"))
        if precio_vuelo is None:
            continue

        for hotel in hoteles[:6]:
            precio_hotel = _to_float(hotel.get("total_rate"))
            if precio_hotel is None:
                continue

            total = precio_vuelo + precio_hotel
            excluded = total > presupuesto
            combos.append(
                {
                    "airline": vuelo.get("airline", "N/D"),
                    "flight_price": round(precio_vuelo, 2),
                    "hotel_name": hotel.get("name", "N/D"),
                    "hotel_total": round(precio_hotel, 2),
                    "total_estimated": round(total, 2),
                    "fits_budget": not excluded,
                    "budget_gap": round(presupuesto - total, 2),
                    "excluded_by_budget": excluded,
                }
            )

    validas = sorted(
        [c for c in combos if not c["excluded_by_budget"]],
        key=lambda c: c["total_estimated"],
    )[:5]
    excluidas = sorted(
        [c for c in combos if c["excluded_by_budget"]],
        key=lambda c: c["total_estimated"],
    )[:5]

    if validas:
        decision = "ok"
    elif excluidas:
        decision = "solo-sugerencias-fuera-presupuesto"
    else:
        decision = "sin-datos"

    return {
        "validas": validas,
        "excluidas": excluidas,
        "auditoria": {
            "decision": decision,
            "presupuesto_eur": round(presupuesto, 2),
            "total_evaluadas": len(combos),
            "n_validas": len(validas),
            "n_excluidas": len(excluidas),
        },
    }


def _router_node(state: SupervisorState) -> dict[str, Any]:
    inicio = _parse_iso_date(state.get("fecha_inicio"))
    horizon: int | None = None

    if inicio is not None:
        horizon = (inicio - date.today()).days

    needs_plan = _needs_flights_hotels(state)

    if inicio is None:
        resultado = {
            "horizonte_dias": None,
            "modo_planificacion": "sin-fecha",
            "usar_clima": True,
            "usar_vuelos_hoteles": needs_plan,
            "motivo_ruta": (
                "No hay fecha de inicio: se asume plan cercano y se incluye clima actual. "
                f"Vuelos/hoteles {'activados' if needs_plan else 'no activados'} por intencion."
            ),
        }
    elif horizon <= SHORT_TERM_DAYS:
        # Clima solo si OpenWeather puede dar forecast real (<=5 dias)
        usa_clima = horizon <= FORECAST_MAX_DAYS
        # Fecha dada = intencion de planificacion → siempre activar vuelos/hoteles
        resultado = {
            "horizonte_dias": horizon,
            "modo_planificacion": "corto-plazo",
            "usar_clima": usa_clima,
            "usar_vuelos_hoteles": True,
            "motivo_ruta": (
                f"Viaje en {horizon} dias: "
                f"{'forecast disponible, clima activado' if usa_clima else f'fuera del horizonte de forecast ({FORECAST_MAX_DAYS} dias), clima omitido'}. "
                "Vuelos/hoteles activados por fecha proporcionada."
            ),
        }
    else:
        resultado = {
            "horizonte_dias": horizon,
            "modo_planificacion": "anticipado",
            "usar_clima": False,
            "usar_vuelos_hoteles": True,
            "motivo_ruta": (
                f"Viaje en {horizon} dias: se omite clima actual y se prioriza planificacion "
                "(vuelos/hotel/itinerario base)."
            ),
        }

    resultado["usar_turismo"] = _needs_tourism(state)
    logger.info(
        "router | ciudad=%s modo=%s clima=%s vuelos_hoteles=%s turismo=%s",
        state.get("ciudad"),
        resultado["modo_planificacion"],
        resultado["usar_clima"],
        resultado["usar_vuelos_hoteles"],
        resultado["usar_turismo"],
    )
    return resultado


def _tourism_node(state: SupervisorState) -> dict[str, Any]:
    logger.info("tourism | ciudad=%s", state.get("ciudad"))
    return {
        "propuesta_turistica": run_tourism_agent(
            state["ciudad"],
            state.get("contexto_viaje", ""),
        )
    }


def _fetch_node(state: SupervisorState) -> dict[str, Any]:
    """Nodo pass-through que dispara la ejecucion paralela de flights y hotels."""
    logger.info("fetch | lanzando vuelos y hoteles en paralelo")
    return {}


def _weather_node(state: SupervisorState) -> dict[str, Any]:
    logger.info("weather | ciudad=%s fecha=%s", state.get("ciudad"), state.get("fecha_inicio"))
    try:
        return {
            "reporte_clima": run_climate_agent(
                state["ciudad"],
                state.get("fecha_inicio", ""),
            )
        }
    except Exception as exc:
        logger.warning("weather | fallo obteniendo clima: %s", exc)
        return {
            "reporte_clima": (
                f"[modo_sin_clima_real_disponible | fuente:error]\n"
                f"No se pudo obtener el clima: {exc}"
            )
        }


def _flights_node(state: SupervisorState) -> dict[str, Any]:
    fecha_inicio = state.get("fecha_inicio", "").strip()
    fecha_fin = state.get("fecha_fin", "").strip()
    if not fecha_inicio:
        logger.info("flights | sin fecha de inicio, saltando busqueda")
        return {"opciones_vuelos": []}

    origen = (state.get("origen_iata", "MAD") or "MAD").upper()
    destino = _resolve_destination_iata(state["ciudad"], state.get("destino_iata", ""))
    adultos = int(state.get("adultos", 2) or 2)
    logger.info("flights | %s → %s el %s (%d adultos)", origen, destino, fecha_inicio, adultos)

    try:
        result = search_flights(origen, destino, fecha_inicio, fecha_fin, adultos)
        opciones = result.get("options", [])
        logger.info("flights | %d opciones obtenidas (fuente: %s)", len(opciones), result.get("source"))
        return {"opciones_vuelos": opciones}
    except Exception as exc:
        logger.warning("flights | fallo: %s", exc)
        return {"opciones_vuelos": [{"error": str(exc)}]}


def _hotels_node(state: SupervisorState) -> dict[str, Any]:
    fecha_inicio = state.get("fecha_inicio", "").strip()
    fecha_fin = state.get("fecha_fin", "").strip()
    if not (fecha_inicio and fecha_fin):
        logger.info("hotels | sin fechas completas, saltando busqueda")
        return {"opciones_hoteles": []}

    adultos = int(state.get("adultos", 2) or 2)
    logger.info("hotels | %s del %s al %s (%d adultos)", state.get("ciudad"), fecha_inicio, fecha_fin, adultos)

    try:
        result = search_hotels(state["ciudad"], fecha_inicio, fecha_fin, adultos)
        opciones = result.get("options", [])
        logger.info("hotels | %d opciones obtenidas (fuente: %s)", len(opciones), result.get("source"))
        return {"opciones_hoteles": opciones}
    except Exception as exc:
        logger.warning("hotels | fallo: %s", exc)
        return {"opciones_hoteles": [{"error": str(exc)}]}


def _budget_node(state: SupervisorState) -> dict[str, Any]:
    presupuesto = float(state.get("presupuesto_total_eur", 0) or 0)
    vuelos = state.get("opciones_vuelos", [])
    hoteles = state.get("opciones_hoteles", [])

    if presupuesto <= 0 or not vuelos or not hoteles:
        if presupuesto <= 0:
            motivo = "Sin presupuesto declarado"
            acciones: list[str] = []
        else:
            motivo = "Sin opciones de vuelos u hoteles disponibles"
            acciones = [
                "Reintentar la busqueda con fechas alternativas",
                "Probar otro aeropuerto de origen o destino",
            ]
        return {
            "combinaciones_presupuesto": [],
            "combinaciones_excluidas": [],
            "auditoria_presupuesto": {
                "decision": "sin-datos",
                "presupuesto_eur": round(presupuesto, 2),
                "total_evaluadas": 0,
                "n_validas": 0,
                "n_excluidas": 0,
                "motivo": motivo,
            },
            "acciones_sugeridas": acciones,
        }

    resultado = _build_budget_combinations(vuelos, hoteles, presupuesto)
    decision = resultado["auditoria"]["decision"]
    logger.info(
        "budget | decision=%s validas=%d excluidas=%d presupuesto=%.2f",
        decision,
        resultado["auditoria"]["n_validas"],
        resultado["auditoria"]["n_excluidas"],
        presupuesto,
    )

    if decision == "solo-sugerencias-fuera-presupuesto":
        acciones = [
            "Aumentar el presupuesto total",
            "Reducir el numero de noches o cambiar a temporada baja",
            "Buscar solo actividades, sin alojamiento",
            "Probar otro aeropuerto de origen",
        ]
    else:
        acciones = []

    return {
        "combinaciones_presupuesto": resultado["validas"],
        "combinaciones_excluidas": resultado["excluidas"],
        "auditoria_presupuesto": resultado["auditoria"],
        "acciones_sugeridas": acciones,
    }


def _synth_node(state: SupervisorState) -> dict[str, Any]:
    usa_clima = state.get("usar_clima", False)
    usa_vh = state.get("usar_vuelos_hoteles", False)
    entrada_clima = state.get("reporte_clima", "No consultado en modo anticipado.")
    entrada_vuelos = state.get("opciones_vuelos", [])
    entrada_hoteles = state.get("opciones_hoteles", [])
    combos_validos = state.get("combinaciones_presupuesto", [])
    combos_excluidos = state.get("combinaciones_excluidas", [])
    auditoria = state.get("auditoria_presupuesto", {})
    acciones = state.get("acciones_sugeridas", [])
    decision = auditoria.get("decision", "sin-datos")

    if usa_clima:
        extra = (
            "Incluye recomendaciones de ropa y actividades condicionadas al clima reportado."
        )
    else:
        extra = (
            "No des ropa especifica por clima actual. En su lugar, incluye un bloque 'Replan meteo' "
            "explicando que se debe reconsultar clima 7-10 dias antes de viajar."
        )

    if usa_vh:
        if decision == "ok":
            extra_vh = (
                "Presenta solo las combinaciones validas (dentro de presupuesto), ordenadas por precio."
            )
        elif decision == "solo-sugerencias-fuera-presupuesto":
            extra_vh = (
                "AVISO: ninguna combinacion encaja en el presupuesto declarado. "
                "Muestra las opciones mas cercanas marcandolas explicitamente como 'fuera de presupuesto' "
                "y enumera las acciones sugeridas para reajustar el viaje."
            )
        else:
            extra_vh = (
                "No hay datos suficientes de vuelos u hoteles. Indicalo con honestidad "
                "y sugiere reintentar la busqueda."
            )
    else:
        extra_vh = "No incluyas busqueda de vuelos/hoteles en esta respuesta."

    prompt_final = (
        "Actua como supervisor de un sistema multiagente de viajes. "
        "Fusiona la informacion de workers en una respuesta unica, clara y accionable.\n\n"
        f"Ciudad: {state['ciudad']}\n"
        f"Contexto del viaje: {state.get('contexto_viaje') or 'Sin contexto adicional'}\n"
        f"Objetivo del usuario: {state.get('objetivo_usuario') or 'Plan general de visita'}\n"
        f"Presupuesto total EUR: {state.get('presupuesto_total_eur') or 0}\n"
        f"Fecha inicio: {state.get('fecha_inicio') or 'No informada'}\n"
        f"Fecha fin: {state.get('fecha_fin') or 'No informada'}\n"
        f"Modo planificacion: {state.get('modo_planificacion')}\n"
        f"Motivo de enrutado: {state.get('motivo_ruta')}\n\n"
        f"[Entrada agente clima]\n{entrada_clima}\n\n"
        f"[Entrada agente turistico]\n{state.get('propuesta_turistica', '')}\n\n"
        f"[Entrada agente vuelos]\n{entrada_vuelos}\n\n"
        f"[Entrada agente hoteles]\n{entrada_hoteles}\n\n"
        f"[Combinaciones validas (dentro de presupuesto)]\n{combos_validos}\n\n"
        f"[Combinaciones excluidas por presupuesto]\n{combos_excluidos}\n\n"
        f"[Auditoria presupuestaria]\n{auditoria}\n\n"
        f"[Acciones sugeridas si el presupuesto no encaja]\n{acciones}\n\n"
        f"Instruccion clave: {extra}\n\n"
        f"Instruccion vuelos/hoteles: {extra_vh}\n\n"
        "Estructura de salida en Markdown:\n"
        "1) Resumen ejecutivo del plan\n"
        "2) Opciones de vuelo y hotel para elegir (etiqueta cada bloque si esta fuera de presupuesto)\n"
        "3) Plan practico del viaje por bloques\n"
        "4) Recomendaciones clave (ropa solo si aplica)\n"
        "5) Siguientes pasos (incluyendo acciones sugeridas si el presupuesto no encaja)"
    )

    logger.info("synth | generando respuesta final con LLM (decision=%s)", decision)
    model, respuesta_final = invoke_with_fallback(
        [
            SystemMessage(
                content=(
                    "Eres el supervisor final. No inventes datos meteo nuevos ni precios: "
                    "usa solo las entradas de workers."
                )
            ),
            HumanMessage(content=prompt_final),
        ]
    )

    rendered = (
        f"[Supervisor LLM: {model}]\n"
        f"[Modo: {state.get('modo_planificacion')}]\n"
        f"[Routing: {state.get('motivo_ruta')}]\n\n"
        f"{respuesta_final}"
    )
    logger.info("synth | completado con modelo=%s", model)
    return {"respuesta_final": rendered, "supervisor_modelo": model}


def _route_after_router(state: SupervisorState) -> str:
    if state.get("usar_turismo", True):
        return "tourism"
    if state.get("usar_vuelos_hoteles"):
        return "fetch"
    return "weather" if state.get("usar_clima") else "synth"


def _route_after_tourism(state: SupervisorState) -> str:
    if state.get("usar_vuelos_hoteles"):
        return "fetch"
    return "weather" if state.get("usar_clima") else "synth"


def _route_after_budget(state: SupervisorState) -> str:
    return "weather" if state.get("usar_clima") else "synth"


def _build_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("router", _router_node)
    graph.add_node("tourism", _tourism_node)
    # fetch es un nodo pass-through que dispara flights y hotels en paralelo
    graph.add_node("fetch", _fetch_node)
    graph.add_node("flights", _flights_node)
    graph.add_node("hotels", _hotels_node)
    graph.add_node("budget", _budget_node)
    graph.add_node("weather", _weather_node)
    graph.add_node("synth", _synth_node)

    graph.add_edge(START, "router")

    # Bifurcacion tras router: turismo (defecto) o saltar directo si solo precios
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {"tourism": "tourism", "fetch": "fetch", "weather": "weather", "synth": "synth"},
    )

    # Bifurcacion tras turismo: fetch (vuelos+hoteles) | weather | synth
    graph.add_conditional_edges(
        "tourism",
        _route_after_tourism,
        {"fetch": "fetch", "weather": "weather", "synth": "synth"},
    )

    # Fan-out paralelo: fetch lanza flights y hotels simultaneamente
    graph.add_edge("fetch", "flights")
    graph.add_edge("fetch", "hotels")

    # Fan-in: budget espera a que terminen ambos branches
    graph.add_edge("flights", "budget")
    graph.add_edge("hotels", "budget")

    # Bifurcacion tras presupuesto: con o sin clima
    graph.add_conditional_edges(
        "budget",
        _route_after_budget,
        {"weather": "weather", "synth": "synth"},
    )
    graph.add_edge("weather", "synth")
    graph.add_edge("synth", END)
    return graph.compile()

#Al ejecutar el archivo se ejecuta esta linea global
SUPERVISOR_GRAPH = _build_graph()


def run_supervisor_structured(
    ciudad: str,
    contexto_viaje: str = "",
    objetivo_usuario: str = "",
    fecha_inicio: str = "",
    fecha_fin: str = "",
    origen_iata: str = "MAD",
    destino_iata: str = "",
    presupuesto_total_eur: float = 0,
    adultos: int = 2,
) -> dict[str, Any]:
    """RF-13: devuelve la propuesta de viaje como payload estructurado.

    Util para frontends (Streamlit/Gradio) y para tests automatizados.
    El campo `respuesta_markdown` contiene la sintesis final del LLM lista
    para renderizar al usuario.
    """
    final_state = SUPERVISOR_GRAPH.invoke(
        {
            "ciudad": ciudad,
            "contexto_viaje": contexto_viaje,
            "objetivo_usuario": objetivo_usuario,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "origen_iata": origen_iata,
            "destino_iata": destino_iata,
            "presupuesto_total_eur": presupuesto_total_eur,
            "adultos": adultos,
        }
    )

    return {
        "contexto": {
            "ciudad": ciudad,
            "origen_iata": origen_iata,
            "destino_iata": final_state.get("destino_iata") or destino_iata,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "presupuesto_total_eur": presupuesto_total_eur,
            "adultos": adultos,
        },
        "routing": {
            "modo_planificacion": final_state.get("modo_planificacion"),
            "horizonte_dias": final_state.get("horizonte_dias"),
            "usar_clima": final_state.get("usar_clima"),
            "usar_vuelos_hoteles": final_state.get("usar_vuelos_hoteles"),
            "usar_turismo": final_state.get("usar_turismo", True),
            "motivo_ruta": final_state.get("motivo_ruta"),
        },
        "turismo": final_state.get("propuesta_turistica", ""),
        "clima": {
            "consultado": bool(final_state.get("usar_clima")),
            "reporte": final_state.get("reporte_clima", ""),
        },
        "vuelos": final_state.get("opciones_vuelos", []),
        "hoteles": final_state.get("opciones_hoteles", []),
        "presupuesto": {
            "auditoria": final_state.get("auditoria_presupuesto", {}),
            "combinaciones_validas": final_state.get("combinaciones_presupuesto", []),
            "combinaciones_excluidas": final_state.get("combinaciones_excluidas", []),
            "acciones_sugeridas": final_state.get("acciones_sugeridas", []),
        },
        "supervisor_modelo": final_state.get("supervisor_modelo"),
        "respuesta_markdown": final_state["respuesta_final"],
    }


def run_supervisor(
    ciudad: str,
    contexto_viaje: str = "",
    objetivo_usuario: str = "",
    fecha_inicio: str = "",
    fecha_fin: str = "",
    origen_iata: str = "MAD",
    destino_iata: str = "",
    presupuesto_total_eur: float = 0,
    adultos: int = 2,
) -> str:
    """Versión retrocompatible: devuelve solo el Markdown final del supervisor."""
    payload = run_supervisor_structured(
        ciudad,
        contexto_viaje,
        objetivo_usuario,
        fecha_inicio,
        fecha_fin,
        origen_iata,
        destino_iata,
        presupuesto_total_eur,
        adultos,
    )
    return payload["respuesta_markdown"]


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Supervisor de viajes multiagente")
    parser.add_argument("ciudad", help="Ciudad destino (ej. Roma)")
    parser.add_argument("--contexto", default="", help="Contexto del viaje")
    parser.add_argument("--objetivo", default="", help="Objetivo del usuario")
    parser.add_argument("--fecha-inicio", default="", dest="fecha_inicio", metavar="YYYY-MM-DD")
    parser.add_argument("--fecha-fin", default="", dest="fecha_fin", metavar="YYYY-MM-DD")
    parser.add_argument("--origen", default="MAD", dest="origen_iata", help="IATA origen")
    parser.add_argument("--destino-iata", default="", dest="destino_iata", help="IATA destino")
    parser.add_argument("--presupuesto", type=float, default=0.0, dest="presupuesto", metavar="EUR")
    parser.add_argument("--adultos", type=int, default=2)
    args = parser.parse_args()

    print("\n--- RESPUESTA FINAL DEL SUPERVISOR ---")
    print(
        run_supervisor(
            args.ciudad,
            args.contexto,
            args.objetivo,
            args.fecha_inicio,
            args.fecha_fin,
            args.origen_iata,
            args.destino_iata,
            args.presupuesto,
            args.adultos,
        )
    )
