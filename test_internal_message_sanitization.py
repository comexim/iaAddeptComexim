import importlib
import asyncio
import sys
import types


def _stub_common_dependencies():
    config_mod = types.ModuleType("app.core.config")

    class Settings:
        llm_provider = "openai"
        formatter_model = "stub"
        formatter_temperature = 0
        openai_api_key = "stub"
        anthropic_api_key = "stub"
        enable_response_formatter = False
        evolution_api_url = "http://example.invalid"
        evolution_api_token = "stub"

    config_mod.settings = Settings()
    sys.modules["app.core.config"] = config_mod


def _load_formatter():
    _stub_common_dependencies()

    openai_mod = types.ModuleType("langchain_openai")
    anthropic_mod = types.ModuleType("langchain_anthropic")
    messages_mod = types.ModuleType("langchain_core.messages")
    prompt_mod = types.ModuleType("app.prompts.system_prompt")

    class DummyLLM:
        def __init__(self, *args, **kwargs):
            pass

    class DummyMessage:
        def __init__(self, content=""):
            self.content = content

    openai_mod.ChatOpenAI = DummyLLM
    anthropic_mod.ChatAnthropic = DummyLLM
    messages_mod.HumanMessage = DummyMessage
    messages_mod.SystemMessage = DummyMessage
    prompt_mod.FORMATTER_SYSTEM_PROMPT = "stub"
    sys.modules["langchain_openai"] = openai_mod
    sys.modules["langchain_anthropic"] = anthropic_mod
    sys.modules["langchain_core.messages"] = messages_mod
    sys.modules["app.prompts.system_prompt"] = prompt_mod

    return importlib.import_module("app.services.formatter").ResponseFormatter


def _load_whatsapp_service():
    _stub_common_dependencies()
    httpx_mod = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    httpx_mod.HTTPError = HTTPError
    httpx_mod.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx_mod
    return importlib.import_module("app.services.whatsapp").WhatsAppService


def test_formatter_removes_internal_preference_update_line():
    ResponseFormatter = _load_formatter()
    formatter = ResponseFormatter.__new__(ResponseFormatter)

    cleaned = formatter._limpar_markdown(
        "Resposta correta.\n\n_[Preferência atualizada: nivel_detalhe → medio]_"
    )

    assert "Resposta correta." in cleaned
    assert "Preferência atualizada" not in cleaned
    assert "nivel_detalhe" not in cleaned


def test_whatsapp_sanitizer_drops_internal_preference_message():
    WhatsAppService = _load_whatsapp_service()
    service = WhatsAppService()

    assert service._sanitize_outbound_text("_[Preferência atualizada: nivel_detalhe → medio]_") == ""
    assert service._sanitize_outbound_text("OK\n\n[Preferencia atualizada: tom → profissional]") == "OK"


def test_hedge_offer_and_recommendations_are_sent_as_one_message():
    ResponseFormatter = _load_formatter()
    formatter = ResponseFormatter.__new__(ResponseFormatter)
    text = (
        "Gostaria que eu fizesse o Hedge da bolsa?\n\n"
        "Quantidade de lotes recomendada: 5 lotes\n"
        "Mês/ano de fixação recomendado: dezembro/2026. "
        "Você pode informar outros dados."
    )

    messages = asyncio.run(formatter.format_response(text))

    assert messages == [text]
