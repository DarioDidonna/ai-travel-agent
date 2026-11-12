import pytest

from travel_agent_api import security


@pytest.fixture(autouse=True)
def isolated_security(monkeypatch):
    """Ogni test parte senza chiave di accesso e senza limite di richieste,
    indipendentemente da cosa c'è nel .env."""
    monkeypatch.delenv("API_ACCESS_KEY", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    security.rate_limiter.reset()
