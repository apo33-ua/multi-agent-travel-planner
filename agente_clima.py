import os
from typing import List, Tuple

import requests
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from google.genai.errors import APIError as GeminiAPIError

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {var_name}. "
            f"Definela antes de ejecutar el script."
        )
    return value


def fetch_weather_data(ciudad: str, openweather_api_key: str) -> dict:
    params = {
        "q": ciudad,
        "appid": openweather_api_key,
        "units": "metric",
        "lang": "es",
    }

    try:
        response = requests.get(OPENWEATHER_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"No se pudo obtener el clima de {ciudad} desde OpenWeather: {exc}"
        ) from exc

    data = response.json()
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})

    return {
        "ciudad": data.get("name", ciudad),
        "descripcion": weather.get("description", "sin descripcion"),
        "temp": main.get("temp", "N/D"),
        "feels_like": main.get("feels_like", "N/D"),
        "humedad": main.get("humidity", "N/D"),
        "viento": wind.get("speed", "N/D"),
    }


def weather_summary(weather_data: dict) -> str:
    return (
        f"Clima actual en {weather_data['ciudad']}: {weather_data['descripcion']}. "
        f"Temperatura {weather_data['temp']}C, sensacion termica {weather_data['feels_like']}C, "
        f"humedad {weather_data['humedad']}%, viento {weather_data['viento']} m/s."
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float))


def fallback_recommendations(weather_data: dict, contexto_viaje: str) -> str:
    temp = weather_data.get("temp")
    desc = str(weather_data.get("descripcion", "")).lower()

    ropa = []
    actividades = []

    if _is_number(temp):
        if temp < 10:
            ropa.extend(["Abrigo", "Jersey", "Bufanda", "Guantes", "Calzado cerrado"])
            actividades.extend(["Museos", "Cafeterias historicas", "Rutas cortas por interiores"])
        elif temp < 20:
            ropa.extend(["Chaqueta ligera", "Camiseta de manga larga", "Pantalon comodo", "Zapatillas"])
            actividades.extend(["Walking tour", "Monumentos", "Mercados locales"])
        else:
            ropa.extend(["Camiseta transpirable", "Pantalon corto", "Gorra", "Gafas de sol", "Agua reutilizable"])
            actividades.extend(["Parques", "Miradores", "Terrazas al aire libre"])
    else:
        ropa.extend(["Capas ligeras", "Chaqueta fina", "Zapatillas comodas"])
        actividades.extend(["Centro historico", "Museos", "Gastronomia local"])

    if "lluv" in desc or "rain" in desc:
        ropa.extend(["Paraguas", "Impermeable"])
        actividades = ["Museos", "Galerias", "Mercados cubiertos"]

    alternativas_lluvia = [
        "Visitar un museo principal de la ciudad",
        "Hacer ruta gastronomica en zonas cubiertas",
    ]
    ropa_unica = list(dict.fromkeys(ropa))
    actividades_unicas = list(dict.fromkeys(actividades))[:3]

    contexto_texto = contexto_viaje or "Sin contexto adicional"
    return (
        "[Modo sin LLM: recomendacion basada en reglas por falta de cuota en Gemini]\n"
        f"Contexto: {contexto_texto}\n\n"
        "1) Ropa recomendada\n"
        + "\n".join(f"- {item}" for item in ropa_unica)
        + "\n\n2) Actividades adecuadas\n"
        + "\n".join(f"- {item}" for item in actividades_unicas)
        + "\n\n3) Alternativas si llueve\n"
        + "\n".join(f"- {item}" for item in alternativas_lluvia)
        + "\n\n4) Consejo de seguridad\n"
        + "- Revisa el pronostico unas horas antes de salir y lleva siempre una capa extra."
    )


def build_llm(model_name: str | None = None) -> ChatGoogleGenerativeAI:
    _require_env("GOOGLE_API_KEY")
    preferred_model = os.getenv("GEMINI_MODEL")
    timeout_seconds = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    retries = int(os.getenv("GEMINI_RETRIES", "0"))

    return ChatGoogleGenerativeAI(
        model=model_name or preferred_model or "gemini-2.5-flash",
        request_timeout=timeout_seconds,
        retries=retries,
    )


def _candidate_models() -> List[str]:
    preferred_model = os.getenv("GEMINI_MODEL")
    env_candidates = os.getenv("GEMINI_MODEL_CANDIDATES", "").strip()
    if env_candidates:
        models = [item.strip() for item in env_candidates.split(",") if item.strip()]
    else:
        models = [
            preferred_model,
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
        ]
    dedup = []
    for model in models:
        if model and model not in dedup:
            dedup.append(model)
    return dedup


