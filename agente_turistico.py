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
            #Define comportamiento general del asistente
            SystemMessage(
                content=(
                    "Eres un experto en turismo urbano. Priorizas lugares reales, "
                    "bien conocidos y utiles para un itinerario corto."
                )
            ),
            #Prompt detallado con instrucciones y contexto
            HumanMessage(content=prompt),
        ]
    )
    return f"[LLM activo: {model}]\n\n{content}"


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Agente turistico")
    parser.add_argument("ciudad", help="Ciudad destino (ej. Roma)")
    parser.add_argument("--contexto", default="", help="Contexto del viaje")
    args = parser.parse_args()

    print("\n--- PROPUESTA TURISTICA ---")
    print(run_tourism_agent(args.ciudad, args.contexto))
