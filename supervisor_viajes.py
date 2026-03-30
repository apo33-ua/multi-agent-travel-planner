from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agente_clima import run_climate_agent
from agente_hoteles import search_hotels
from agente_turistico import run_tourism_agent
from agente_vuelos import search_flights
from llm_gemini import invoke_with_fallback


SHORT_TERM_DAYS = 14


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
    motivo_ruta: str
    reporte_clima: str
    propuesta_turistica: str
    opciones_vuelos: list[dict[str, Any]]
    opciones_hoteles: list[dict[str, Any]]
    combinaciones_presupuesto: list[dict[str, Any]]
    respuesta_final: str


CITY_TO_IATA = {
    "roma": "FCO",
    "londres": "LON",
    "oslo": "OSL",
    "madrid": "MAD",
    "paris": "PAR",
    "barcelona": "BCN",
}


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
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace("\u00a0", " ")
        cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^0-9.]", "", cleaned)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _resolve_destination_iata(ciudad: str, destino_iata: str) -> str:
    if destino_iata.strip():
        return destino_iata.strip().upper()
    return CITY_TO_IATA.get(ciudad.strip().lower(), ciudad[:3].upper())


def _needs_flights_hotels(state: SupervisorState) -> bool:
    text = (
        f"{state.get('contexto_viaje', '')} "
        f"{state.get('objetivo_usuario', '')}"
    ).lower()
    budget = state.get("presupuesto_total_eur", 0) or 0

    keywords = ["presupuesto", "vuelo", "hotel", "alojamiento", "organizar", "planificar"]
    return budget > 0 or any(word in text for word in keywords)


def _build_budget_combinations(
    vuelos: list[dict[str, Any]],
    hoteles: list[dict[str, Any]],
    presupuesto: float,
) -> list[dict[str, Any]]:
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
            combos.append(
                {
                    "airline": vuelo.get("airline", "N/D"),
                    "flight_price": round(precio_vuelo, 2),
                    "hotel_name": hotel.get("name", "N/D"),
                    "hotel_total": round(precio_hotel, 2),
                    "total_estimated": round(total, 2),
                    "fits_budget": total <= presupuesto,
                    "budget_gap": round(presupuesto - total, 2),
                }
            )

    under = [c for c in combos if c["fits_budget"]]
    if under:
        under.sort(key=lambda c: c["total_estimated"])
        return under[:5]

    combos.sort(key=lambda c: c["total_estimated"])
    return combos[:5]


def _router_node(state: SupervisorState) -> dict[str, Any]:
    inicio = _parse_iso_date(state.get("fecha_inicio"))
    horizon: int | None = None

    if inicio is not None:
        horizon = (inicio - date.today()).days

    needs_plan = _needs_flights_hotels(state)

    if inicio is None:
        return {
            "horizonte_dias": None,
            "modo_planificacion": "sin-fecha",
            "usar_clima": True,
            "usar_vuelos_hoteles": needs_plan,
            "motivo_ruta": (
                "No hay fecha de inicio: se asume plan cercano y se incluye clima actual. "
                f"Vuelos/hoteles {'activados' if needs_plan else 'no activados'} por intencion."
            ),
        }

    if horizon <= SHORT_TERM_DAYS:
        return {
            "horizonte_dias": horizon,
            "modo_planificacion": "corto-plazo",
            "usar_clima": True,
            "usar_vuelos_hoteles": needs_plan,
            "motivo_ruta": (
                f"Viaje en {horizon} dias: se activa clima. "
                f"Vuelos/hoteles {'activados' if needs_plan else 'no activados'} por intencion."
            ),
        }

    return {
        "horizonte_dias": horizon,
        "modo_planificacion": "anticipado",
        "usar_clima": False,
        "usar_vuelos_hoteles": True,
        "motivo_ruta": (
            f"Viaje en {horizon} dias: se omite clima actual y se prioriza planificacion "
            "(vuelos/hotel/itinerario base)."
        ),
    }


def _tourism_node(state: SupervisorState) -> dict[str, Any]:
    return {
        "propuesta_turistica": run_tourism_agent(
            state["ciudad"],
            state.get("contexto_viaje", ""),
        )
    }


def _weather_node(state: SupervisorState) -> dict[str, Any]:
    return {
        "reporte_clima": run_climate_agent(
            state["ciudad"],
            state.get("fecha_inicio", ""),
        )
    }


def _flights_node(state: SupervisorState) -> dict[str, Any]:
    fecha_inicio = state.get("fecha_inicio", "").strip()
    fecha_fin = state.get("fecha_fin", "").strip()
    if not fecha_inicio:
        return {
            "opciones_vuelos": [],
        }

    origen = (state.get("origen_iata", "MAD") or "MAD").upper()
    destino = _resolve_destination_iata(state["ciudad"], state.get("destino_iata", ""))
    adultos = int(state.get("adultos", 2) or 2)

    try:
        result = search_flights(origen, destino, fecha_inicio, fecha_fin, adultos)
        return {"opciones_vuelos": result.get("options", [])}
    except Exception as exc:
        return {"opciones_vuelos": [{"error": str(exc)}]}


def _hotels_node(state: SupervisorState) -> dict[str, Any]:
    fecha_inicio = state.get("fecha_inicio", "").strip()
    fecha_fin = state.get("fecha_fin", "").strip()
    if not (fecha_inicio and fecha_fin):
        return {
            "opciones_hoteles": [],
        }

    adultos = int(state.get("adultos", 2) or 2)
    try:
        result = search_hotels(state["ciudad"], fecha_inicio, fecha_fin, adultos)
        return {"opciones_hoteles": result.get("options", [])}
    except Exception as exc:
        return {"opciones_hoteles": [{"error": str(exc)}]}


