import logging
import os
import time

from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from travel_agent_api.tools import serpapi_client

load_dotenv()

logger = logging.getLogger(__name__)

MAX_HOTELS = 5


def _summarize_hotel(hotel: dict) -> dict:
    """Riduce i dati di un hotel di SerpApi ai soli campi utili all'agente."""
    images = hotel.get("images") or [{}]
    return {
        "name": hotel.get("name"),
        "description": hotel.get("description"),
        "link": hotel.get("link"),
        "image": images[0].get("thumbnail"),
        "hotel_class": hotel.get("hotel_class"),
        "rate_per_night": (hotel.get("rate_per_night") or {}).get("lowest"),
        "total_rate": (hotel.get("total_rate") or {}).get("lowest"),
        "check_in_time": hotel.get("check_in_time"),
        "check_out_time": hotel.get("check_out_time"),
        "overall_rating": hotel.get("overall_rating"),
        "reviews": hotel.get("reviews"),
        "amenities": (hotel.get("amenities") or [])[:8],
    }


class HotelsInput(BaseModel):
    q: str = Field(description="Location of the hotel.", min_length=1, max_length=100)
    check_in_date: str = Field(
        description="The check-in date (YYYY-MM-DD) e.g. 2024-12-13.", pattern=serpapi_client.DATE_PATTERN
    )
    check_out_date: str = Field(
        description="The check-out date (YYYY-MM-DD) e.g. 2024-12-19.", pattern=serpapi_client.DATE_PATTERN
    )
    adults: int = Field(1, description="The number of adults. Defaults to 1.", ge=1, le=serpapi_client.MAX_PASSENGERS)
    children: int = Field(0, description="The number of children. Defaults to 0.", ge=0, le=8)
    children_ages: str | None = Field(
        None,
        description="Comma-separated age of each child (1-17), e.g. '5,9'. Required when children > 0: "
        "ask the user if you don't know them.",
        pattern=r"^\d{1,2}(,\d{1,2})*$",
    )
    hotel_class: str | None = Field(
        None,
        description="Only if the user asks for a star rating. Comma-separated star classes from 2 to 5: "
        "'4' for 4-star only, '3,4,5' for at least 3 stars.",
        pattern=r"^[2-5](,[2-5])*$",
    )
    max_price_per_night: int | None = Field(
        None,
        description="Maximum price per night in EUR. If the user gives a total budget, "
        "divide it by the number of nights.",
        ge=1,
    )
    cheapest_first: bool = Field(
        False, description="Set to true when the user asks for the cheapest hotels: results sorted by price."
    )


class HotelsInputSchema(BaseModel):
    params: HotelsInput


@tool(args_schema=HotelsInputSchema)
def hotels_finder(params: HotelsInput):
    """
    This tool uses the SerpApi Google Hotels API to retrieve hotels info.
    Parameters:
        q (str): Location of the hotel.
        check_in_date (str): The outbound date (YYYY-MM-DD) e.g. 2024-12-13.
        check_out_date (str): The return date (YYYY-MM-DD) e.g. 2024-12-19.
        adults (int): The number of adults. Defaults to 1.
        children (int): The number of children. Defaults to 0.
        children_ages (str): Age of each child, required when children > 0.
        hotel_class (str): Star classes, e.g. '3,4,5'. Optional: no filter by default.
        max_price_per_night (int): Maximum price per night in EUR. Optional.
        cheapest_first (bool): Sort results by price. Defaults to false.
    Note:
        The number of rooms cannot be filtered: Google Hotels only accepts adults and children.
    Returns:
        dict: A dictionary containing the hotels info. If the API call fails, it returns an error message.
    """

    if params.children and len((params.children_ages or "").split(",")) != params.children:
        # SerpApi rifiuterebbe la ricerca: meglio far chiedere le età all'utente
        return {"error": "Per cercare hotel con bambini serve l'età di ogni bambino: chiedila all'utente."}

    start = time.perf_counter()
    search_params = {
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "engine": "google_hotels",
        "hl": "it",
        "gl": "it",
        "currency": "EUR",
        "q": params.q,
        "check_in_date": params.check_in_date,
        "check_out_date": params.check_out_date,
        "adults": params.adults,
        "children": params.children,
    }
    if params.children:
        search_params["children_ages"] = params.children_ages
    # Senza filtro di default: hotel_class=2 per SerpApi significa "solo 2 stelle"
    if params.hotel_class:
        search_params["hotel_class"] = params.hotel_class
    if params.max_price_per_night:
        search_params["max_price"] = str(params.max_price_per_night)
    if params.cheapest_first:
        search_params["sort_by"] = "3"  # 3 = prezzo più basso

    try:
        properties = serpapi_client.search(search_params).get("properties", [])
        results = [_summarize_hotel(hotel) for hotel in properties[:MAX_HOTELS]]
    except serpapi_client.SerpApiError as e:
        # Prima diventava una lista vuota: l'agente rispondeva "nessun hotel" anche con la chiave sbagliata
        logger.error("SerpApi ha rifiutato la ricerca hotel: %s", e)
        results = {"error": "Ricerca hotel non disponibile al momento."}
    except Exception as e:
        # Il messaggio dell'errore può contenere l'URL con la api_key: non va né al modello né nel log
        logger.error("Errore SerpApi nella ricerca hotel: %s", type(e).__name__)
        results = {"error": "Ricerca hotel non disponibile al momento."}

    logger.info("hotels_finder completato in %.1fs", time.perf_counter() - start)
    return results
