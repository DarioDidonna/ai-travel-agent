import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from travel_agent_api.routes import chat_router

DEFAULT_CORS_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
STATIC_DIR = Path(__file__).parent / "static"

# Solo file del sito; le immagini degli hotel arrivano da Google (https)
CHAT_PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


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



@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


app.include_router(
    chat_router.router,
    tags=["Chat"],
    prefix="/chat"
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def chat_page() -> FileResponse:
    """Pagina di chat per provare l'agente dal browser."""
    return FileResponse(STATIC_DIR / "index.html", headers={"Content-Security-Policy": CHAT_PAGE_CSP})
