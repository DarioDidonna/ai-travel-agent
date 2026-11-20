import pytest

from travel_agent_api.tools import flights_finder, hotels_finder, serpapi_client

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

    monkeypatch.setattr(serpapi_client, "GoogleSearch", FakeSearch)
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


# --- Correzioni dalla code review --------------------------------------------------

def test_hotel_di_default_nessun_filtro_sulle_stelle(sent_params):
    """hotel_class=2 per SerpApi significa "solo 2 stelle", non "almeno 2"."""
    hotels_finder.hotels_finder.invoke({"params": HOTEL})

    assert "hotel_class" not in sent_params


def test_hotel_stelle_solo_se_richieste(sent_params):
    hotels_finder.hotels_finder.invoke({"params": {**HOTEL, "hotel_class": "3,4,5"}})

    assert sent_params["hotel_class"] == "3,4,5"


def test_hotel_con_bambini_passa_le_eta(sent_params):
    hotels_finder.hotels_finder.invoke({"params": {**HOTEL, "children": 2, "children_ages": "5,9"}})

    assert sent_params["children"] == 2
    assert sent_params["children_ages"] == "5,9"


def test_hotel_con_bambini_senza_eta_chiede_le_eta(sent_params):
    """SerpApi rifiuta la ricerca senza un'età per ogni bambino: meglio dirlo all'agente."""
    result = hotels_finder.hotels_finder.invoke({"params": {**HOTEL, "children": 2, "children_ages": "5"}})

    assert sent_params == {}  # nessuna chiamata a SerpApi
    assert "età" in result["error"]


@pytest.mark.parametrize(
    "field, value",
    [("departure_airport", "Milano"), ("departure_airport", "lin"), ("outbound_date", "5 febbraio 2027"),
     ("adults", 0), ("adults", 50), ("max_price", -10)],
)
def test_voli_argomenti_del_modello_validati(sent_params, field, value):
    """Gli argomenti li scrive il modello: valori fuori formato tornano a lui come errore, senza chiamare SerpApi."""
    with pytest.raises(ValueError):
        flights_finder.flights_finder.invoke({"params": {**FLIGHT, field: value}})

    assert sent_params == {}


@pytest.mark.parametrize(
    "field, value",
    [("check_in_date", "2027/02/10"), ("hotel_class", "tre stelle"), ("children_ages", "otto"), ("adults", 0)],
)
def test_hotel_argomenti_del_modello_validati(sent_params, field, value):
    with pytest.raises(ValueError):
        hotels_finder.hotels_finder.invoke({"params": {**HOTEL, field: value}})

    assert sent_params == {}


def test_voli_con_dati_mancanti_non_fanno_fallire_la_ricerca():
    """Un'opzione con campi null non deve far perdere tutti i risultati."""
    results = {"best_flights": [{
        "price": 120, "total_duration": 90, "carbon_emissions": {"this_flight": None},
        "layovers": None, "flights": None,
    }]}

    summary = flights_finder._summarize_flights(results)

    assert summary["flights"][0]["price"] == 120
    assert summary["flights"][0]["carbon_emissions_kg"] == 0


def test_hotel_con_dati_mancanti_non_fanno_fallire_la_ricerca():
    hotel = {"name": "Hotel", "amenities": None, "images": None, "rate_per_night": None}

    summary = hotels_finder._summarize_hotel(hotel)

    assert summary["name"] == "Hotel"
    assert summary["amenities"] == []
