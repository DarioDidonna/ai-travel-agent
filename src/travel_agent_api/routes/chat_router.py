from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints, field_validator
from travel_agent_api.services.agent_service import Agent

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
    
    agent = Agent()
    response = agent.run(messages=[message.model_dump() for message in request.messages])
    print("*" * 80)
    print("chat_completion")
    print("*" * 80)
    return response
    