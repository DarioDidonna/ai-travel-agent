import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.exceptions import ModelAPIError, ModelError, ModelRateLimitError
from pydantic import BaseModel, Field, StringConstraints, field_validator
from travel_agent_api.security import rate_limit, verify_api_key
from travel_agent_api.services.agent_service import Agent

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_MESSAGE_LENGTH = 4000
MAX_MESSAGES = 30


class ChatMessage(BaseModel):
    # Solo user/assistant: i ruoli system/developer/tool sono riservati all'agente
    role: Literal["user", "assistant"]
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)
    ]


class ChatComplentionRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)

    @field_validator("messages")
    @classmethod
    def last_message_from_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError("L'ultimo messaggio deve avere ruolo 'user'")
        return messages

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "Vorrei organizzare un viaggio a Roma"
                    }
                ]
            }
        }
    }


class ChatCompletionResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


def provider_unavailable(error: ModelError) -> HTTPException:
    """Traduce l'errore del provider in un 503 che dice all'utente quando ha senso riprovare."""
    if isinstance(error, ModelRateLimitError):
        if "per day" in str(error).lower():
            return HTTPException(
                status_code=503,
                detail="La quota giornaliera del servizio di intelligenza artificiale è esaurita. "
                "Riprova domani oppure cambia modello (LLM_MODEL nel .env).",
            )
        detail = "Troppe richieste al servizio di intelligenza artificiale. Riprova tra un minuto."
    elif isinstance(error, ModelAPIError):
        detail = "Il servizio di intelligenza artificiale è sovraccarico. Riprova tra un minuto."
    else:
        return HTTPException(
            status_code=503,
            detail="Il servizio di intelligenza artificiale non è al momento disponibile. "
            "Riprova tra qualche minuto.",
        )
    return HTTPException(status_code=503, detail=detail, headers={"Retry-After": "60"})


@router.post(
    "/travel-agent",
    response_model=ChatCompletionResponse,
    dependencies=[Depends(rate_limit), Depends(verify_api_key)],
    responses={
        401: {"description": "Chiave di accesso mancante o non valida (solo se API_ACCESS_KEY è impostata)"},
        422: {"description": "Messaggi non validi"},
        429: {"description": "Troppe richieste: riprovare dopo i secondi indicati in Retry-After"},
        503: {"description": "Servizio di intelligenza artificiale non disponibile"},
    },
)
def chat_completion(request: ChatComplentionRequest):
    """
    Endpoint per la gestione delle richieste di chat.
    Processa i messaggi ricevuti e restituisce la risposta finale dell'agente di viaggio.

    Args:
        request (ChatComplentionRequest): La richiesta contenente i messaggi della conversazione

    Returns:
        ChatCompletionResponse: La risposta dell'assistente, in markdown

    Raises:
        HTTPException: In caso di errori durante l'elaborazione della richiesta
    """

    try:
        agent = Agent()
        reply = agent.run(messages=[message.model_dump() for message in request.messages])
    except ModelError as error:
        # Gemini/OpenAI/Ollama non raggiungibile, quota esaurita, chiave non valida...
        logger.exception("Errore del provider del modello")
        raise provider_unavailable(error)
    except Exception:
        # I dettagli restano nel log del server, al client arriva un messaggio generico
        logger.exception("Errore imprevisto durante l'elaborazione della chat")
        raise HTTPException(status_code=500, detail="Si è verificato un errore interno. Riprova più tardi.")

    print("*" * 80)
    print("chat_completion")
    print("*" * 80)
    return ChatCompletionResponse(content=reply)
    