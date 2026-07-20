import json
import unittest
from unittest.mock import AsyncMock, patch

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

    def tearDown(self):
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
            self.assertTrue(result.startswith("CONFIRMACAO_INVALIDA:"))
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
            self.assertIsNotNone(self.fake.get(self.tool.key))

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


if __name__ == "__main__":
    unittest.main()
