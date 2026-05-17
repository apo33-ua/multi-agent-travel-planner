import os
import time
from typing import List, Sequence, Tuple

from google.genai.errors import APIError as GeminiAPIError
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langsmith import traceable

# Errores que justifican reintentar el mismo modelo antes de saltar al siguiente
_TRANSIENT_HINTS = ("503", "429", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "Deadline", "DEADLINE_EXCEEDED")


def require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno {var_name}. Definela antes de ejecutar."
        )
    return value


def build_llm(model_name: str) -> ChatGoogleGenerativeAI:
    require_env("GOOGLE_API_KEY")
    timeout_seconds = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
    return ChatGoogleGenerativeAI(
        model=model_name,
        request_timeout=timeout_seconds,
    )


def candidate_models() -> List[str]:
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

    unique: List[str] = []
    for model in models:
        if model and model not in unique:
            unique.append(model)
    return unique


def _is_transient(exc: Exception) -> bool:
    text = str(exc)
    return any(hint in text for hint in _TRANSIENT_HINTS)


@traceable(name="invoke_with_fallback", run_type="llm")
def invoke_with_fallback(messages: Sequence[BaseMessage]) -> Tuple[str, str]:
    """Invoca Gemini con doble capa de resiliencia:
    1) Reintentos con backoff exponencial sobre el mismo modelo ante errores transitorios.
    2) Fallback en cascada al siguiente modelo candidato si la lista de reintentos se agota.
    Decorado con @traceable para trazabilidad en LangSmith (activo si LANGCHAIN_TRACING_V2=true).
    """
    # GEMINI_RETRIES=0 significa "sin reintentos" → 1 intento total
    max_attempts = max(1, int(os.getenv("GEMINI_RETRIES", "3")))
    base_delay = float(os.getenv("GEMINI_BACKOFF_BASE_SECONDS", "1.5"))
    errors: list[str] = []

    for model_name in candidate_models():
        llm = build_llm(model_name)
        for attempt in range(1, max_attempts + 1):
            try:
                response = llm.invoke(list(messages))
                return model_name, response.content
            except (ChatGoogleGenerativeAIError, GeminiAPIError, TimeoutError, ConnectionError) as exc:
                errors.append(f"{model_name} intento {attempt}: {exc}")
                # Solo aplica backoff si es transitorio y aun quedan intentos
                if attempt < max_attempts and _is_transient(exc):
                    time.sleep(base_delay * (2 ** (attempt - 1)))
                    continue
                break  # error no transitorio o intentos agotados -> siguiente modelo
            except Exception as exc:
                errors.append(f"{model_name} intento {attempt}: {exc}")
                break

    combined_errors = " | ".join(errors)
    if "API_KEY_INVALID" in combined_errors or "API Key not found" in combined_errors:
        raise RuntimeError(
            "Gemini rechazo la API key (API_KEY_INVALID). "
            "Abre una terminal nueva o ejecuta 'source ~/.zshrc' y verifica GOOGLE_API_KEY. "
            f"Detalle: {combined_errors}"
        )

    raise RuntimeError(
        "No se pudo obtener respuesta del LLM con ningun modelo candidato. "
        f"Errores: {combined_errors}"
    )
