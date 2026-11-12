import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from travel_agent_api.routes import chat_router

DEFAULT_CORS_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"


def get_cors_origins() -> list[str]:
    """Origini autorizzate a chiamare l'API dal browser: CORS_ORIGINS nel .env, separate da virgole."""
    value = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(
    title="Travel Agent API",
    description="Agente AI che organizza viaggi: cerca voli e hotel reali e crea itinerari.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    # L'API non usa cookie: le credenziali viaggiano nell'header X-API-Key
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(
    chat_router.router,
    tags=["Chat"],
    prefix="/chat"
)

