import pytest
from fastapi.testclient import TestClient

from travel_agent_api import security
from travel_agent_api.main import app
from travel_agent_api.routes import chat_router

URL = "/chat/travel-agent"
BODY = {"messages": [{"role": "user", "content": "Vorrei andare a Roma"}]}


class FakeAgent:
    calls = 0

    def run(self, messages):
        FakeAgent.calls += 1
        return "Risposta di prova"


@pytest.fixture
def client(monkeypatch):
    FakeAgent.calls = 0
    monkeypatch.setattr(chat_router, "Agent", FakeAgent)
    return TestClient(app)


# --- Chiave di accesso ---------------------------------------------------------

def test_senza_api_access_key_l_endpoint_e_aperto(client):
    assert client.post(URL, json=BODY).status_code == 200


def test_chiave_mancante_risponde_401(client, monkeypatch):
    monkeypatch.setenv("API_ACCESS_KEY", "chiave-corretta")

    response = client.post(URL, json=BODY)

    assert response.status_code == 401
    assert FakeAgent.calls == 0


def test_chiave_sbagliata_risponde_401(client, monkeypatch):
    monkeypatch.setenv("API_ACCESS_KEY", "chiave-corretta")

    response = client.post(URL, json=BODY, headers={"X-API-Key": "chiave-sbagliata"})

    assert response.status_code == 401
    assert FakeAgent.calls == 0


def test_chiave_corretta_risponde_200(client, monkeypatch):
    monkeypatch.setenv("API_ACCESS_KEY", "chiave-corretta")

    response = client.post(URL, json=BODY, headers={"X-API-Key": "chiave-corretta"})

    assert response.status_code == 200
    assert FakeAgent.calls == 1


# --- Limite di richieste --------------------------------------------------------

def test_oltre_il_limite_risponde_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")

    codes = [client.post(URL, json=BODY).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert FakeAgent.calls == 2


def test_risposta_429_indica_quando_riprovare(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    client.post(URL, json=BODY)

    response = client.post(URL, json=BODY)

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_il_limite_si_libera_dopo_un_minuto(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(security.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")

    assert security.rate_limiter.hit("1.2.3.4") is None
    assert security.rate_limiter.hit("1.2.3.4") is not None

    now[0] += 61
    assert security.rate_limiter.hit("1.2.3.4") is None


def test_il_limite_e_per_indirizzo_ip(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")

    assert security.rate_limiter.hit("1.1.1.1") is None
    assert security.rate_limiter.hit("2.2.2.2") is None
    assert security.rate_limiter.hit("1.1.1.1") is not None
