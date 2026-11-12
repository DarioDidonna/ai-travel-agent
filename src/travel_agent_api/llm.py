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


def get_chat_model() -> BaseChatModel:
    """
    Restituisce il modello di chat configurato nel .env.

    Variabili:
        LLM_PROVIDER: gemini (default), ollama oppure openai.
        LLM_MODEL: nome del modello; se assente usa quello predefinito del provider.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"LLM_PROVIDER non valido: {provider}. Usa uno tra {list(DEFAULT_MODELS)}")

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
