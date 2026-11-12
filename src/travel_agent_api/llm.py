import os
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv()

# Si sceglie con LLM_PROVIDER nel .env
DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "ollama": "qwen3:4b",
    "openai": "gpt-4o",
}

# Modelli leggeri per i tool interni (itinerario, storia). Su Gemini hanno una
# quota gratuita separata, così il modello principale resta per l'agente
DEFAULT_LIGHT_MODELS = {
    "gemini": "gemini-flash-lite-latest",
    "ollama": "qwen3:4b",
    "openai": "gpt-4o-mini",
}


def get_chat_model(light: bool = False) -> BaseChatModel:
    """
    Restituisce il modello di chat configurato nel .env.

    Args:
        light: se True restituisce il modello leggero, usato dai tool interni.

    Variabili:
        LLM_PROVIDER: gemini (default), ollama oppure openai.
        LLM_MODEL: modello principale; se assente usa quello predefinito del provider.
        LLM_LIGHT_MODEL: modello leggero; se assente usa quello predefinito del provider.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"LLM_PROVIDER non valido: {provider}. Usa uno tra {list(DEFAULT_MODELS)}")

    if light:
        model = os.getenv("LLM_LIGHT_MODEL", DEFAULT_LIGHT_MODELS[provider])
    else:
        model = os.getenv("LLM_MODEL", DEFAULT_MODELS[provider])

    if provider == "gemini":
        # Connettore nativo: gestisce le "thought signature" richieste da Gemini 3
        return ChatGoogleGenerativeAI(
            model=model,
            api_key=os.getenv("GEMINI_API_KEY"),
            timeout=120,
        )

    if provider == "ollama":
        # Ollama espone un'API compatibile con OpenAI e non richiede una chiave
        return ChatOpenAI(
            model=model,
            api_key="ollama",
            base_url="http://localhost:11434/v1",
            timeout=120,
        )

    return ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), timeout=120)
