from serpapi import GoogleSearch

# La libreria usa 60000 di default, che requests interpreta in secondi (~17 ore)
TIMEOUT_SECONDS = 20

# SerpApi usa il campo "error" anche quando la ricerca va a buon fine ma non trova nulla
NO_RESULTS_MESSAGE = "hasn't returned any results"


class SerpApiError(Exception):
    """Guasto del servizio (chiave non valida, quota esaurita…), non una ricerca senza risultati."""


def is_service_error(results: dict) -> bool:
    error = results.get("error")
    return bool(error) and NO_RESULTS_MESSAGE not in error


def search(params: dict) -> dict:
    """Esegue una ricerca SerpApi con un timeout ragionevole e solleva SerpApiError se il servizio fallisce."""
    client = GoogleSearch(params)
    client.timeout = TIMEOUT_SECONDS
    results = client.get_dict()
    if is_service_error(results):
        # Il messaggio di errore di SerpApi non contiene la chiave
        raise SerpApiError(results["error"])
    return results