def build_gemini_diagnosis(errors: List[str]) -> str:
    joined = " ".join(errors)
    if "RESOURCE_EXHAUSTED" in joined or "Quota exceeded" in joined:
        return (
            "Diagnostico: la API key es valida, pero el proyecto asociado no tiene cuota disponible "
            "para los modelos intentados (429 RESOURCE_EXHAUSTED). "
            "Suele pasar cuando no hay billing activo en Google AI Studio/Google Cloud, "
            "o cuando se alcanzo el limite diario/minuto."
        )
    if "NOT_FOUND" in joined:
        return (
            "Diagnostico: el nombre del modelo no esta habilitado para tu endpoint/version. "
            "Define GEMINI_MODEL con un modelo disponible en tu proyecto."
        )
    if "DEADLINE_EXCEEDED" in joined or "timed out" in joined.lower():
        return (
            "Diagnostico: el endpoint de Gemini no respondio a tiempo (504). "
            "Suele resolverse subiendo GEMINI_TIMEOUT_SECONDS o usando un modelo mas ligero."
        )
    return "Diagnostico: error de conexion o configuracion con Gemini API."


def run_climate_travel_flow(
    ciudad: str,
    contexto_viaje: str = "",
) -> Tuple[str, str]:
    """
    Flujo multi-agente minimo:
    1) Agente de clima (ReAct + herramienta OpenWeather).
    2) Agente recomendador (Gemini) que genera ropa + actividades.
    """
    openweather_api_key = _require_env("OPENWEATHER_API_KEY")
    weather_data = fetch_weather_data(ciudad, openweather_api_key)
    resumen_clima = weather_summary(weather_data)
    errors = []

    for model_name in _candidate_models():
        llm = build_llm(model_name)

        try:
            recommendation_prompt = (
                "Actua como agente planificador de viajes. "
                "Con el reporte de clima, recomienda ropa concreta y actividades.\n\n"
                f"Ciudad: {ciudad}\n"
                f"Contexto del viaje: {contexto_viaje or 'Sin contexto adicional'}\n"
                f"Reporte de clima: {resumen_clima}\n\n"
                "Devuelve:\n"
                "1) Lista de ropa recomendada (5-8 items)\n"
                "2) 3 actividades adecuadas al clima\n"
                "3) 2 actividades alternativas si llueve\n"
                "4) Un consejo breve de seguridad"
            )

            recommendation_response = llm.invoke(
                [
                    SystemMessage(
                        content="Eres un experto en viajes. Se claro, util y evita inventar datos que no se derivan del clima."
                    ),
                    HumanMessage(content=recommendation_prompt),
                ]
            )

            enriched = (
                f"[LLM activo: {model_name}]\n\n"
                f"{recommendation_response.content}"
            )
            return resumen_clima, enriched
        except (ChatGoogleGenerativeAIError, GeminiAPIError, TimeoutError, ConnectionError) as exc:
            message = str(exc)
            if "DEADLINE_EXCEEDED" in message or "timed out" in message.lower():
                # Reintento puntual en timeouts con timeout mayor.
                try:
                    llm_retry = ChatGoogleGenerativeAI(
                        model=model_name,
                        request_timeout=max(float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30")), 45.0),
                        retries=0,
                    )
                    recommendation_response = llm_retry.invoke(
                        [
                            SystemMessage(
                                content="Eres un experto en viajes. Se claro, util y evita inventar datos que no se derivan del clima."
                            ),
                            HumanMessage(content=recommendation_prompt),
                        ]
                    )
                    enriched = (
                        f"[LLM activo: {model_name}]\n\n"
                        f"{recommendation_response.content}"
                    )
                    return resumen_clima, enriched
                except Exception as retry_exc:
                    errors.append(f"{model_name} (retry-timeout): {retry_exc}")
            errors.append(f"{model_name}: {exc}")
        except Exception as exc:
            errors.append(f"{model_name}: {exc}")

    # Fallback robusto para no bloquear la demo cuando Gemini no tiene cuota.
    fallback = fallback_recommendations(weather_data, contexto_viaje)
    fallback += "\n\n" + build_gemini_diagnosis(errors)
    fallback += "\n\nErrores Gemini detectados:\n" + "\n".join(f"- {e}" for e in errors)
    return resumen_clima, fallback


if __name__ == "__main__":
    print("Iniciando modulo de clima para el planificador multi-agente...\n")

    ciudad = input("Ciudad destino: ").strip()
    contexto = input("Contexto del viaje (opcional): ").strip()

    if not ciudad:
        raise SystemExit("Debes indicar una ciudad.")

    clima, recomendaciones = run_climate_travel_flow(ciudad, contexto)

    print("\n--- REPORTE DE CLIMA ---")
    print(clima)
    print("\n--- ROPA Y ACTIVIDADES RECOMENDADAS ---")
    print(recomendaciones)