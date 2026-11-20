import math
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_PER_MINUTE = 5
# Oltre questo numero di IP tracciati si eliminano quelli inattivi, così la memoria non cresce senza limite
MAX_TRACKED_CLIENTS = 10_000


def is_production() -> bool:
    return os.getenv("APP_ENV", "").lower() == "production"


def rate_limit_per_minute() -> int:
    value = os.getenv("RATE_LIMIT_PER_MINUTE", str(DEFAULT_RATE_LIMIT_PER_MINUTE)).strip()
    if not value.isdigit():
        raise RuntimeError(f"RATE_LIMIT_PER_MINUTE deve essere un intero >= 0 (0 = nessun limite), non {value!r}")
    return int(value)


def validate_settings() -> None:
    """Controlli all'avvio: meglio non partire che fallire a ogni richiesta o partire insicuri."""
    rate_limit_per_minute()
    # In produzione l'API non deve mai partire aperta a tutti per una variabile dimenticata
    if is_production() and not os.getenv("API_ACCESS_KEY"):
        raise RuntimeError(
            "APP_ENV=production richiede API_ACCESS_KEY: senza chiave chiunque potrebbe "
            "consumare le quote di Gemini e SerpApi."
        )


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Richiede l'header X-API-Key se nel .env è impostata API_ACCESS_KEY.
    Senza API_ACCESS_KEY l'endpoint resta aperto (comodo in locale).
    """
    expected = os.getenv("API_ACCESS_KEY")
    if not expected:
        return
    # compare_digest evita di rivelare la chiave tramite i tempi di risposta; si confrontano i byte
    # perché con stringhe non ASCII solleva TypeError (sarebbe un 500 invece di un 401)
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Chiave di accesso mancante o non valida.")


class RateLimiter:
    """
    Limite di richieste per indirizzo IP su una finestra mobile di 60 secondi.
    Lo stato è in memoria: vale finché il server gira come un solo processo.
    """

    def __init__(self, max_tracked_clients: int = MAX_TRACKED_CLIENTS):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._max_tracked_clients = max_tracked_clients

    def _forget_idle_clients(self, now: float) -> None:
        idle = [client for client, hits in self._hits.items() if not hits or now - hits[-1] >= WINDOW_SECONDS]
        for client in idle:
            del self._hits[client]

    def tracked_clients(self) -> int:
        with self._lock:
            return len(self._hits)

    def hit(self, client_id: str) -> int | None:
        """Registra una richiesta. Restituisce None se è permessa, altrimenti i secondi di attesa."""
        limit = rate_limit_per_minute()
        if limit == 0:
            return None

        now = time.monotonic()
        with self._lock:
            if len(self._hits) >= self._max_tracked_clients:
                self._forget_idle_clients(now)
            hits = self._hits[client_id]
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, math.ceil(WINDOW_SECONDS - (now - hits[0])))
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def rate_limit(request: Request) -> None:
    client_id = request.client.host if request.client else "sconosciuto"
    retry_after = rate_limiter.hit(client_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Troppe richieste. Riprova tra qualche secondo.",
            headers={"Retry-After": str(retry_after)},
        )
