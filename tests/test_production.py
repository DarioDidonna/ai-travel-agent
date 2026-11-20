import pytest
from fastapi.testclient import TestClient

from travel_agent_api.main import MAX_BODY_BYTES, app
from travel_agent_api.routes import chat_router

URL = "/chat/travel-agent"


class FakeAgent:
    def run(self, messages):
        return "ok"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(chat_router, "Agent", FakeAgent)
    return TestClient(app)


# --- Avvio in produzione ----------------------------------------------------------

def test_in_produzione_senza_chiave_il_server_non_parte(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="API_ACCESS_KEY"):
        with TestClient(app):
            pass


def test_in_produzione_con_chiave_il_server_parte(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_ACCESS_KEY", "chiave-lunga-e-casuale")

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_in_locale_senza_chiave_il_server_parte(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


# --- Documentazione dell'API --------------------------------------------------------

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentazione_disattivata_in_produzione(client, monkeypatch, path):
    monkeypatch.setenv("APP_ENV", "production")

    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_documentazione_attiva_in_locale(client, path):
    assert client.get(path).status_code == 200


# --- Dimensione del body ------------------------------------------------------------

def test_body_troppo_grande_risponde_413(client):
    body = b'{"messages":[{"role":"user","content":"' + b"a" * MAX_BODY_BYTES + b'"}]}'

    response = client.post(URL, content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 413


def test_body_troppo_grande_senza_content_length_risponde_413(client):
    """Il limite conta i byte ricevuti: non basta omettere o falsificare Content-Length."""

    def chunks():
        yield b'{"messages":[{"role":"user","content":"'
        for _ in range(MAX_BODY_BYTES // 1024 + 2):
            yield b"a" * 1024
        yield b'"}]}'

    response = client.post(URL, content=chunks(), headers={"Content-Type": "application/json"})

    assert response.status_code == 413


def test_conversazione_valida_al_limite_massimo_accettata(client):
    """30 messaggi da 4000 caratteri devono restare sotto il limite."""
    messages = [{"role": "user", "content": "è" * 4000} for _ in range(30)]

    response = client.post(URL, json={"messages": messages})

    assert response.status_code == 200
