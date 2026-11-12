import logging
import os
from langchain_core.tools import tool
from serpapi import GoogleSearch
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional
from enum import IntEnum

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
        "amenities": hotel.get("amenities", [])[:8],
    }


class HotelClassEnum(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class HotelsInput(BaseModel):
    q: str = Field(description="Location of the hotel.")
    check_in_date: str = Field(
        description="The outbound date (YYYY-MM-DD) e.g. 2024-12-13."
    )
    check_out_date: str = Field(
        description="The return date (YYYY-MM-DD) e.g. 2024-12-19."
    )
    adults: Optional[int] = Field(1, description="The number of adults. Defaults to 1.")
    children: Optional[int] = Field(
        0, description="The number of children. Defaults to 0."
    )
    hotel_class: Optional[int] = Field(
        2, description="The hotel class available from 2 to 5. Defaults to 2."
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
        hotel_class (int): The hotel class available from 2 to 5. Defaults to 2.
    Returns:
        dict: A dictionary containing the hotels info. If the API call fails, it returns the error message as a string.
    """

    params = {
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
        "hotel_class": params.hotel_class,
    }

    try:
        search = GoogleSearch(params)
        properties = search.get_dict().get("properties", [])
        results = [_summarize_hotel(hotel) for hotel in properties[:MAX_HOTELS]]
    except Exception as e:
        # Il messaggio dell'errore può contenere l'URL con la api_key: non va né al modello né nel log
        logger.error("Errore SerpApi nella ricerca hotel: %s", type(e).__name__)
        results = {"error": "Ricerca hotel non disponibile al momento."}

    print("*" * 80)
    print("hotels_finder")
    print("*" * 80)
    return results
