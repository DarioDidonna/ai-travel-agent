import pytest
import requests

from travel_agent_api.tools import flights_finder, hotels_finder, serpapi_client

FLIGHT = {"departure_airport": "LIN", "arrival_airport": "FCO",
          "outbound_date": "2027-01-10", "return_date": "2027-01-14"}
HOTEL = {"q": "Roma", "check_in_date": "2027-01-10", "check_out_date": "2027-01-14"}

INVALID_KEY = {"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}
NO_HOTELS = {"error": "Google Hotels hasn't returned any results for this query."}
NO_FLIGHTS = {"error": "Google Flights hasn't returned any results for this query."}


def fake_search(response=None, raises=None):
    """GoogleSearch finto: registra il timeout impostato e restituisce la risposta indicata."""

    class FakeSearch:
        last = None

        def __init__(self, params):
            self.timeout = 60000  # il default della libreria (in secondi!)
            FakeSearch.last = self

        def get_dict(self):
            if raises:
                raise raises
            return response

    return FakeSearch


def run(module, tool, params, monkeypatch, search):
    monkeypatch.setattr(serpapi_client, "GoogleSearch", search)
    return tool.invoke({"params": params})


TOOLS = [
    pytest.param(flights_finder, flights_finder.flights_finder, FLIGHT, id="voli"),
    pytest.param(hotels_finder, hotels_finder.hotels_finder, HOTEL, id="hotel"),
]


@pytest.mark.parametrize("module, tool, params", TOOLS)
def test_timeout_esplicito_invece_di_17_ore(monkeypatch, module, tool, params):
    search = fake_search(response={})

    run(module, tool, params, monkeypatch, search)

    assert search.last.timeout == serpapi_client.TIMEOUT_SECONDS == 20


@pytest.mark.parametrize("module, tool, params", TOOLS)
def test_timeout_di_serpapi_diventa_un_errore_gestito(monkeypatch, module, tool, params):
    search = fake_search(raises=requests.Timeout("read timed out"))

    result = run(module, tool, params, monkeypatch, search)

    assert result == {"error": f"Ricerca {'voli' if module is flights_finder else 'hotel'} non disponibile al momento."}


@pytest.mark.parametrize("module, tool, params", TOOLS)
def test_chiave_serpapi_non_valida_non_viene_scambiata_per_nessun_risultato(monkeypatch, module, tool, params):
    result = run(module, tool, params, monkeypatch, fake_search(response=INVALID_KEY))

    assert isinstance(result, dict)
    assert "non disponibile" in result["error"]


def test_hotel_senza_risultati_restituisce_lista_vuota(monkeypatch):
    result = run(hotels_finder, hotels_finder.hotels_finder, HOTEL, monkeypatch, fake_search(response=NO_HOTELS))

    assert result == []


def test_voli_senza_risultati_restituiscono_lista_vuota(monkeypatch):
    result = run(flights_finder, flights_finder.flights_finder, FLIGHT, monkeypatch, fake_search(response=NO_FLIGHTS))

    assert result["flights"] == []
    assert "non disponibile" not in str(result)


@pytest.mark.parametrize(
    "response, expected",
    [
        ({}, False),
        (NO_HOTELS, False),
        (NO_FLIGHTS, False),
        (INVALID_KEY, True),
        ({"error": "Your account has run out of searches."}, True),
    ],
)
def test_distinzione_tra_guasto_e_nessun_risultato(response, expected):
    assert serpapi_client.is_service_error(response) is expected
