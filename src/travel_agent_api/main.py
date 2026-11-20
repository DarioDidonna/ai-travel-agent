import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from travel_agent_api.routes import chat_router
from travel_agent_api.security import is_production, validate_settings

# I log dell'app (durata dei tool, errori dei servizi esterni) nello stesso formato di uvicorn
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:     %(name)s - %(message)s",
)

DEFAULT_CORS_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
STATIC_DIR = Path(__file__).parent / "static"

# 30 messaggi da 4000 caratteri stanno ampiamente sotto questo limite
MAX_BODY_BYTES = 512 * 1024
DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}

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


class MaxBodySizeMiddleware:
    """
    Rifiuta con 413 i body oltre max_bytes. Conta i byte davvero ricevuti, quindi
    non si aggira omettendo o falsificando l'header Content-Length.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        too_large = HTTPException(status_code=413, detail="Richiesta troppo grande.")
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await JSONResponse({"detail": too_large.detail}, status_code=413)(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise too_large
            return message

        await self.app(scope, limited_receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_settings()
    yield


app = FastAPI(
    title="Travel Agent API",
    description="Agente AI che organizza viaggi: cerca voli e hotel reali e crea itinerari.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(MaxBodySizeMiddleware, max_bytes=MAX_BODY_BYTES)

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
    # In produzione la documentazione interattiva non deve rivelare la struttura dell'API
    if is_production() and request.url.path in DOCS_PATHS:
        response = JSONResponse({"detail": "Not Found"}, status_code=404)
    else:
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


@app.get("/health", tags=["Monitoraggio"])
def health() -> dict[str, str]:
    """Indica che il server è attivo. Non chiama servizi esterni e non consuma quote."""
    return {"status": "ok"}
