from langchain_core.messages import AIMessage, HumanMessage

from travel_agent_api.services import agent_service


class FakeExecutor:
    """Simula l'agente compilato: restituisce lo stato come farebbe create_agent."""

    def __init__(self, reply):
        self.reply = reply
        self.received = None

    def invoke(self, state, config=None):
        self.received = state
        self.config = config
        return {"messages": [HumanMessage(m["content"]) for m in state["messages"]] + [self.reply]}


def build_agent(monkeypatch, reply):
    captured = {}
    executor = FakeExecutor(reply)

    def fake_create_agent(model, tools, system_prompt, middleware=()):
        captured.update(model=model, tools=tools, system_prompt=system_prompt, middleware=middleware)
        return executor

    monkeypatch.setattr(agent_service, "get_chat_model", lambda: "modello-finto")
    monkeypatch.setattr(agent_service, "create_agent", fake_create_agent)
    return agent_service.Agent(), executor, captured


def test_prompt_di_sistema_passato_a_create_agent(monkeypatch):
    agent, _, captured = build_agent(monkeypatch, AIMessage("ok"))

    assert captured["model"] == "modello-finto"
    assert len(captured["tools"]) == 4
    assert "Sei un travel planner" in captured["system_prompt"]
    assert agent.today.isoformat() in captured["system_prompt"]


def test_prompt_spiega_come_gestire_richieste_vaghe_o_non_supportate(monkeypatch):
    _, _, captured = build_agent(monkeypatch, AIMessage("ok"))
    prompt = captured["system_prompt"]

    assert "date precise" in prompt  # date vaghe: chiedere o dichiarare la scelta
    assert "camere" in prompt  # filtro non disponibile: dirlo all'utente
    assert "per notte" in prompt  # budget totale convertito in prezzo per notte


def test_run_restituisce_solo_la_risposta_finale(monkeypatch):
    agent, executor, _ = build_agent(monkeypatch, AIMessage("Ecco il tuo viaggio"))
    messages = [{"role": "user", "content": "Vorrei andare a Roma"}]

    result = agent.run(messages)

    # Il prompt di sistema non viene più mescolato ai messaggi dell'utente
    assert executor.received == {"messages": messages}
    assert result == "Ecco il tuo viaggio"
    assert type(result) is str


def test_contenuto_a_blocchi_riportato_a_testo(monkeypatch):
    reply = AIMessage(content=[{"type": "text", "text": "Ciao "}, {"type": "text", "text": "Roma"}])
    agent, _, _ = build_agent(monkeypatch, reply)

    result = agent.run([{"role": "user", "content": "Ciao"}])

    assert result == "Ciao Roma"


def test_consumo_limitato_per_ogni_richiesta(monkeypatch):
    """OWASP LLM10: una sola richiesta non può far fare all'agente chiamate senza limite."""
    _, _, captured = build_agent(monkeypatch, AIMessage("ok"))
    limits = {type(m).__name__: m for m in captured["middleware"]}

    assert limits["ModelCallLimitMiddleware"].run_limit == agent_service.MAX_MODEL_CALLS
    assert limits["ToolCallLimitMiddleware"].run_limit == agent_service.MAX_TOOL_CALLS
    assert agent_service.MAX_MODEL_CALLS <= 10
    assert agent_service.MAX_TOOL_CALLS <= 10


def test_limite_di_passi_passato_all_esecuzione(monkeypatch):
    agent, executor, _ = build_agent(monkeypatch, AIMessage("ok"))

    agent.run([{"role": "user", "content": "Ciao"}])

    assert executor.config == {"recursion_limit": agent_service.RECURSION_LIMIT}


def test_nel_prompt_solo_la_data_non_l_ora(monkeypatch):
    agent, _, captured = build_agent(monkeypatch, AIMessage("ok"))

    assert f"La data di oggi è {agent.today.isoformat()}\n" in captured["system_prompt"]
