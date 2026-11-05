"""Testes offline: Redis em memória, transporte/SQL simulados, rede bloqueada."""
import asyncio
from copy import deepcopy
import json
import socket
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Não carrega .env nem inicializa conexões externas durante os testes.
config = types.ModuleType("app.core.config")
config.settings = types.SimpleNamespace(
    redis_url="redis://localhost", cmx_api_url="https://cmx.test",
    cmx_token_path="/token", cmx_fixacao_path="/z24", cmx_hedge_path="/z03",
    cmx_f3_path="/f3", cmx_tenant_id="01,05", cmx_verify_ssl=False,
    cmx_username="user", cmx_password="password",
)
sys.modules.setdefault("app.core.config", config)
for name in ("redis", "httpx"):
    try:
        __import__(name)
    except ImportError:
        stub = types.ModuleType(name)
        stub.from_url = MagicMock()
        stub.AsyncClient = MagicMock()
        for exception_name in ("ConnectError", "ConnectTimeout", "PoolTimeout", "ReadTimeout", "WriteError"):
            setattr(stub, exception_name, type(exception_name, (Exception,), {}))
        sys.modules[name] = stub
try:
    import langchain_core.tools
except ImportError:
    stub = types.ModuleType("langchain_core.tools")
    stub.StructuredTool = types.SimpleNamespace(from_function=lambda **kwargs: kwargs)
    sys.modules["langchain_core"] = types.ModuleType("langchain_core")
    sys.modules["langchain_core.tools"] = stub
database = types.ModuleType("app.core.database")
database.sql_client = MagicMock()
sys.modules.setdefault("app.core.database", database)

from app.agents.contract_batch_flow import ContractBatchFlow, identifier, identity
from app.agents.fixacao_tools import FixacaoTools
from app.agents.hedge_tools import HedgeTools
from app.core.fixacao_api_client import FixacaoApiClient, OperationNotSent, OperationRejected


class MemoryRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value

    def set(self, key, value, nx=False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    def delete(self, key):
        self.data.pop(key, None)

    def eval(self, script, count, *args):
        if count == 3:
            key, lock, record_key, owner, updated, record, lock_action = args
            current = json.loads(self.get(key) or "{}")
            if current.get("operation_id") != owner or current.get("stage") not in ContractBatchFlow.BLOCKED:
                return 0
            self.setex(key, 86400, updated)
            self.setex(record_key, 604800, record)
            if lock_action == "release" and self.get(lock) == owner:
                self.delete(lock)
            return 1
        key, owner = args
        if self.get(key) == owner:
            self.delete(key)
            return 1
        return 0


def fixation_result(successes=(), failures=(), level=102.10):
    return {
        "code": "201" if successes else "400", "message": "Resultado fixação",
        "fixados": len(successes), "naoFixados": len(failures),
        "contratosFixados": [{"contrato": "012329", "venda": identifier(ref)[0], "letra": identifier(ref)[1], "nivel": level} for ref in successes],
        "contratosNaoFixados": [{"contrato": "012328", "venda": identifier(ref)[0], "letra": identifier(ref)[1], "motivos": ["Motivo " + ref]} for ref in failures],
    }


def hedge_result(successes=(), failures=()):
    return {"code": "201" if successes else "400", "message": "Resultado Hedge",
            "registrados": len(successes), "naoRegistrados": len(failures),
            "movimentosRegistrados": [{"contrato": ref, "valor": 102.10, "lotes": 2, "corretora": "A14"} for ref in successes],
            "movimentosNaoRegistrados": [{"contrato": ref, "motivos": ["Motivo " + ref]} for ref in failures]}


def protheus_fixation_failure():
    return {
        "code": "400", "message": "Nenhum contrato foi fixado. Verifique!",
        "fixados": 0, "naoFixados": 3, "contratosFixados": [],
        "contratosNaoFixados": [
            {"contrato": "012327", "venda": "374/26", "letra": "D",
             "motivos": ["Fixador - Preenchimento Obrigatorio para Preco a Fixar"]},
            {"contrato": "012329", "venda": "375/26", "letra": " ",
             "motivos": ["Fixador - Preenchimento Obrigatorio para Preco a Fixar"]},
            {"contrato": "", "venda": "037/26", "letra": "",
             "motivos": ["Contrato Exportação não encontrado."]},
        ],
    }


class BatchFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = MemoryRedis()
        self.flow = ContractBatchFlow("teste", True)
        self.patches = [
            patch.object(ContractBatchFlow, "_redis", return_value=self.store),
            patch("app.agents.hedge_tools.sql_client.execute_procedure", return_value=[
                {"tipoValor": "CTS/LB", "sacas": 576.60047033809, "mesFixacao": "202612"}]),
            patch("socket.socket.connect", side_effect=AssertionError("Rede proibida no teste")),
        ]
        for item in self.patches:
            mock = item.start()
            if item is self.patches[1]:
                self.contract_query = mock
            self.addCleanup(item.stop)
        self.fix_send = AsyncMock()
        self.hedge_send = AsyncMock()
        for name, mock in (("cadastrar_fixacao", self.fix_send), ("cadastrar_hedge", self.hedge_send)):
            p = patch("app.agents.contract_batch_flow.fixacao_api_client." + name, mock)
            p.start()
            self.addCleanup(p.stop)

    async def prepare(self):
        return await self.flow.handle("fixe 374/26D e 375/26 em nível 221.25 e 37/26 em nível 219.05")

    async def fixed(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        await self.flow.handle("sim")

    def test_identifier_and_duplicates(self):
        self.assertEqual(identifier("7/27 D"), ("007/27", "D"))
        self.assertNotEqual(identity({"numeroVenda": "375/26"}), identity({"venda": "375/26", "letra": "D"}))
        for ref in ("1234/26", "1/2", "1/2026", "012329", "007/27AB"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                identifier(ref)
        with self.assertRaisesRegex(ValueError, "mais de uma vez"):
            self.flow.parse_contracts("7/27D, 007/27 D")

    def test_identifier_normalizes_letters_and_preserves_conflict_validation(self):
        for value, letter, expected in (
            ("375/26", " ", ("375/26", "")),
            ("375/26", "\t  ", ("375/26", "")),
            ("7/27d", None, ("007/27", "D")),
            ("7/27 d", " d ", ("007/27", "D")),
            ("7/27D", "d", ("007/27", "D")),
            ("7/27", "d", ("007/27", "D")),
        ):
            with self.subTest(value=value, letter=letter):
                self.assertEqual(identifier(value, letter), expected)
        for value, letter in (("7/27D", "e"), ("7/27", "ab"), ("7/27", "1"), ("7/27D", " ")):
            with self.subTest(value=value, letter=letter), self.assertRaises(ValueError):
                identifier(value, letter)
        with self.assertRaisesRegex(ValueError, "mais de uma vez"):
            self.flow.parse_contracts("7/27d, 007/27D")

    async def test_mixed_groups_confirmation_and_exact_payload(self):
        summary = await self.prepare()
        self.assertIn("374/26D", summary)
        self.assertEqual([i["valorFixacao"] for i in self.flow.load()["contratos"]], [221.25, 221.25, 219.05])
        self.fix_send.assert_not_called()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        output = await self.flow.handle("confirmo")
        body = self.fix_send.await_args.args[0]
        self.assertEqual(body["contratos"][1], {"numeroVenda": "375/26", "letraVenda": "", "fixacaoContrato": [{"valorFixacao": 221.25, "tipoValor": "C"}]})
        self.assertNotIn("contratodeVenda", json.dumps(body))
        self.assertIn("Hedge", output)

    async def test_partial_retry_preserves_snapshot_corrections_reasons_and_successes(self):
        await self.prepare()
        initial = deepcopy(self.flow.load()["contratosIniciais"])
        self.fix_send.return_value = fixation_result(("374/26D",), ("375/26", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        await self.flow.handle("375/26 nível 225 diferencial -2 tipo K fixador Exportador")
        self.assertEqual(self.fix_send.await_count, 1)
        self.fix_send.return_value = fixation_result((), ("375/26",))
        await self.flow.handle("sim")
        self.assertEqual(self.flow.load()["contratosIniciais"], initial)
        pending = self.flow.load()["contratosAindaNaoFixados"]
        self.assertEqual(pending[0]["valorFixacao"], 225)
        self.assertEqual(pending[1]["motivos"], ["Motivo 037/26"])
        await self.flow.handle("sim")
        await self.flow.handle("3")
        self.fix_send.return_value = fixation_result(("375/26", "037/26"))
        await self.flow.handle("sim")
        body = self.fix_send.await_args.args[0]
        self.assertEqual(len(body["contratos"]), 2)
        self.assertEqual(body["contratos"][0]["fixacaoContrato"][0]["valorFixacao"], 225)
        self.assertEqual(len(self.flow.load()["contratosFixadosAcumulado"]), 3)

    async def test_subset_success_returns_to_failure_flow(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result((), ("374/26D", "375/26", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        await self.flow.handle("375/26 nivel 222")
        self.fix_send.return_value = fixation_result(("375/26",))
        self.assertIn("listagem", await self.flow.handle("sim"))
        listing = await self.flow.handle("sim")
        self.assertIn("037/26", listing)
        self.assertIn("374/26D", listing)

    async def test_completed_contract_and_outside_initial_are_rejected(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("375/26",), ("374/26D", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        for ref in ("375/26", "999/26"):
            self.assertIn("não está entre", await self.flow.handle(f"{ref} nivel 100"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_edit_after_summary_requires_new_confirmation(self):
        await self.prepare()
        await self.flow.handle("374/26D nivel 222, sim")
        self.fix_send.assert_not_called()
        self.assertEqual(self.flow.load()["stage"], "confirm_fix")

    async def test_collect_missing_value_and_optional_fields(self):
        output = await self.flow.handle("fixe o contrato 7/27")
        self.assertIn("opcionais", output)
        summary = await self.flow.handle("200,32 com -12")
        self.assertIn("200,32", summary)
        self.assertEqual(self.flow.load()["contratos"][0]["diferencial"], -12)

    async def test_collect_only_missing_value_preserves_other_contract(self):
        await self.flow.handle("fixe 375/26 nivel 100 e 374/26D")
        await self.flow.handle("200")
        self.assertEqual([i["valorFixacao"] for i in self.flow.load()["contratos"]], [100, 200])

    async def test_value_before_identifier_is_preserved(self):
        await self.flow.handle("fixe em nivel 200")
        result = await self.flow.handle("375/26")
        self.assertIn("200", result)
        self.assertEqual(self.flow.load()["stage"], "confirm_fix")

    async def test_total_failure_can_finish_without_hedge(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result((), ("374/26D", "375/26", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        report = await self.flow.handle("1")
        self.assertIn("Nenhum contrato elegível", report)
        self.assertEqual(self.flow.load()["stage"], "done")

    async def test_hedge_selection_uses_returned_level_and_preserves_required_aa(self):
        await self.fixed()
        self.assertIn("corretora", await self.flow.handle("sim 375/26"))
        summary = await self.flow.handle("A14")
        self.assertIn("Lanc. AA: Nao", summary)
        self.assertIn("Valor: 102,1", summary)
        self.hedge_send.return_value = hedge_result(("375/26",))
        report = await self.flow.handle("sim")
        body = self.hedge_send.await_args.args[0]
        self.assertEqual(len(body["movimentos"]), 1)
        self.assertEqual(body["movimentos"][0]["corret"], "A14")
        self.assertEqual(body["movimentos"][0]["account"], "A14")
        self.assertIn("375/26 = Nível: 102,1 — Hedge = SIM - Lotes: 2", report)
        self.assertIn("374/26D = Nível: 102,1 — Hedge = NAO", report)

    async def test_friendly_fixation_summary_preserves_exact_request_and_confirmed_level(self):
        summary = self.flow.prepare_fixation([
            ("374/26D", {"valorFixacao": 110.1, "tipoValor": "C", "fixadorPreco": "E", "diferencial": -1}),
            ("375/26", {"valorFixacao": 105.1, "tipoValor": "C", "fixadorPreco": "I", "diferencial": 0}),
            ("037/26", {"valorFixacao": 99.87}),
        ])
        self.assertIn("- 374/26D\n\t- Valor da Fixação: 110,1 CTS/LB\n\t- Fixador do Preço: Exportador\n\t- Diferencial: -1", summary)
        self.assertIn("Fixador do Preço: Importador\n\t- Diferencial: 0", summary)
        self.assertNotIn(";", summary)
        self.assertIn("- 037/26\n\t- Valor da Fixação: 99,87", summary)
        self.assertNotIn("valorFixacao", summary)
        result = fixation_result(("374/26D",), ("375/26", "037/26"), level=112.3)
        result["contratosNaoFixados"][0]["motivos"] = ["Fixador obrigatório", "Outro motivo retornado"]
        result["contratosNaoFixados"][1].update(contrato="", motivos=["Contrato Exportação não encontrado."])
        original = deepcopy(result)
        self.fix_send.return_value = result
        output = await self.flow.handle("sim")
        self.assertIn("- Venda: 374/26D\n- Nível: 112,3 CTS/LB", output)
        self.assertNotIn("Nível: 110,1", output)
        self.assertIn("- Contrato: \"\"\n- Venda: 037/26\n- Motivo: Contrato Exportação não encontrado.", output)
        self.assertIn("- Motivos:\n\t1. Fixador obrigatório\n\t2. Outro motivo retornado", output)
        self.assertEqual(result, original)
        self.assertEqual(self.fix_send.await_args.args[0], {"contratos": [
            {"numeroVenda": "374/26", "letraVenda": "D", "fixacaoContrato": [
                {"valorFixacao": 110.1, "diferencial": -1.0, "tipoValor": "C", "fixadorPreco": "E"}]},
            {"numeroVenda": "375/26", "letraVenda": "", "fixacaoContrato": [
                {"valorFixacao": 105.1, "diferencial": 0.0, "tipoValor": "C", "fixadorPreco": "I"}]},
            {"numeroVenda": "037/26", "letraVenda": "", "fixacaoContrato": [{"valorFixacao": 99.87, "tipoValor": "C"}]},
        ]})
        listing = await self.flow.handle("sim")
        self.assertIn("- 375/26:\nNível: 105,1 CTS/LB\nMotivos:\n\t1. Fixador obrigatório\n\t2. Outro motivo retornado", listing)
        self.assertIn("- 037/26:\nNível: 99,87 CTS/LB\nMotivo: Contrato Exportação não encontrado.", listing)
        self.assertNotIn("Dados:", listing)

    async def test_numbered_broker_choice_and_friendly_hedge_keep_exact_request(self):
        self.flow.prepare_fixation([("374/26D", {"valorFixacao": 100, "mesfix": "DEZ", "anofix": "2026", "lotes": 1})])
        self.fix_send.return_value = fixation_result(("374/26D",), level=110.1)
        await self.flow.handle("sim")
        question = await self.flow.handle("sim")
        self.assertTrue(question.startswith("Qual é a corretora da bolsa?\nContrato 374/26D:\nOpções:\n1 - Adm13"))
        self.assertIn("4 - Adm14", question)
        self.assertIn("10 - BTGPactual", question)
        for invalid in ("0", "11"):
            self.assertIn("Qual é a corretora", await self.flow.handle(invalid))
            self.assertNotIn("corret", self.flow.load()["movimentos"][0])
        summary = await self.flow.handle("4")
        self.assertIn("Contrato 374/26D:\n- Mes Fix: DEZ\n- Ano Fix: 2026\n- Lotes: 1\n- Valor: 110,10\n- Corretora: A14\n- Lanc. AA: Nao", summary)
        self.assertNotIn("account", summary)
        self.hedge_send.return_value = hedge_result(("374/26D",))
        output = await self.flow.handle("sim")
        self.assertEqual(self.hedge_send.await_args.args[0], {"movimentos": [{
            "mesfix": "DEZ", "anofix": "2026", "lotes": 1, "valor": 110.1,
            "corret": "A14", "operac": "FV", "account": "A14", "ctrex": "374/26D", "tipo": "C", "lancaa": "Nao",
        }]})
        self.assertIn("Movimentos registrados:\n- Contrato: 374/26D\n- Lotes: 2\n- Valor: 102,1\n- Corretora: A14", output)
        self.assertIn("Movimentos não registrados:\nNenhum", output)
        self.assertIn("Relatório final de fixação e Hedge:", output)
        # O retorno confirmado tem dois lotes; a tentativa tinha um.
        self.assertIn("374/26D = Nível: 110,1 — Hedge = SIM - Lotes: 2", output)

    def test_broker_numbers_are_scoped_to_broker_question(self):
        helper = HedgeTools("parser")
        codes = ("A13", "RJO", "NDF", "A14", "SCD", "HED", "MAR", "MAO", "FCS", "ICE")
        for index, code in enumerate(codes, 1):
            for field in ("corret", "account"):
                values = helper.remember_from_text({}, str(index), expected=field)
                self.assertEqual((values["corret"], values["account"]), (code, code))
        self.assertIsNone(helper.parse_known_broker("4"))
        self.assertNotIn("corret", helper.remember_from_text({}, "4", expected="lotes"))
        self.assertEqual(helper.remember_from_text({}, "opção 4", expected="corret")["corret"], "A14")

    def test_unit_and_reason_formatting_without_mutating_source(self):
        for code, label in (("C", "CTS/LB"), ("K", "KG"), ("5", "50 KG"), ("6", "59 KG"), ("T", "TON")):
            self.assertEqual(self.flow.display_value(110.1, {"tipoValor": code}), f"110,1 {label}")
        self.assertEqual(self.flow.display_value(110.1), "110,1")
        self.assertEqual(self.flow.display_number(100), "100")
        self.assertEqual(self.flow.display_number(0), "0")
        self.assertEqual(self.flow.reason_lines({"motivo": "Um motivo"}), ["Motivo: Um motivo"])
        self.assertEqual(self.flow.reason_lines({"motivos": "Um motivo"}), ["Motivo: Um motivo"])

    async def test_singular_api_reason_is_preserved_in_failure_and_final_reports(self):
        await self.prepare()
        result = fixation_result(("374/26D",), ("375/26", "037/26"))
        result["contratosNaoFixados"][0].pop("motivos")
        result["contratosNaoFixados"][0]["motivo"] = "Um motivo"
        result["contratosNaoFixados"][1]["motivos"] = ["Primeiro", "Segundo"]
        self.fix_send.return_value = result
        await self.flow.handle("sim")
        listing = await self.flow.handle("sim")
        self.assertIn("Motivo: Um motivo", listing)
        final = await self.flow.handle("1")
        self.assertIn("Hedge", final)
        report = self.flow.final_report(self.flow.load(), hedge=True)
        self.assertIn("- 375/26 = Motivo: Um motivo", report)
        self.assertIn("- 037/26 = Motivos:\n\t1. Primeiro\n\t2. Segundo", report)

    async def hedge_ready(self):
        await self.fixed()
        await self.flow.handle("sim corretora A14")
        self.assertEqual(self.flow.load()["stage"], "confirm_hedge")

    async def test_offer_part_waits_and_accepts_contracts_in_a_sentence(self):
        await self.fixed()
        self.assertIn("Quais contratos", await self.flow.handle("parte"))
        self.assertEqual(self.flow.load()["stage"], "offer")
        self.assertNotIn("movimentos", self.flow.load())
        await self.flow.handle("Quero apenas o contrato 375/26 corretora A13")
        self.assertEqual([identity(i) for i in self.flow.load()["movimentos"]], ["375/26"])
        self.hedge_send.assert_not_called()

    async def test_batch_correction_exclusion_preserves_selection_and_final_report(self):
        await self.hedge_ready()
        fixed = deepcopy(self.flow.load()["contratosFixadosAcumulado"])
        await self.flow.handle("nao")
        summary = await self.flow.handle("Corrija o Contrato 375/26 para 2 lotes contra a corretora A13 e AA Sim e exclua o contrato 374/26D")
        self.assertIn("Corretora: A13\n- Lanc. AA: Sim", summary)
        self.assertIn("Contrato 037/26:", summary)
        self.assertNotIn("Contrato 374/26D:", summary)
        data = self.flow.load()
        for field in ("movimentos", "movimentosIniciais", "movimentosAindaNaoRegistrados"):
            self.assertEqual({identity(i) for i in data[field]}, {"375/26", "037/26"})
        self.assertEqual(data["contratosFixadosAcumulado"], fixed)
        self.assertEqual(data["movimentos"][0]["account"], "A13")
        summary = await self.flow.handle("037/26 3 lotes")
        self.assertIn("Corretora: A13\n- Lanc. AA: Sim", summary)
        self.hedge_send.assert_not_called()
        self.hedge_send.return_value = hedge_result(("375/26", "037/26"))
        report = await self.flow.handle("sim")
        self.assertIn("374/26D = Nível: 102,1 — Hedge = NAO", report)
        self.assertNotIn("VERIFICAR", report)
        self.assertEqual({i["ctrex"] for i in self.hedge_send.await_args.args[0]["movimentos"]}, {"375/26", "037/26"})

    async def test_exclude_all_discards_only_hedge_without_sending(self):
        await self.hedge_ready()
        report = await self.flow.handle("exclua 374/26D, 375/26 e 037/26")
        data = self.flow.load()
        self.assertEqual(data["stage"], "done")
        for field in ("movimentos", "movimentosIniciais", "movimentosAindaNaoRegistrados"):
            self.assertEqual(data[field], [])
        self.assertEqual(len(data["contratosFixadosAcumulado"]), 3)
        self.assertEqual(report.count("Hedge = NAO"), 3)
        self.hedge_send.assert_not_called()

    async def test_invalid_batch_is_atomic_and_aa_is_validated(self):
        await self.hedge_ready()
        original = self.flow.load()
        for message in ("exclua 374/26D e corrija 375/26 0 lotes", "375/26 AA talvez", "exclua 999/26", "corrija 375/26 3 lotes e exclua 375/26"):
            self.assertIn("Verifique", await self.flow.handle(message))
            self.assertEqual(self.flow.load(), original)
        self.hedge_send.assert_not_called()

    async def test_exclusion_during_broker_collection_and_offer_exit(self):
        await self.fixed()
        await self.flow.handle("todos")
        summary = await self.flow.handle("exclua 374/26D")
        self.assertIn("corretora", summary)
        self.assertEqual({identity(i) for i in self.flow.load()["movimentos"]}, {"375/26", "037/26"})
        summary = await self.flow.handle("corretora A13")
        self.assertEqual(self.flow.load()["stage"], "confirm_hedge")
        self.assertEqual(summary.count("Corretora: A13"), 2)
        self.hedge_send.assert_not_called()
        await self.flow.handle("sair")
        await self.fixed()
        report = await self.flow.handle("sair")
        self.assertIn("Relatório sintético", report)
        self.assertEqual(self.flow.load()["stage"], "done")

    async def test_aa_defaults_to_no_despite_previous_metadata_and_preserves_precision(self):
        self.flow.prepare_fixation([("375/26", {"valorFixacao": 100, "corret": "A13", "lancaa": "Sim"})])
        self.fix_send.return_value = fixation_result(("375/26",), level=101.111)
        await self.flow.handle("sim")
        summary = await self.flow.handle("todos")
        self.assertIn("Lanc. AA: Nao", summary)
        self.assertIn("Valor: 101,111", summary)
        self.assertEqual(self.flow.load()["movimentos"][0]["valor"], 101.111)

    async def test_excluded_contract_never_returns_as_pending_after_partial_result(self):
        await self.hedge_ready()
        await self.flow.handle("exclua 374/26D")
        initial = deepcopy(self.flow.load()["movimentosIniciais"])
        self.hedge_send.return_value = hedge_result(("375/26",), ("037/26",))
        await self.flow.handle("sim")
        self.assertEqual([identity(i) for i in self.flow.load()["movimentosAindaNaoRegistrados"]], ["037/26"])
        await self.flow.handle("nao")
        await self.flow.handle("2")
        self.assertIn("antes do primeiro envio", await self.flow.handle("exclua 037/26"))
        await self.flow.handle("037/26 3 lotes AA Sim")
        self.assertEqual(self.flow.load()["movimentosIniciais"], initial)
        self.hedge_send.return_value = hedge_result(("037/26",))
        report = await self.flow.handle("sim")
        self.assertEqual(self.hedge_send.await_count, 2)
        self.assertEqual([i["ctrex"] for i in self.hedge_send.await_args.args[0]["movimentos"]], ["037/26"])
        self.assertIn("374/26D = Nível: 102,1 — Hedge = NAO", report)
        self.assertNotIn("VERIFICAR", report)

    async def test_legacy_retry_keeps_initial_snapshot(self):
        await self.hedge_ready()
        self.hedge_send.return_value = hedge_result(("375/26",), ("374/26D", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        data = self.flow.load()
        data.pop("hedge_submitted")
        initial = deepcopy(data["movimentosIniciais"])
        self.flow.save(data)
        await self.flow.handle("037/26 corretora A13")
        self.assertEqual(self.flow.load()["movimentosIniciais"], initial)

    async def test_unknown_selection_is_rejected_and_offer_aa_is_explicit(self):
        await self.fixed()
        original = self.flow.load()
        self.assertIn("efetivamente fixados", await self.flow.handle("parte 999/26"))
        self.assertEqual(self.flow.load(), original)
        summary = await self.flow.handle("sim 375/26 corretora A13 AA Sim")
        self.assertIn("Lanc. AA: Sim", summary)
        self.hedge_send.assert_not_called()

    async def test_correction_invalidates_stale_confirmation(self):
        await self.hedge_ready()
        stale = self.flow.load()
        await self.flow.handle("375/26 3 lotes AA Sim")
        self.assertIn("resumo foi alterado", await self.flow.send(stale, hedge=True))
        self.hedge_send.assert_not_called()

    async def test_all_fixed_contracts_are_shown_with_distinct_levels_and_known_metadata(self):
        await self.fixed()
        data = self.flow.load()
        for index, item in enumerate(data["contratosFixadosAcumulado"]):
            item["nivel"] = 100 + index + 0.111
        self.flow.save(data)
        summary = await self.flow.handle("todos corretora A13")
        self.assertEqual(summary.count("Contrato "), 3)
        for index, movement in enumerate(self.flow.load()["movimentos"]):
            self.assertEqual(movement["valor"], 100 + index + 0.111)
            self.assertEqual((movement["operac"], movement["tipo"], movement["account"], movement["lancaa"]), ("FV", "C", "A13", "Nao"))
        self.hedge_send.assert_not_called()

    async def test_contract_query_is_once_across_corrections_restart_fixation_and_hedge_retry(self):
        await self.prepare()
        self.assertEqual(self.contract_query.call_count, 3)
        for ref in ("374/26D", "375/26", "037/26"):
            self.contract_query.assert_any_call("usp_IA_Vendas", {"Contrato": ref})
        self.flow = ContractBatchFlow("teste", True)
        await self.flow.handle("375/26 nivel 222")
        self.fix_send.return_value = fixation_result(("374/26D",), ("375/26", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        await self.flow.handle("375/26 nivel 225")
        self.fix_send.return_value = fixation_result(("375/26",))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("1")
        with patch.object(HedgeTools, "recommend_lots", side_effect=AssertionError("Consulta tardia proibida")):
            await self.flow.handle("todos corretora A13")
        self.hedge_send.return_value = hedge_result(("374/26D",), ("375/26",))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        await self.flow.handle("375/26 3 lotes")
        self.hedge_send.return_value = hedge_result(("375/26",))
        await self.flow.handle("sim")
        self.assertEqual(self.contract_query.call_count, 3)

    async def test_procedure_type_descriptions_are_displayed_and_only_codes_are_sent(self):
        for index, (code, description) in enumerate(self.flow.TYPE_DESCRIPTIONS.items()):
            self.flow = ContractBatchFlow(f"tipo-{index}", True)
            self.contract_query.return_value = [{"tipoValor": description}]
            summary = await self.flow.handle("fixe 375/26 nivel 105,75")
            self.assertIn(f"Valor da Fixação: 105,75 {description}", summary)
            self.fix_send.return_value = fixation_result(("375/26",))
            await self.flow.handle("sim")
            payload = self.fix_send.await_args.args[0]["contratos"][0]["fixacaoContrato"][0]
            self.assertEqual(payload, {"valorFixacao": 105.75, "tipoValor": code})
        self.assertEqual(self.contract_query.call_count, 5)

    async def test_query_failure_empty_missing_and_unknown_type_require_user_input_without_retry(self):
        cases = [(RuntimeError("SQL indisponível"), "erro"), ([], "vazio"),
                 ([{"sacas": 865}], "ok"), ([{"tipoValor": "US$ valor desconhecido"}], "ok")]
        for index, (response, status) in enumerate(cases):
            self.flow = ContractBatchFlow(f"ausente-{index}", True)
            self.contract_query.side_effect = response if isinstance(response, Exception) else None
            self.contract_query.return_value = response
            summary = await self.flow.handle("fixe 375/26 nivel 110,1")
            self.assertIn("Tipo Valor ausente ou não reconhecido", summary)
            self.assertNotIn("Confirma o envio", summary)
            data = self.flow.load()
            self.assertEqual(data["consultasContratos"]["375/26"]["status"], status)
            self.assertEqual(data["stage"], "collect_fix")
            self.fix_send.reset_mock()
            await self.flow.handle("sim")
            self.fix_send.assert_not_called()
            summary = await self.flow.handle("US$ KG")
            self.assertIn("110,1 US$ KG", summary)
            self.fix_send.assert_not_called()
            self.assertEqual(self.flow.load()["stage"], "confirm_fix")
        self.assertEqual(self.contract_query.call_count, len(cases))

    async def test_missing_type_answer_only_fills_contracts_that_need_it(self):
        self.contract_query.side_effect = [[{"tipoValor": "CTS/LB"}], [{"tipoValor": "inexistente"}]]
        summary = await self.flow.handle("fixe 374/26A e 374/26D nivel 100")
        self.assertIn("Informe o Tipo Valor para: 374/26D", summary)
        summary = await self.flow.handle("5")
        self.assertIn("100 US$ 50KG", summary)
        items = self.flow.load()["contratos"]
        self.assertEqual([i["tipoValor"] for i in items], ["C", "5"])
        self.assertEqual([i["valorFixacao"] for i in items], [100, 100])
        self.assertEqual(self.contract_query.call_count, 2)

    async def test_contract_letters_keep_separate_cached_returns_and_user_overrides(self):
        from decimal import Decimal
        from datetime import date
        rows = [
            [{"tipoValor": "US$ KG", "sacas": Decimal("865"), "mesFixacao": "202607", "data": date(2026, 1, 1)}],
            [{"tipoValor": "CTS/LB", "sacas": 576.60047, "mesFixacao": "202612"}],
        ]
        self.contract_query.side_effect = rows
        self.flow.prepare_fixation([
            ("374/26A", {"valorFixacao": 100}),
            ("374/26D", {"valorFixacao": 110, "lotes": 7, "mesfix": "SET", "anofix": "2027", "tipoValor": "T"}),
        ])
        data = self.flow.load()
        self.assertEqual(data["consultasContratos"]["374/26A"]["retorno"][0]["data"], "2026-01-01")
        self.assertEqual(data["contratos"][1]["tipoValor"], "T")
        summary = await self.flow.handle("374/26A tipo US$ 59KG")
        self.assertIn("100 US$ 59KG", summary)
        self.fix_send.return_value = fixation_result(("374/26A", "374/26D"), level=101.111)
        await self.flow.handle("sim")
        await self.flow.handle("todos corretora A13")
        movements = self.flow.load()["movimentos"]
        self.assertEqual([(i["mesfix"], i["anofix"], i["lotes"]) for i in movements], [("JUL", "2026", 3), ("SET", "2027", 7)])
        self.assertTrue(all(i["valor"] == 101.111 for i in movements))
        self.assertEqual(self.contract_query.call_count, 2)

    async def test_type_is_available_without_sacks_and_unknown_hedge_fields_are_collected(self):
        self.contract_query.return_value = [{"tipoValor": "CTS/LB"}]
        await self.flow.handle("fixe 375/26 nivel 100")
        self.fix_send.return_value = fixation_result(("375/26",))
        await self.flow.handle("sim")
        self.assertIn("mês", await self.flow.handle("sim corretora A13"))
        await self.flow.handle("DEZ")
        await self.flow.handle("2026")
        summary = await self.flow.handle("2 lotes")
        self.assertIn("Confirma o envio", summary)
        self.assertEqual(self.contract_query.call_count, 1)

    async def test_new_process_can_query_same_contract_again(self):
        await self.flow.handle("fixe 375/26 nivel 100")
        await self.flow.handle("sair")
        await self.flow.handle("fixe 375/26 nivel 110")
        self.assertEqual(self.contract_query.call_count, 2)

    async def test_interrupted_lookup_is_not_repeated(self):
        await self.flow.handle("fixe 375/26 nivel 100")
        data = self.flow.load()
        data["consultasContratos"]["375/26"] = {"status": "consultando", "retorno": [], "recomendacao": {}}
        item = data["contratos"][0]
        item.pop("tipoValor")
        item.pop("tipoValorDescricao")
        data["contratosAindaNaoFixados"] = deepcopy(data["contratos"])
        data["stage"] = "collect_fix"
        self.flow.save(data)
        await self.flow.handle("tipo C")
        self.assertEqual(self.flow.load()["stage"], "confirm_fix")
        self.assertEqual(self.contract_query.call_count, 1)

    async def test_hedge_partial_subset_and_accumulated_final(self):
        await self.hedge_ready()
        initial = deepcopy(self.flow.load()["movimentosIniciais"])
        self.hedge_send.return_value = hedge_result(("374/26D",), ("375/26", "037/26"))
        await self.flow.handle("sim")
        await self.flow.handle("nao")
        await self.flow.handle("2")
        await self.flow.handle("375/26 corretora A13 3 lotes")
        self.assertEqual(self.hedge_send.await_count, 1)
        self.hedge_send.return_value = hedge_result(("375/26",))
        await self.flow.handle("sim")
        listing = await self.flow.handle("sim")
        self.assertIn("Motivo 037/26", listing)
        self.assertEqual(self.flow.load()["movimentosIniciais"], initial)
        await self.flow.handle("3")
        self.hedge_send.return_value = hedge_result(("037/26",))
        report = await self.flow.handle("sim")
        self.assertEqual(report.count("Hedge = SIM"), 3)
        self.assertEqual(len(self.hedge_send.await_args.args[0]["movimentos"]), 1)

    async def test_hedge_only_editable_fields_and_positive_lots(self):
        await self.hedge_ready()
        for message in ("375/26 valor 9", "375/26 mes DEZ", "375/26 0 lotes", "375/26 -1 lote", "375/26 1.5 lotes"):
            result = await self.flow.handle(message)
            self.assertIn("Verifique", result, message)
        await self.flow.handle("375/26 corretora A13 4 lotes")
        self.hedge_send.assert_not_called()
        item = next(i for i in self.flow.load()["movimentos"] if i["ctrex"] == "375/26")
        self.assertEqual((item["corret"], item["account"], item["lotes"]), ("A13", "A13", 4))

    async def test_offer_accepts_per_contract_broker_and_lots(self):
        await self.fixed()
        await self.flow.handle("sim 375/26 corretora A13 3 lotes e 374/26D corretora A14 4 lotes")
        movements = {i["ctrex"]: i for i in self.flow.load()["movimentos"]}
        self.assertEqual(set(movements), {"375/26", "374/26D"})
        self.assertEqual((movements["375/26"]["corret"], movements["375/26"]["lotes"]), ("A13", 3))
        self.assertEqual((movements["374/26D"]["corret"], movements["374/26D"]["lotes"]), ("A14", 4))

    async def test_contract_metadata_does_not_leak_between_group_members(self):
        self.flow.prepare_fixation([
            ("375/26", {"valorFixacao": 100, "mesfix": "DEZ", "anofix": "2026", "lotes": 1, "corret": "A13", "lancaa": "Sim"}),
            ("374/26D", {"valorFixacao": 99, "mesfix": "JUL", "anofix": "2027", "lotes": 4, "corret": "A14", "lancaa": "Nao"}),
        ])
        self.fix_send.return_value = fixation_result(("375/26", "374/26D"))
        await self.flow.handle("sim")
        await self.flow.handle("sim")
        movements = self.flow.load()["movimentos"]
        self.assertEqual((movements[0]["mesfix"], movements[0]["anofix"], movements[0]["lotes"]), ("DEZ", "2026", 1))
        self.assertEqual((movements[1]["mesfix"], movements[1]["anofix"], movements[1]["lotes"]), ("JUL", "2027", 4))

    async def test_stale_confirmation_cannot_repost(self):
        await self.prepare()
        stale = self.flow.load()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        await self.flow.handle("sim")
        output = await self.flow.send(stale)
        self.assertIn("já foi processado", output)
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_concurrent_confirmations_send_once(self):
        await self.prepare()
        entered, release = asyncio.Event(), asyncio.Event()
        async def response(body):
            entered.set()
            await release.wait()
            return fixation_result(("374/26D", "375/26", "037/26"))
        self.fix_send.side_effect = response
        first = asyncio.create_task(self.flow.handle("sim"))
        await entered.wait()
        second = await self.flow.handle("sim")
        self.assertIn("aguarda resultado", second)
        release.set()
        await first
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_deadline_advances_listing_to_options_without_api(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result((), ("374/26D", "375/26", "037/26"))
        await self.flow.handle("sim")
        data = self.flow.load()
        data["list_deadline"] = 0
        self.flow.save(data)
        self.assertIn("Escolha uma opção", await self.flow.handle("sim"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_timer_delivers_options_without_user_reply(self):
        await self.prepare()
        self.flow.notify = AsyncMock()
        with patch("app.agents.contract_batch_flow.asyncio.sleep", AsyncMock()):
            await self.flow.ask_failure(self.flow.load())
            # Dá oportunidade à task de executar sem aguardar cinco minutos.
            await asyncio.sleep(0)
            for task in list(__import__('app.agents.contract_batch_flow', fromlist=['_timers'])._timers):
                await task
        self.flow.notify.assert_awaited_once()
        self.assertEqual(self.flow.load()["stage"], "retry_fix")

    async def test_late_response_warns_then_processes_same_request(self):
        await self.prepare()
        self.flow.notify = AsyncMock()
        real_wait = asyncio.wait
        async def fast_wait(tasks, timeout=None, **kwargs):
            if timeout is not None:
                self.assertEqual(timeout, 90)
                return await real_wait(tasks, timeout=0, **kwargs)
            return await real_wait(tasks, **kwargs)
        async def response(body):
            await asyncio.sleep(0.001)
            return fixation_result(("374/26D", "375/26", "037/26"))
        self.fix_send.side_effect = response
        with patch("app.agents.contract_batch_flow.asyncio.wait", fast_wait):
            result = await self.flow.handle("sim")
        self.flow.notify.assert_awaited_once_with("ATENÇÃO - Não obtivemos resposta do processo de fixação de contratos. Verifique no Protheus!")
        self.assertIn("Hedge", result)
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_inflight_and_uncertain_result_never_resend(self):
        await self.prepare()
        self.fix_send.side_effect = RuntimeError("sem resultado")
        await self.flow.handle("sim")
        self.assertEqual(self.flow.load()["stage"], "uncertain")
        await self.flow.handle("sim")
        await self.flow.handle("fixe 375/26 nivel 20")
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_permission_denial_has_no_side_effects(self):
        self.flow.has_permission = False
        result = await self.prepare()
        self.assertIn("não tem permissão", result)
        self.assertFalse(self.store.data)
        self.fix_send.assert_not_called()

    async def test_unrelated_messages_pass_through_without_releasing_pending_operation(self):
        await self.prepare()
        self.fix_send.side_effect = RuntimeError("resposta perdida")
        await self.flow.handle("sim")
        before = deepcopy(self.store.data)
        for message in ("ola", "qual a cotação do dólar?", "consulte os embarques",
                        "consulte o contrato 375/26", "quais contratos estão em aberto?"):
            self.assertIsNone(await self.flow.handle(message))
        self.assertEqual(self.store.data, before)
        self.assertIn("aguarda resultado", await self.flow.handle("pode enviar"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_known_failure_allows_new_confirmation_without_automatic_retry(self):
        for error in (OperationNotSent("Autenticação falhou"), OperationRejected("HTTP 401")):
            with self.subTest(error=type(error).__name__):
                self.store.data.clear()
                await self.prepare()
                old_confirmation = self.flow.load()["confirmation_id"]
                self.fix_send.reset_mock()
                self.fix_send.side_effect = error
                self.assertIn("Confirme novamente", await self.flow.handle("sim"))
                self.assertEqual(self.flow.load()["stage"], "confirm_fix")
                self.assertNotEqual(self.flow.load()["confirmation_id"], old_confirmation)
                self.assertIsNone(self.store.get(self.flow.key + ":envio"))
                self.assertEqual(self.fix_send.await_count, 1)

    async def test_exit_legacy_block_after_restart(self):
        for stage in ("sending_fix", "sending_hedge", "uncertain"):
            self.flow.save({"stage": stage})
            self.store.set(self.flow.key + ":envio", "1")
            restarted = ContractBatchFlow("teste", True)
            self.assertEqual(await restarted.handle("SAIR"), self.flow.EXIT_MESSAGE)
            self.assertIsNone(self.store.get(self.flow.key + ":envio"))
            self.assertIsNone(await restarted.handle("ola"))
            self.assertIn("Resumo", await restarted.handle("fixe 375/26 nivel 100"))
        self.fix_send.assert_not_called()

    async def test_exit_wakes_waiter_and_discards_late_response_without_touching_new_lock(self):
        await self.prepare()
        entered, release = asyncio.Event(), asyncio.Event()
        async def late_response(body):
            entered.set()
            await release.wait()
            return fixation_result(("374/26D", "375/26", "037/26"))
        self.fix_send.side_effect = late_response
        waiting = asyncio.create_task(self.flow.handle("sim"))
        await entered.wait()
        operation_id = self.flow.load()["operation_id"]
        worker = __import__('app.agents.contract_batch_flow', fromlist=['_operations'])._operations[(self.flow.key, operation_id)]
        self.assertEqual(await self.flow.handle("sair"), self.flow.EXIT_MESSAGE)
        self.assertEqual(await asyncio.wait_for(waiting, 1), "")
        await self.flow.handle("fixe 375/26 nivel 200")
        self.store.set(self.flow.key + ":envio", "new-operation")
        before = deepcopy(self.flow.load())
        release.set()
        self.assertEqual(await worker, "")
        self.assertEqual(self.flow.load(), before)
        self.assertEqual(self.store.get(self.flow.key + ":envio"), "new-operation")
        self.assertEqual(self.flow.read_operation(operation_id)["status"], "discarded")

    async def test_persisted_result_recovers_after_restart_without_resending(self):
        await self.prepare()
        data = self.flow.load()
        data.update(stage="sending_fix", operation_id="interrupted", process_id="old-process")
        self.flow.save(data)
        self.store.set(self.flow.key + ":envio", "interrupted")
        result = fixation_result(("374/26D", "375/26", "037/26"))
        del result["fixados"]
        del result["naoFixados"]
        self.flow.save_operation("interrupted", {"status": "received", "result": result, "hedge": False})
        self.assertIn("Hedge", await ContractBatchFlow("teste", True).handle("resultado"))
        self.assertEqual(self.flow.load()["stage"], "offer")
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.fix_send.assert_not_called()

    async def test_restart_without_result_preserves_uncertainty_until_exit(self):
        self.flow.save({"stage": "sending_fix", "operation_id": "lost", "process_id": "old-process"})
        self.store.set(self.flow.key + ":envio", "lost")
        self.assertIsNone(await self.flow.handle("ola"))
        self.assertEqual(self.flow.load()["stage"], "uncertain")
        self.assertIn("aguarda resultado", await self.flow.handle("sim"))
        self.assertEqual(await self.flow.handle("sair"), self.flow.EXIT_MESSAGE)
        self.fix_send.assert_not_called()

    async def test_local_interpretation_failure_preserves_response_for_recovery(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        with patch.object(ContractBatchFlow, "apply_result", AsyncMock(side_effect=ValueError("erro local"))):
            self.assertEqual(await self.flow.handle("sim"), self.flow.RESULT_ERROR_MESSAGE)
            self.assertEqual(self.flow.load()["stage"], "result_error")
            self.assertEqual(await self.flow.handle("resultado"), self.flow.RESULT_ERROR_MESSAGE)
            self.assertIsNone(await self.flow.handle("ola"))
        operation_id = self.flow.load()["operation_id"]
        self.assertEqual(self.flow.read_operation(operation_id)["status"], "received")
        self.assertEqual(self.flow.read_operation(operation_id)["processing_error"], "erro local")
        self.assertIn("Hedge", await self.flow.handle("resultado"))
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_incomplete_result_does_not_mark_missing_contracts_as_failed(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("375/26",))
        await self.flow.handle("sim")
        self.assertEqual(self.flow.load()["stage"], "result_error")
        self.assertEqual(self.flow.load()["contratosFixadosAcumulado"], [])

    async def test_exact_protheus_failure_is_conclusive_and_allows_corrections(self):
        await self.prepare()
        result = protheus_fixation_failure()
        original = deepcopy(result)
        self.fix_send.return_value = result
        output = await self.flow.handle("sim")
        self.assertIn("Quantidade de contratos fixados: 0", output)
        self.assertIn("Quantidade de contratos não fixados: 3", output)
        self.assertIn("Fixador - Preenchimento Obrigatorio", output)
        self.assertIn("Contrato Exportação não encontrado.", output)
        self.assertIn("listagem detalhada", output)
        data = self.flow.load()
        self.assertEqual(data["stage"], "list_fix")
        self.assertEqual(len(data["contratosAindaNaoFixados"]), 3)
        self.assertEqual(data["contratosFixadosAcumulado"], [])
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.assertEqual(self.flow.read_operation(data["operation_id"])["status"], "applied")
        self.assertEqual(result, original)
        listing = await self.flow.handle("sim")
        for ref in ("374/26D", "375/26", "037/26"):
            self.assertIn(ref, listing)
        await self.flow.handle("2")
        self.assertIn("Confirma o envio", await self.flow.handle("374/26D fixador importador"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_saved_protheus_failure_recovers_without_resending(self):
        await self.prepare()
        data = self.flow.load()
        data.update(stage="uncertain", operation_id="previous-return", process_id="old-process")
        self.flow.save(data)
        self.store.set(self.flow.key + ":envio", "previous-return")
        self.flow.save_operation("previous-return", {
            "status": "received", "result": protheus_fixation_failure(), "hedge": False,
        })
        output = await ContractBatchFlow("teste", True).handle("resultado")
        self.assertIn("Quantidade de contratos não fixados: 3", output)
        self.assertEqual(self.flow.load()["stage"], "list_fix")
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.fix_send.assert_not_called()

    async def test_result_processing_error_blocks_tools_until_recovery_or_exit(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("375/26",))
        self.assertEqual(await self.flow.handle("sim"), self.flow.RESULT_ERROR_MESSAGE)
        before = deepcopy(self.flow.load())
        tool = FixacaoTools("teste", True)
        tool.clear_pending()
        self.assertIn("erro ao interpretar", tool.cadastrar_valor_contrato(numero_venda="375/26", valor_fixacao=100))
        self.assertEqual(self.flow.load(), before)
        self.assertEqual(await self.flow.handle("sair"), self.flow.EXIT_MESSAGE)
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.assertIn("Resumo", await self.flow.handle("fixe 375/26 nivel 100"))
        self.assertEqual(self.fix_send.await_count, 1)

    async def test_cancelled_waiter_does_not_lose_eventual_result(self):
        await self.prepare()
        entered, release = asyncio.Event(), asyncio.Event()
        async def response(body):
            entered.set()
            await release.wait()
            return fixation_result(("374/26D", "375/26", "037/26"))
        self.fix_send.side_effect = response
        waiter = asyncio.create_task(self.flow.handle("sim"))
        await entered.wait()
        operation_id = self.flow.load()["operation_id"]
        worker = __import__('app.agents.contract_batch_flow', fromlist=['_operations'])._operations[(self.flow.key, operation_id)]
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter
        release.set()
        await worker
        self.assertEqual(self.flow.load()["stage"], "offer")
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))

    async def test_exit_during_result_processing_prevents_stale_commit(self):
        await self.prepare()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        apply_result = self.flow.apply_result
        async def interrupted_apply(data, result, hedge, **kwargs):
            output = await apply_result(data, result, hedge, **kwargs)
            await ContractBatchFlow("teste", True).handle("sair")
            await self.flow.handle("fixe 375/26 nivel 200")
            return output
        with patch.object(self.flow, "apply_result", interrupted_apply):
            self.assertEqual(await self.flow.handle("sim"), "")
        self.assertEqual(self.flow.load()["stage"], "confirm_fix")
        self.assertEqual(self.flow.load()["contratos"][0]["valorFixacao"], 200)

    async def test_expired_session_recovers_saved_response_from_lock(self):
        await self.prepare()
        data = self.flow.load()
        data.update(stage="sending_fix", operation_id="expired", process_id="old-process")
        self.flow.save_operation("expired", {
            "status": "received", "snapshot": data, "hedge": False,
            "result": fixation_result(("374/26D", "375/26", "037/26")),
        })
        self.store.delete(self.flow.key)
        self.store.set(self.flow.key + ":envio", "expired")
        self.assertIn("Hedge", await self.flow.handle("resultado"))
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.fix_send.assert_not_called()

    async def test_hedge_uncertainty_also_allows_exit_and_new_fixation(self):
        await self.hedge_ready()
        self.hedge_send.side_effect = RuntimeError("resultado perdido")
        await self.flow.handle("sim")
        self.assertIsNone(await self.flow.handle("ola"))
        self.assertEqual(await self.flow.handle("sair"), self.flow.EXIT_MESSAGE)
        self.assertIn("Resumo", await self.flow.handle("fixe 375/26 nivel 200"))
        self.assertEqual(self.hedge_send.await_count, 1)

    async def test_saved_pre_send_failure_recovers_new_confirmation(self):
        await self.prepare()
        data = self.flow.load()
        data.update(stage="sending_fix", operation_id="auth-failed", process_id="old-process")
        self.flow.save(data)
        self.store.set(self.flow.key + ":envio", "auth-failed")
        self.flow.save_operation("auth-failed", {"status": "not_sent", "hedge": False})
        self.assertIn("Confirme novamente", await self.flow.handle("sim"))
        self.assertEqual(self.flow.load()["stage"], "confirm_fix")
        self.assertIsNone(self.store.get(self.flow.key + ":envio"))
        self.fix_send.assert_not_called()

    def test_tool_rejects_internal_code_and_premature_confirmation(self):
        tool = FixacaoTools("teste", True)
        self.assertIn("VALOR_INVALIDO", tool.cadastrar_valor_contrato(numero_venda="012329", valor_fixacao=5))
        result = tool.cadastrar_valor_contrato(contratos_json=json.dumps([
            {"numeroVenda": "7/27", "fixacaoContrato": [{"valorFixacao": 5}]}]), confirmar_envio=True)
        self.assertIn("AGUARDANDO_CONFIRMACAO", result)
        self.fix_send.assert_not_called()


class BatchTransportTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        deny_network = patch("socket.socket.connect", side_effect=AssertionError("Rede proibida no teste"))
        deny_network.start()
        self.addCleanup(deny_network.stop)

    async def test_auth_failure_never_posts_financial_operation(self):
        for method, body in (("cadastrar_fixacao", {"contratos": [{}]}), ("cadastrar_hedge", {"movimentos": [{}]})):
            client = FixacaoApiClient()
            with patch.object(client, "get_token", AsyncMock(side_effect=RuntimeError("token indisponível"))), patch(
                "app.core.fixacao_api_client.httpx.AsyncClient"
            ) as transport:
                with self.assertRaises(OperationNotSent):
                    await getattr(client, method)(body)
                transport.assert_not_called()

    async def test_connection_failure_is_safe_but_read_timeout_remains_uncertain(self):
        import httpx
        for method, body in (("cadastrar_fixacao", {"contratos": [{}]}), ("cadastrar_hedge", {"movimentos": [{}]})):
            for error, expected in ((httpx.ConnectError("conexão recusada"), OperationNotSent),
                                    (httpx.ReadTimeout("resposta perdida"), httpx.ReadTimeout),
                                    (httpx.WriteError("envio interrompido"), httpx.WriteError)):
                client = FixacaoApiClient()
                context = AsyncMock()
                context.__aenter__.return_value.post.side_effect = error
                with patch.object(client, "get_token", AsyncMock(return_value="fake")), patch(
                    "app.core.fixacao_api_client.httpx.AsyncClient", return_value=context
                ):
                    with self.assertRaises(expected):
                        await getattr(client, method)(body)

    async def test_business_400_is_a_result_not_transport_error(self):
        for method, body, result in (
            ("cadastrar_fixacao", {"contratos": [{}]}, fixation_result((), ("375/26",))),
            ("cadastrar_hedge", {"movimentos": [{}]}, hedge_result((), ("375/26",))),
        ):
            for status in (200, 400):
                with self.subTest(method=method, status=status):
                    client = FixacaoApiClient()
                    response = MagicMock(status_code=status)
                    response.json.return_value = result
                    context = AsyncMock()
                    context.__aenter__.return_value.post.return_value = response
                    with patch.object(client, "get_token", AsyncMock(return_value="fake")), patch(
                        "app.core.fixacao_api_client.httpx.AsyncClient", return_value=context
                    ) as factory, patch("socket.socket.connect", side_effect=AssertionError("Rede proibida")):
                        self.assertEqual(await getattr(client, method)(body), result)
                    self.assertIsNone(factory.call_args.kwargs["timeout"])

    async def test_batch_never_reposts_on_unauthorized_response(self):
        client = FixacaoApiClient()
        response = MagicMock(status_code=401, text="unauthorized")
        context = AsyncMock()
        context.__aenter__.return_value.post.return_value = response
        with patch.object(client, "get_token", AsyncMock(return_value="fake")), patch(
            "app.core.fixacao_api_client.httpx.AsyncClient", return_value=context
        ):
            with self.assertRaises(RuntimeError):
                await client.cadastrar_fixacao({"contratos": [{}]})
        self.assertEqual(context.__aenter__.return_value.post.await_count, 1)


if __name__ == "__main__":
    unittest.main()
