"""Contrato da tool de fixação em lote; executa somente com doubles offline."""
import json
import unittest
from unittest.mock import patch

from test_contract_batch_flow import MemoryRedis, ContractBatchFlow, FixacaoTools


class FixacaoToolsTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryRedis()
        self.tool = FixacaoTools("tool", True)
        p = patch.object(ContractBatchFlow, "_redis", return_value=self.store)
        p.start()
        self.addCleanup(p.stop)
        query = patch("app.agents.hedge_tools.sql_client.execute_procedure", return_value=[{"tipoValor": "CTS/LB"}])
        query.start()
        self.addCleanup(query.stop)

    def test_only_sale_number_and_value_are_required(self):
        result = self.tool.cadastrar_valor_contrato(numero_venda="7/27", valor_fixacao=0)
        self.assertIn("AGUARDANDO_CONFIRMACAO", result)
        self.assertTrue(self.tool.is_awaiting_confirmation())
        item = self.tool._batch_flow().load()["contratos"][0]
        self.assertEqual(item, {"numeroVenda": "007/27", "letraVenda": "", "valorFixacao": 0.0,
                                "tipoValor": "C", "tipoValorDescricao": "CTS/LB"})

    def test_optional_values_and_descriptions(self):
        self.tool.cadastrar_valor_contrato(numero_venda="7/27D", valor_fixacao=100, diferencial=-1, tipo_valor="cts/lb", fixador_preco="Importador")
        item = self.tool._batch_flow().load()["contratos"][0]
        self.assertEqual((item["tipoValor"], item["fixadorPreco"], item["diferencial"]), ("C", "I", -1))

    def test_same_contract_in_group_is_rejected(self):
        result = self.tool.cadastrar_valor_contrato(contratos_json=json.dumps([
            {"numeroVenda": "7/27D", "fixacaoContrato": [{"valorFixacao": 1}]},
            {"numeroVenda": "007/27", "letraVenda": "D", "fixacaoContrato": [{"valorFixacao": 2}]},
        ]))
        self.assertIn("repetido", result)

    def test_exactly_one_fixation_per_contract(self):
        for items in ([], [{"valorFixacao": 1}, {"valorFixacao": 2}]):
            result = self.tool.cadastrar_valor_contrato(contratos_json=json.dumps([
                {"numeroVenda": "7/27", "fixacaoContrato": items}]))
            self.assertIn("exatamente uma", result)

    def test_internal_identifier_is_forbidden(self):
        with self.assertRaises(ValueError):
            self.tool.build_contract_identifier("012329")
        self.assertEqual(self.tool.build_contract_identifier("7/27 D"), {"numeroVenda": "007/27", "letraVenda": "D"})
        self.assertIn("Não informe contratodeVenda", self.tool.cadastrar_valor_contrato(contratos_json='[{"contratodeVenda":"012329"}]'))

    def test_missing_value_is_not_confirmation(self):
        self.tool.cadastrar_valor_contrato(numero_venda="7/27")
        self.assertTrue(self.tool.is_waiting_for_value())
        self.assertIn("007/27", self.tool.format_pending_summary())

    def test_numeric_values_must_be_finite(self):
        for value in (float("inf"), float("nan")):
            self.assertIn("VALOR_INVALIDO", self.tool.cadastrar_valor_contrato(numero_venda="7/27", valor_fixacao=value))

    def test_extract_level_and_type_codes(self):
        self.assertEqual(self.tool.extract_fixation_value("fixe 7/27 em nível 221,25"), 221.25)
        for value, code in (("cts/lb", "C"), ("kg", "K"), ("50 kg", "5"), ("59 kg", "6"), ("tonelada", "T")):
            self.assertEqual(self.tool.normalize_tipo_valor(value), code)


if __name__ == "__main__":
    unittest.main()
