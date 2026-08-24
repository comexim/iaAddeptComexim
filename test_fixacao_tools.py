import json
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

if "redis" not in sys.modules:
    redis_stub = types.ModuleType("redis")
    redis_stub.from_url = lambda *_args, **_kwargs: None
    sys.modules["redis"] = redis_stub

if "langchain_core.tools" not in sys.modules:
    langchain_core_stub = types.ModuleType("langchain_core")
    tools_stub = types.ModuleType("langchain_core.tools")

    class StructuredToolStub:
        @classmethod
        def from_function(cls, **kwargs):
            return kwargs

    tools_stub.StructuredTool = StructuredToolStub
    sys.modules["langchain_core"] = langchain_core_stub
    sys.modules["langchain_core.tools"] = tools_stub

if "app.core.config" not in sys.modules:
    core_stub = types.ModuleType("app.core")
    core_stub.__path__ = []
    config_stub = types.ModuleType("app.core.config")
    config_stub.settings = types.SimpleNamespace(redis_url="redis://localhost")
    fixacao_client_stub = types.ModuleType("app.core.fixacao_api_client")
    fixacao_client_stub.fixacao_api_client = types.SimpleNamespace(
        cadastrar_fixacao=AsyncMock()
    )
    sys.modules["app.core"] = core_stub
    sys.modules["app.core.config"] = config_stub
    sys.modules["app.core.fixacao_api_client"] = fixacao_client_stub

if "app.agents.hedge_tools" not in sys.modules:
    import app.agents as agents_package

    hedge_tools_stub = types.ModuleType("app.agents.hedge_tools")

    class HedgeToolsStub:
        def __init__(self, *_args, **_kwargs):
            pass

        def clear(self):
            pass

        def prepare_offer(self, **_kwargs):
            pass

    hedge_tools_stub.HedgeTools = HedgeToolsStub
    sys.modules["app.agents.hedge_tools"] = hedge_tools_stub
    agents_package.hedge_tools = hedge_tools_stub

