import pytest

from travel_agent_api.tools import flights_finder, hotels_finder

FLIGHT = {"departure_airport": "BRI", "arrival_airport": "AMS",
          "outbound_date": "2027-02-10", "return_date": "2027-02-14"}
HOTEL = {"q": "Amsterdam centro", "check_in_date": "2027-02-10", "check_out_date": "2027-02-14"}


@pytest.fixture
def sent_params(monkeypatch):
    """Sostituisce SerpApi e registra i parametri che i tool gli inviano."""
    sent = {}

    class FakeSearch:
        def __init__(self, params):
            sent.clear()
            sent.update(params)

        def get_dict(self):
            return {}

    monkeypatch.setattr(flights_finder, "GoogleSearch", FakeSearch)
    monkeypatch.setattr(hotels_finder, "GoogleSearch", FakeSearch)
    return sent


# --- Voli -----------------------------------------------------------------------

def test_voli_di_default_qualsiasi_scalo_e_nessun_filtro(sent_params):
    flights_finder.flights_finder.invoke({"params": FLIGHT})

    assert sent_params["stops"] == "0"
    assert "sort_by" not in sent_params
    assert "max_price" not in sent_params


def test_voli_solo_diretti(sent_params):
    flights_finder.flights_finder.invoke({"params": {**FLIGHT, "nonstop_only": True}})

    assert sent_params["stops"] == "1"


def test_voli_dal_piu_economico_con_prezzo_massimo(sent_params):
    flights_finder.flights_finder.invoke({"params": {**FLIGHT, "cheapest_first": True, "max_price": 300}})

    assert sent_params["sort_by"] == "2"
    assert sent_params["max_price"] == "300"


# --- Hotel ----------------------------------------------------------------------

def test_hotel_di_default_nessun_filtro_di_prezzo(sent_params):
    hotels_finder.hotels_finder.invoke({"params": HOTEL})

    assert "max_price" not in sent_params
    assert "sort_by" not in sent_params


def test_hotel_prezzo_massimo_per_notte_e_dal_piu_economico(sent_params):
    hotels_finder.hotels_finder.invoke(
        {"params": {**HOTEL, "max_price_per_night": 137, "cheapest_first": True}}
    )

    assert sent_params["max_price"] == "137"
    assert sent_params["sort_by"] == "3"


def test_hotel_dichiara_che_le_camere_non_si_possono_filtrare():
    """Il modello legge la descrizione del tool: deve sapere che il filtro camere non esiste."""
    description = hotels_finder.hotels_finder.description.lower()

    assert "rooms" in description
    assert "per night" in description
