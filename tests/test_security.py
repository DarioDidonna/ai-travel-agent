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


def test_chiave_con_caratteri_non_ascii_risponde_401_non_500(monkeypatch):
    monkeypatch.setenv("API_ACCESS_KEY", "chiave-corretta")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(URL, json=BODY, headers={"X-API-Key": "chiavé".encode("latin-1")})

    assert response.status_code == 401


def test_il_rate_limiter_libera_la_memoria_degli_ip_inattivi(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(security.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    limiter = security.RateLimiter(max_tracked_clients=100)

    for i in range(100):
        limiter.hit(f"10.0.0.{i}")
    now[0] += 61
    limiter.hit("10.0.1.1")

    assert limiter.tracked_clients() == 1


@pytest.mark.parametrize("value", ["10/min", "", "-1", "cinque"])
def test_rate_limit_non_valido_blocca_l_avvio(monkeypatch, value):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", value)

    with pytest.raises(RuntimeError, match="RATE_LIMIT_PER_MINUTE"):
        security.validate_settings()
