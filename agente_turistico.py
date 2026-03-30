from langchain_core.messages import HumanMessage, SystemMessage

from llm_gemini import invoke_with_fallback


def run_tourism_agent(ciudad: str, contexto_viaje: str = "") -> str:
    """Agente turistico/cultural: solo monumentos, rutas y propuestas de visita."""
    prompt = (
        "Eres un agente turistico y cultural especializado. "
        "No hables de clima ni ropa; eso lo resuelve otro agente.\n\n"
        f"Ciudad: {ciudad}\n"
        f"Contexto del viaje: {contexto_viaje or 'Sin contexto adicional'}\n\n"
        "Devuelve en espanol:\n"
        "1) 5 monumentos/lugares imprescindibles\n"
        "2) Ruta sugerida de medio dia\n"
        "3) 3 zonas recomendadas para comer\n"
        "4) 2 consejos culturales/practicos"
    )

    model, content = invoke_with_fallback(
        [
            SystemMessage(
                content=(
                    "Eres un experto en turismo urbano. Priorizas lugares reales, "
                    "bien conocidos y utiles para un itinerario corto."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    return f"[LLM activo: {model}]\n\n{content}"


if __name__ == "__main__":
    ciudad = input("Ciudad destino: ").strip()
    contexto = input("Contexto del viaje (opcional): ").strip()

    if not ciudad:
        raise SystemExit("Debes indicar una ciudad.")

    print("\n--- PROPUESTA TURISTICA ---")
    print(run_tourism_agent(ciudad, contexto))