from app.agents.fixacao_tools import FixacaoTools


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, _ttl, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class FixacaoToolsTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeRedis()
        self.tool = FixacaoTools("teste")
        self.redis_patch = patch.object(self.tool, "_redis", return_value=self.fake)
        self.redis_patch.start()
        self.value_type_patch = patch.object(
            self.tool, "_load_contract_value_type", return_value=None
        )
        self.value_type_patch.start()

    def tearDown(self):
        self.value_type_patch.stop()
        self.redis_patch.stop()

    def test_coleta_todos_campos_e_exige_confirmacao(self):
        send = AsyncMock(return_value={"ok": True})
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            summary = self.tool.cadastrar_valor_contrato(contratode_venda="011706", valor_fixacao=321.321)
            self.assertTrue(summary.startswith("AGUARDANDO_CONFIRMACAO:"))
            self.assertEqual(send.await_count, 0)
            self.assertIn("011706", summary)
            self.assertTrue(self.tool.is_awaiting_confirmation())
            self.assertEqual(send.await_count, 0)

            success = self.tool.cadastrar_valor_contrato(confirmar_envio=True)
            self.assertTrue(success.startswith("FIXACAO_CADASTRADA_SUCESSO:"))
            self.assertEqual(send.await_count, 1)
            self.assertEqual(send.await_args.args[0], {
                "contratodeVenda": "011706",
                "fixacaoContrato": [{"valorFixacao": 321.321}],
            })

    def test_correcao_exige_novo_resumo_e_nova_confirmacao(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "011706", "valorFixacao": 321.321, "diferencial": -10,
            "tipoValor": "5", "fixadorPreco": "E", "aguardando_confirmacao": True,
        })
        send = AsyncMock(return_value={"ok": True})
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            result = self.tool.cadastrar_valor_contrato(valor_fixacao=400, confirmar_envio=True)
            self.assertTrue(result.startswith("AGUARDANDO_CONFIRMACAO:"))
            self.assertEqual(send.await_count, 0)

            result = self.tool.cadastrar_valor_contrato(confirmar_envio=True)
            self.assertTrue(result.startswith("FIXACAO_CADASTRADA_SUCESSO:"))
            self.assertEqual(send.await_count, 1)

    def test_erro_funcional_da_api_nao_vira_sucesso(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "012324", "valorFixacao": 150.20,
            "aguardando_confirmacao": True,
        })
        send = AsyncMock(side_effect=RuntimeError(
            "Nao sera possivel fixar o contrato. Contrato ja fixado em 17/07/2026"
        ))
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            result = self.tool.cadastrar_valor_contrato(confirmar_envio=True)
            self.assertTrue(result.startswith("ERRO_API:"))
            self.assertIn("Contrato ja fixado em 17/07/2026", result)
            # Após falha funcional, preserva contrato e valor para permitir
            # "já ajustei, fixe agora" sem perguntar tudo novamente.
            pending = json.loads(self.fake.get(self.tool.key))
            self.assertEqual(pending["contratodeVenda"], "012324")
            self.assertEqual(pending["valorFixacao"], 150.20)
            self.assertTrue(pending["aguardando_confirmacao"])

    def test_chamada_sem_parametros_nao_confirma(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "012325", "valorFixacao": 124.50,
            "aguardando_confirmacao": True,
        })
        send = AsyncMock(return_value={"success": True})
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            result = self.tool.cadastrar_valor_contrato()
            self.assertTrue(result.startswith("AGUARDANDO_CONFIRMACAO:"))
            self.assertEqual(send.await_count, 0)

    def test_normaliza_fixador_por_codigo_ou_descricao(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "012302", "valorFixacao": 214.30,
            "aguardando_confirmacao": True,
        })
        result = self.tool.cadastrar_valor_contrato(fixador_preco="Importador")
        self.assertTrue(result.startswith("AGUARDANDO_CONFIRMACAO:"))
        self.assertEqual(json.loads(self.fake.get(self.tool.key))["fixadorPreco"], "I")
        summary = self.tool.format_pending_summary()
        self.assertIn("Fixador do preço: Importador (I)", summary)
        self.assertIn("Você confirma o envio", summary)

    def test_confirmation_uses_contract_value_type_without_currency_symbol(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "108/26", "valorFixacao": 230.50,
            "tipoValorContrato": "CTS/LB", "aguardando_confirmacao": True,
        })

        summary = self.tool.format_pending_summary()

        self.assertIn("Valor da fixação: 230,50 CTS/LB", summary)
        self.assertNotIn("R$", summary)

    def test_novo_cadastro_pode_limpar_estado_anterior(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "012302", "valorFixacao": 214.30,
            "diferencial": -23, "fixadorPreco": "I",
            "aguardando_confirmacao": True,
        })
        self.tool.clear_pending()
        self.assertIsNone(self.fake.get(self.tool.key))

    def test_normaliza_tipos_de_valor(self):
        cases = {
            "C": "C", "cts/lb": "C", "centavos por libra": "C",
            "K": "K", "em kg": "K", "quilogramas": "K",
            "5": "5", "saca de 50 kg": "5", "US$ 50KG": "5",
            "6": "6", "tipo 59 kg": "6", "US$ 59KG": "6",
            "T": "T", "em toneladas": "T", "valor por tonelada": "T",
        }
        for informed, expected in cases.items():
            with self.subTest(informed=informed):
                self.assertEqual(self.tool.normalize_tipo_valor(informed), expected)
        self.assertIsNone(self.tool.normalize_tipo_valor("tipo desconhecido"))

    def test_monta_identificador_do_contrato_para_api(self):
        self.assertEqual(
            self.tool.build_contract_identifier("012276"),
            {"contratodeVenda": "012276"},
        )
        self.assertEqual(
            self.tool.build_contract_identifier("352/26"),
            {"numeroVenda": "352/26"},
        )
        self.assertEqual(
            self.tool.build_contract_identifier("352/26a"),
            {"numeroVenda": "352/26", "letraVenda": "A"},
        )

    def test_identifica_estado_aguardando_valor(self):
        self.fake.data[self.tool.key] = json.dumps({"contratodeVenda": "352/26"})
        self.assertTrue(self.tool.is_waiting_for_value())
        self.tool.cadastrar_valor_contrato(valor_fixacao=200.32, diferencial=12)
        self.assertFalse(self.tool.is_waiting_for_value())

    def test_confirmacao_com_dados_repetidos_nao_e_alteracao(self):
        self.fake.data[self.tool.key] = json.dumps({
            "contratodeVenda": "012325", "valorFixacao": 125.42,
            "aguardando_confirmacao": True,
        })
        send = AsyncMock(return_value={"success": True})
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            result = self.tool.cadastrar_valor_contrato(
                contratode_venda="012325",
                valor_fixacao=125.42,
                confirmar_envio=True,
            )
            self.assertTrue(result.startswith("FIXACAO_CADASTRADA_SUCESSO:"))
            self.assertEqual(send.await_count, 1)

    def test_confirmacao_prematura_com_dados_novos_prepara_proximo_sim(self):
        send = AsyncMock(return_value={"success": True})
        with patch("app.agents.fixacao_tools.fixacao_api_client.cadastrar_fixacao", send):
            result = self.tool.cadastrar_valor_contrato(
                contratode_venda="012305",
                valor_fixacao=211.11,
                tipo_valor="K",
                confirmar_envio=True,
            )
            self.assertTrue(result.startswith("AGUARDANDO_CONFIRMACAO:"))
            self.assertEqual(send.await_count, 0)
            self.assertTrue(self.tool.is_awaiting_confirmation())

            result = self.tool.cadastrar_valor_contrato(confirmar_envio=True)
            self.assertTrue(result.startswith("FIXACAO_CADASTRADA_SUCESSO:"))
            self.assertEqual(send.await_count, 1)


if __name__ == "__main__":
    unittest.main()
