from langchain_core.messages import AIMessage, HumanMessage

from travel_agent_api.services import agent_service


class FakeExecutor:
    """Simula l'agente compilato: restituisce lo stato come farebbe create_agent."""

    def __init__(self, reply):
        self.reply = reply
        self.received = None

    def invoke(self, state):
        self.received = state
        return {"messages": [HumanMessage(m["content"]) for m in state["messages"]] + [self.reply]}


def build_agent(monkeypatch, reply):
    captured = {}
    executor = FakeExecutor(reply)

    def fake_create_agent(model, tools, system_prompt):
        captured.update(model=model, tools=tools, system_prompt=system_prompt)
        return executor

    monkeypatch.setattr(agent_service, "get_chat_model", lambda: "modello-finto")
    monkeypatch.setattr(agent_service, "create_agent", fake_create_agent)
    return agent_service.Agent(), executor, captured


def test_prompt_di_sistema_passato_a_create_agent(monkeypatch):
    agent, _, captured = build_agent(monkeypatch, AIMessage("ok"))

    assert captured["model"] == "modello-finto"
    assert len(captured["tools"]) == 4
    assert "Sei un travel planner" in captured["system_prompt"]
    assert str(agent.current_datetime.date()) in captured["system_prompt"]


def test_run_restituisce_la_conversazione_senza_prompt_di_sistema(monkeypatch):
    agent, executor, _ = build_agent(monkeypatch, AIMessage("Ecco il tuo viaggio"))
    messages = [{"role": "user", "content": "Vorrei andare a Roma"}]

    result = agent.run(messages)

    # Il prompt di sistema non viene più mescolato ai messaggi dell'utente
    assert executor.received == {"messages": messages}
    assert [m.content for m in result] == ["Vorrei andare a Roma", "Ecco il tuo viaggio"]


def test_contenuto_a_blocchi_riportato_a_testo(monkeypatch):
    reply = AIMessage(content=[{"type": "text", "text": "Ciao "}, {"type": "text", "text": "Roma"}])
    agent, _, _ = build_agent(monkeypatch, reply)

    result = agent.run([{"role": "user", "content": "Ciao"}])

    assert result[-1].content == "Ciao Roma"
