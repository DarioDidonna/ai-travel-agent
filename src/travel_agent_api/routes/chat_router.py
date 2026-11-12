import logging
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import ModelError
from pydantic import BaseModel, Field, StringConstraints, field_validator
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
    
@router.post("/travel-agent") 
def chat_completion(request: ChatComplentionRequest):
    """
    Endpoint per la gestione delle richieste di chat.
    Processa i messaggi ricevuti e restituisce una risposta dall'agente di viaggio.

    Args:
        request (ChatComplentionRequest): La richiesta contenente i messaggi della conversazione
        
    Returns:
        dict: La risposta elaborata dall'agente di viaggio 
        
    Raises:
        HTTPException: In caso di errori durante l'elaborazione della richiesta 
    """
    
    try:
        agent = Agent()
        response = agent.run(messages=[message.model_dump() for message in request.messages])
    except ModelError:
        # Gemini/OpenAI/Ollama non raggiungibile, quota esaurita, chiave non valida...
        logger.exception("Errore del provider del modello")
        raise HTTPException(
            status_code=503,
            detail="Il servizio di intelligenza artificiale non è al momento disponibile. "
            "Riprova tra qualche minuto.",
        )
    except Exception:
        # I dettagli restano nel log del server, al client arriva un messaggio generico
        logger.exception("Errore imprevisto durante l'elaborazione della chat")
        raise HTTPException(status_code=500, detail="Si è verificato un errore interno. Riprova più tardi.")

    print("*" * 80)
    print("chat_completion")
    print("*" * 80)
    return response
    