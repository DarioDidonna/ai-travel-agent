"""
OWASP LLM10 (Unbounded Consumption) con l'agente LangChain vero: solo il modello è finto.
Riproduce un caso osservato con Gemini: 23 ricerche voli chieste in parallelo in un solo passo.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from travel_agent_api.services import agent_service
from travel_agent_api.tools import serpapi_client


class ScriptedModel(BaseChatModel):
    """Restituisce le risposte prefissate, una per ogni chiamata."""

    replies: list

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def flight_call(day: int) -> dict:
    return {
        "name": "flights_finder",
        "id": f"call-{day}",
        "args": {"params": {"departure_airport": "LIN", "arrival_airport": "FCO",
                            "outbound_date": f"2027-02-{day:02d}", "return_date": f"2027-02-{day:02d}"}},
    }


def run_agent(monkeypatch, replies):
    searches = []

    class CountingSearch:
        def __init__(self, params):
            searches.append(params["outbound_date"])

        def get_dict(self):
            return {}

    monkeypatch.setattr(serpapi_client, "GoogleSearch", CountingSearch)
    monkeypatch.setattr(agent_service, "get_chat_model", lambda: ScriptedModel(replies=replies))
    reply = agent_service.Agent().run([{"role": "user", "content": "Voli per ogni giorno di febbraio"}])
    return reply, searches


def test_23_ricerche_in_parallelo_ne_eseguono_al_massimo_8(monkeypatch):
    replies = [
        AIMessage(content="", tool_calls=[flight_call(day) for day in range(1, 24)]),
        AIMessage(content="Ho confrontato i primi giorni disponibili."),
    ]

    reply, searches = run_agent(monkeypatch, replies)

    assert len(searches) == agent_service.MAX_TOOL_CALLS
    assert reply == "Ho confrontato i primi giorni disponibili."


def test_risposta_vuota_del_modello_diventa_un_messaggio_chiaro(monkeypatch):
    """Con Gemini, dopo i tool bloccati, la risposta finale è arrivata vuota: l'utente vedeva una bolla bianca."""
    replies = [
        AIMessage(content="", tool_calls=[flight_call(day) for day in range(1, 24)]),
        AIMessage(content=""),
    ]

    reply, _ = run_agent(monkeypatch, replies)

    assert reply == agent_service.EMPTY_REPLY_MESSAGE
    assert "più semplici" in reply
