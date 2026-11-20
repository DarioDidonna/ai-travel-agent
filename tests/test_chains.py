from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from travel_agent_api.tools import chain_historical_expert, chain_travel_plan
from travel_agent_api.tools.chain_travel_plan import TravelDayOutput, TravelPlanOutput

PLAN_PARAMS = {
    "start_date": "2027-02-05", "end_date": "2027-02-06", "destination": "Parigi",
    "travel_style": "culturale", "activities": "musei", "food_restriction": "vegetariana",
}


class FakeModel:
    """Modello finto: registra il prompt ricevuto e restituisce una risposta prefissata."""

    def __init__(self, reply):
        self.reply = reply
        self.prompt = None
        self.schema = None

    def _answer(self, prompt_value):
        self.prompt = prompt_value.to_string()
        return self.reply

    def with_structured_output(self, schema):
        self.schema = schema
        return RunnableLambda(self._answer)

    def as_runnable(self):
        """Per le catene che usano il modello direttamente (prompt | model)."""
        return RunnableLambda(self._answer)


def test_itinerario_strutturato_con_i_dati_del_viaggio(monkeypatch):
    plan = TravelPlanOutput(travel_plan=[
        TravelDayOutput(morning="Louvre", afternoon="Senna", evening="Cena"),
        TravelDayOutput(morning="Orsay", afternoon="Montmartre", evening="Teatro"),
    ])
    model = FakeModel(plan)
    used_light = []
    monkeypatch.setattr(chain_travel_plan, "get_chat_model", lambda light=False: used_light.append(light) or model)

    result = chain_travel_plan.chain_travel_plan.invoke({"params": PLAN_PARAMS})

    assert result == plan
    assert model.schema is TravelPlanOutput
    assert used_light == [True]  # modello leggero, quota separata
    for value in ("2027-02-05", "Parigi", "vegetariana", "Italian"):
        assert value in model.prompt


def test_esperto_storico_restituisce_testo(monkeypatch):
    model = FakeModel(AIMessage(content=[{"type": "text", "text": "Il Colosseo fu inaugurato nell'80 d.C."}]))
    monkeypatch.setattr(chain_historical_expert, "get_chat_model", lambda light=False: model.as_runnable())

    result = chain_historical_expert.chain_historical_expert.invoke({"input_text": "Colosseo"})

    assert result == "Il Colosseo fu inaugurato nell'80 d.C."
    assert "Colosseo" in model.prompt
    assert "historical expert" in model.prompt