def _budget_node(state: SupervisorState) -> dict[str, Any]:
    presupuesto = float(state.get("presupuesto_total_eur", 0) or 0)
    vuelos = state.get("opciones_vuelos", [])
    hoteles = state.get("opciones_hoteles", [])

    if presupuesto <= 0 or not vuelos or not hoteles:
        return {"combinaciones_presupuesto": []}

    combos = _build_budget_combinations(vuelos, hoteles, presupuesto)
    return {"combinaciones_presupuesto": combos}


def _synth_node(state: SupervisorState) -> dict[str, Any]:
    usa_clima = state.get("usar_clima", False)
    usa_vh = state.get("usar_vuelos_hoteles", False)
    entrada_clima = state.get("reporte_clima", "No consultado en modo anticipado.")
    entrada_vuelos = state.get("opciones_vuelos", [])
    entrada_hoteles = state.get("opciones_hoteles", [])
    entrada_combos = state.get("combinaciones_presupuesto", [])

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
        extra_vh = (
            "Prioriza presentar opciones de vuelos y hoteles, y combina precios con el presupuesto. "
            "Si no hay combinaciones dentro del presupuesto, muestra las mas cercanas."
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
        f"[Combinaciones vuelo+hotel con presupuesto]\n{entrada_combos}\n\n"
        f"Instruccion clave: {extra}\n\n"
        f"Instruccion vuelos/hoteles: {extra_vh}\n\n"
        "Estructura de salida:\n"
        "1) Resumen ejecutivo del plan\n"
        "2) Opciones de vuelo y hotel para elegir\n"
        "3) Plan practico del viaje por bloques\n"
        "4) Recomendaciones clave (ropa solo si aplica)\n"
        "5) Siguientes pasos"
    )

    model, respuesta_final = invoke_with_fallback(
        [
            SystemMessage(
                content=(
                    "Eres el supervisor final. No inventes datos meteo nuevos: "
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
        f"{respuesta_final}\n\n"
        "---\n"
        "[Debug workers]\n"
        f"- Clima consultado: {'si' if usa_clima else 'no'}\n"
        f"- Vuelos/hoteles consultados: {'si' if usa_vh else 'no'}\n"
        f"- Clima: {entrada_clima}\n"
    )
    return {"respuesta_final": rendered}


def _route_after_tourism(state: SupervisorState) -> str:
    return "flights" if state.get("usar_vuelos_hoteles") else (
        "weather" if state.get("usar_clima") else "synth"
    )


def _route_after_hotels(state: SupervisorState) -> str:
    return "weather" if state.get("usar_clima") else "synth"


def _build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("router", _router_node)
    graph.add_node("tourism", _tourism_node)
    graph.add_node("flights", _flights_node)
    graph.add_node("hotels", _hotels_node)
    graph.add_node("budget", _budget_node)
    graph.add_node("weather", _weather_node)
    graph.add_node("synth", _synth_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "tourism")
    graph.add_conditional_edges(
        "tourism",
        _route_after_tourism,
        {
            "flights": "flights",
            "weather": "weather",
            "synth": "synth",
        },
    )
    graph.add_edge("flights", "hotels")
    graph.add_edge("hotels", "budget")
    graph.add_conditional_edges(
        "budget",
        _route_after_hotels,
        {
            "weather": "weather",
            "synth": "synth",
        },
    )
    graph.add_edge("weather", "synth")
    graph.add_edge("synth", END)
    return graph.compile()


SUPERVISOR_GRAPH = _build_graph()


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
    """
    Supervisor con enrutado dinamico (LangGraph):
    - Si el viaje esta cercano, llama a clima + turismo.
    - Si el viaje esta lejano, llama solo a turismo y deja replan meteo.
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
    return final_state["respuesta_final"]


if __name__ == "__main__":
    print("Iniciando supervisor de viajes...\n")

    ciudad = input("Ciudad destino: ").strip()
    contexto = input("Contexto del viaje (opcional): ").strip()
    objetivo = input("Objetivo del usuario (opcional): ").strip()
    fecha_inicio = input("Fecha inicio (YYYY-MM-DD, opcional): ").strip()
    fecha_fin = input("Fecha fin (YYYY-MM-DD, opcional): ").strip()
    origen_iata = input("Origen IATA (opcional, por defecto MAD): ").strip() or "MAD"
    destino_iata = input("Destino IATA (opcional, ej FCO): ").strip()
    presupuesto_raw = input("Presupuesto total EUR (opcional, ej 500): ").strip()
    adultos_raw = input("Numero de adultos (opcional, por defecto 2): ").strip()

    if not ciudad:
        raise SystemExit("Debes indicar una ciudad.")

    presupuesto_total_eur = float(presupuesto_raw) if presupuesto_raw else 0.0
    adultos = int(adultos_raw) if adultos_raw else 2

    print("\n--- RESPUESTA FINAL DEL SUPERVISOR ---")
    print(
        run_supervisor(
            ciudad,
            contexto,
            objetivo,
            fecha_inicio,
            fecha_fin,
            origen_iata,
            destino_iata,
            presupuesto_total_eur,
            adultos,
        )
    )
