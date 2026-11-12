from fastapi.testclient import TestClient

from travel_agent_api.main import app, get_cors_origins

URL = "/chat/travel-agent"


def preflight(client, origin):
    return client.options(
        URL,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )


def test_origini_predefinite(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert get_cors_origins() == ["http://localhost:8000", "http://127.0.0.1:8000"]


def test_origini_dal_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://mio-sito.it , http://localhost:3000 ,")

    assert get_cors_origins() == ["https://mio-sito.it", "http://localhost:3000"]


def test_origine_autorizzata_puo_inviare_la_chiave():
    response = preflight(TestClient(app), "http://localhost:8000")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()


def test_origine_non_autorizzata_bloccata():
    response = preflight(TestClient(app), "https://sito-sconosciuto.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
