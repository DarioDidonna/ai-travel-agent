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


def test_permissions_policy_su_tutte_le_risposte(client):
    assert client.get("/").headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


def test_hsts_solo_in_produzione(client, monkeypatch):
    assert "strict-transport-security" not in client.get("/health").headers

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_ACCESS_KEY", "chiave")
    headers = client.get("/health").headers

    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_la_pagina_non_tiene_la_chiave_dopo_la_chiusura_del_browser(client):
    script = client.get("/static/app.js").text

    assert "localStorage" not in script
    assert "sessionStorage" in script


def test_la_pagina_scarta_le_risposte_di_una_chat_precedente(client):
    """Se l'utente preme "Nuova chat" durante l'attesa, la vecchia risposta non deve finire nella nuova chat."""
    script = client.get("/static/app.js").text

    assert "conversationId" in script
    assert "if (requestConversation !== conversationId) return;" in script


def test_la_pagina_limita_le_risposte_rimandate_al_server(client):
    script = client.get("/static/app.js").text

    assert "MAX_ASSISTANT_CHARS" in script
