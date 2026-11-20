import pytest
from fastapi.testclient import TestClient

from travel_agent_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_la_home_mostra_la_pagina_di_chat(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Travel Agent AI" in response.text


def test_la_home_ha_una_content_security_policy_rigida(client):
    csp = client.get("/").headers["content-security-policy"]

    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp.split("img-src")[0]


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/static/app.js", "javascript"),
        ("/static/style.css", "text/css"),
        ("/static/vendor/marked.min.js", "javascript"),
        ("/static/vendor/purify.min.js", "javascript"),
    ],
)
def test_file_statici_serviti(client, path, content_type):
    response = client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/", "/static/app.js", "/docs"])
def test_header_di_sicurezza_su_tutte_le_risposte(client, path):
    headers = client.get(path).headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"


def test_la_pagina_sanifica_il_markdown_del_modello(client):
    """Il testo del modello passa da DOMPurify prima di finire nell'HTML."""
    script = client.get("/static/app.js").text

    assert "DOMPurify.sanitize(" in script
    assert script.count("innerHTML") == 1
    assert "bubble.innerHTML = renderMarkdown(content)" in script


def test_health_risponde_senza_chiamare_servizi_esterni(client, monkeypatch):
    """Usato da Docker e dagli hosting per sapere se il server è vivo."""
    monkeypatch.setenv("API_ACCESS_KEY", "chiave")  # non serve la chiave per /health

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
