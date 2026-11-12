import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.exceptions import ModelRateLimitError

from travel_agent_api.main import app
from travel_agent_api.routes import chat_router
from travel_agent_api.tools import flights_finder, hotels_finder

URL = "/chat/travel-agent"
BODY = {"messages": [{"role": "user", "content": "Vorrei andare a Roma"}]}
SECRET = "api_key=CHIAVE-SEGRETA"


def failing_agent(error):
    class FailingAgent:
        def run(self, messages):
            raise error

    return FailingAgent


@pytest.fixture
def client():
    # raise_server_exceptions=False: come in produzione, l'errore diventa una risposta HTTP
    return TestClient(app, raise_server_exceptions=False)


def test_provider_non_disponibile_risponde_503(client, monkeypatch):
    error = ModelRateLimitError(f"429 quota esaurita {SECRET}")
    monkeypatch.setattr(chat_router, "Agent", failing_agent(error))

    response = client.post(URL, json=BODY)

    assert response.status_code == 503
    assert "non è al momento disponibile" in response.json()["detail"]
    assert SECRET not in response.text


def test_errore_imprevisto_risponde_500_generico(client, monkeypatch):
    monkeypatch.setattr(chat_router, "Agent", failing_agent(RuntimeError(f"bug interno {SECRET}")))

    response = client.post(URL, json=BODY)

    assert response.status_code == 500
    assert response.json() == {"detail": "Si è verificato un errore interno. Riprova più tardi."}
    assert SECRET not in response.text


class BrokenSearch:
    """Simula un errore di rete di SerpApi il cui messaggio contiene l'URL con la chiave."""

    def __init__(self, params):
        pass

    def get_dict(self):
        raise ConnectionError(f"Max retries exceeded with url: /search?{SECRET}")


@pytest.mark.parametrize(
    "module, tool, params",
    [
        (
            flights_finder,
            flights_finder.flights_finder,
            {"departure_airport": "LIN", "arrival_airport": "FCO",
             "outbound_date": "2027-01-10", "return_date": "2027-01-14"},
        ),
        (
            hotels_finder,
            hotels_finder.hotels_finder,
            {"q": "Roma", "check_in_date": "2027-01-10", "check_out_date": "2027-01-14"},
        ),
    ],
    ids=["voli", "hotel"],
)
def test_errore_serpapi_non_espone_la_chiave(monkeypatch, module, tool, params):
    monkeypatch.setattr(module, "GoogleSearch", BrokenSearch)

    result = tool.invoke({"params": params})

    assert SECRET not in json.dumps(result, default=str)
    assert "non disponibile" in json.dumps(result, ensure_ascii=False)
