import logging
import os
import time

from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from travel_agent_api.tools import serpapi_client

load_dotenv()

logger = logging.getLogger(__name__)

MAX_FLIGHTS = 5


def _summarize_flights(results: dict) -> dict:
    """Riduce la risposta di SerpApi ai soli campi utili all'agente."""
    options = results.get("best_flights", []) + results.get("other_flights", [])
    flights = []
    for option in options[:MAX_FLIGHTS]:
        flights.append({
            "price": option.get("price"),
            "total_duration": option.get("total_duration"),
            "carbon_emissions_kg": (option.get("carbon_emissions") or {}).get("this_flight", 0) // 1000,
            "layovers": [layover.get("name") for layover in option.get("layovers", [])],
            "legs": [
                {
                    "airline": leg.get("airline"),
                    "flight_number": leg.get("flight_number"),
                    "departure": leg.get("departure_airport"),
                    "arrival": leg.get("arrival_airport"),
                    "duration": leg.get("duration"),
                }
                for leg in option.get("flights", [])
            ],
        })
    return {
        "google_flights_url": results.get("search_metadata", {}).get("google_flights_url"),
        "error": results.get("error"),
        "flights": flights,
    }


class FlightsInput(BaseModel):
    departure_airport: str = Field(description="The departure airport code (IATA).")
    arrival_airport: str = Field(description="The arrival airport code (IATA).")
    outbound_date: str = Field(description="The outbound date (YYYY-MM-DD) e.g. 2024-12-13.")
    return_date: str = Field(description="The return date (YYYY-MM-DD) e.g. 2024-12-19.")
    adults: int | None = Field(1, description="The number of adults. Defaults to 1.")
    children: int | None = Field(0, description="The number of children. Defaults to 0.")
    nonstop_only: bool = Field(
        False, description="Set to true only when the user asks for direct / nonstop flights."
    )
    cheapest_first: bool = Field(
        False, description="Set to true when the user asks for the cheapest flights: results sorted by price."
    )
    max_price: int | None = Field(
        None, description="Maximum total price in EUR for the round trip, only if the user gives a flight budget."
    )

class FlightsInputSchema(BaseModel):
    params : FlightsInput


@tool(args_schema=FlightsInputSchema)
def flights_finder(params: FlightsInput):
    """
    This tool uses the SerpApi Google Flights API to retrieve flights info.
    Parameters:
        departure_airport (str): The departure airport code (IATA).
        arrival_airport (str): The arrival airport code (IATA).
        outbound_date (str): The outbound date (YYYY-MM-DD) e.g. 2024-12-13.
        return_date (str): The return date (YYYY-MM-DD) e.g. 2024-12-19.
        adults (int): The number of adults. Defaults to 1.
        children (int): The number of children. Defaults to 0.
        nonstop_only (bool): Only direct flights. Defaults to false.
        cheapest_first (bool): Sort results by price. Defaults to false.
        max_price (int): Maximum total price in EUR. Optional.
    Returns:
        dict: A dictionary containing the flights info. If the API call fails, it returns an error message.
    """
    start = time.perf_counter()
    try:
        search_params = {
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "engine": "google_flights",
            "hl": "it",
            "gl": "it",
            "currency": "EUR",
            # 0 = qualsiasi numero di scali, 1 = solo voli diretti
            "stops": "1" if params.nonstop_only else "0",
            "departure_id": params.departure_airport,
            "arrival_id": params.arrival_airport,
            "outbound_date": params.outbound_date,
            "return_date": params.return_date,
            "adults": params.adults,
            "children": params.children
        }
        if params.cheapest_first:
            search_params["sort_by"] = "2"  # 2 = prezzo
        if params.max_price:
            search_params["max_price"] = str(params.max_price)
        summary = _summarize_flights(serpapi_client.search(search_params))

        logger.info("flights_finder: %d opzioni in %.1fs", len(summary["flights"]), time.perf_counter() - start)
        return summary

    except serpapi_client.SerpApiError as e:
        # Chiave non valida, quota esaurita…: il messaggio di SerpApi è sicuro da registrare
        logger.error("SerpApi ha rifiutato la ricerca voli: %s", e)
        return {"error": "Ricerca voli non disponibile al momento."}
    except Exception as e:
        # Il messaggio dell'errore può contenere l'URL con la api_key: non va né al modello né nel log
        logger.error("Errore SerpApi nella ricerca voli: %s", type(e).__name__)
        return {"error": "Ricerca voli non disponibile al momento."}




