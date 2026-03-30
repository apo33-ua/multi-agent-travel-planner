import os
from typing import List, Sequence, Tuple

from google.genai.errors import APIError as GeminiAPIError
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError


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
    retries = int(os.getenv("GEMINI_RETRIES", "0"))
    return ChatGoogleGenerativeAI(
        model=model_name,
        request_timeout=timeout_seconds,
        retries=retries,
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


def invoke_with_fallback(messages: Sequence[BaseMessage]) -> Tuple[str, str]:
    errors = []
    for model_name in candidate_models():
        llm = build_llm(model_name)
        try:
            response = llm.invoke(list(messages))
            return model_name, response.content
        except (ChatGoogleGenerativeAIError, GeminiAPIError, TimeoutError, ConnectionError) as exc:
            errors.append(f"{model_name}: {exc}")
        except Exception as exc:
            errors.append(f"{model_name}: {exc}")

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
