import pytest

from travel_agent_api import security
from travel_agent_api.routes import chat_router


@pytest.fixture(autouse=True)
def isolated_security(monkeypatch):
    """Ogni test parte senza chiave di accesso e senza limite di richieste,
    indipendentemente da cosa c'è nel .env."""
    monkeypatch.delenv("API_ACCESS_KEY", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.delenv("APP_ENV", raising=False)
    security.rate_limiter.reset()
    chat_router.get_agent.cache_clear()
