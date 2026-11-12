import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from serpapi import GoogleSearch
from pydantic import BaseModel , Field
from typing import Optional

load_dotenv()

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
    adults: Optional[int] = Field(1, description="The number of adults. Defaults to 1.")
    children: Optional[int] = Field(0, description="The number of children. Defaults to 0.")

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
    Returns:
        dict: A dictionary containing the flights info. If the API call fails, it returns the error message as a string.
    """
    try:
        params = {
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "engine": "google_flights",
            "hl": "it",
            "gl": "it",
            "currency": "EUR",
            "stops": "0",  # 0 = qualsiasi numero di scali (1 = solo voli diretti)
            "departure_id": params.departure_airport,
            "arrival_id": params.arrival_airport,
            "outbound_date": params.outbound_date,
            "return_date": params.return_date,
            "adults": params.adults,
            "children": params.children
        }
        search = GoogleSearch(params)
        
        print("*" * 80)
        print("flights_finder")
        print("*" * 80)
        return _summarize_flights(search.get_dict())

    except Exception as e:
        return str(e)
    
    
    
    
