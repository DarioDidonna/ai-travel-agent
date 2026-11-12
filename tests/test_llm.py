import pytest

from travel_agent_api import llm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_LIGHT_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "chiave-di-test")
    monkeypatch.setenv("OPENAI_API_KEY", "chiave-di-test")


def model_name(model):
    return getattr(model, "model_name", None) or model.model


@pytest.mark.parametrize(
    "provider, main, light",
    [
        ("gemini", "gemini-3.5-flash", "gemini-flash-lite-latest"),
        ("ollama", "qwen3:4b", "qwen3:4b"),
        ("openai", "gpt-4o", "gpt-4o-mini"),
    ],
)
def test_modelli_predefiniti(monkeypatch, provider, main, light):
    monkeypatch.setenv("LLM_PROVIDER", provider)

    assert model_name(llm.get_chat_model()) == main
    assert model_name(llm.get_chat_model(light=True)) == light


def test_modelli_personalizzati_dal_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "modello-principale")
    monkeypatch.setenv("LLM_LIGHT_MODEL", "modello-leggero")

    assert model_name(llm.get_chat_model()) == "modello-principale"
    assert model_name(llm.get_chat_model(light=True)) == "modello-leggero"


def test_provider_non_valido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "inesistente")

    with pytest.raises(ValueError, match="LLM_PROVIDER non valido"):
        llm.get_chat_model()


def test_i_tool_interni_usano_il_modello_leggero():
    """chain_travel_plan e chain_historical_expert risparmiano la quota del modello principale."""
    from travel_agent_api.tools import chain_historical_expert, chain_travel_plan

    for module in (chain_historical_expert, chain_travel_plan):
        source = open(module.__file__, encoding="utf-8").read()
        assert "get_chat_model(light=True)" in source, module.__name__
