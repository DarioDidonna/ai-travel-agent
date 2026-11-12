import math
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_PER_MINUTE = 5


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Richiede l'header X-API-Key se nel .env è impostata API_ACCESS_KEY.
    Senza API_ACCESS_KEY l'endpoint resta aperto (comodo in locale).
    """
    expected = os.getenv("API_ACCESS_KEY")
    if not expected:
        return
    # compare_digest evita di rivelare la chiave tramite i tempi di risposta
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Chiave di accesso mancante o non valida.")


class RateLimiter:
    """
    Limite di richieste per indirizzo IP su una finestra mobile di 60 secondi.
    Lo stato è in memoria: vale finché il server gira come un solo processo.
    """

    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, client_id: str) -> int | None:
        """Registra una richiesta. Restituisce None se è permessa, altrimenti i secondi di attesa."""
        limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE))
        if limit <= 0:
            return None

        now = time.monotonic()
        with self._lock:
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
