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
from app.core.fixacao_api_client import FixacaoApiClient


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


class BatchFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = MemoryRedis()
        self.flow = ContractBatchFlow("teste", True)
        self.patches = [
            patch.object(ContractBatchFlow, "_redis", return_value=self.store),
            patch.object(HedgeTools, "recommend_lots", return_value={"mesfixRecomendado": "DEZ", "anofixRecomendado": "2026", "lotesRecomendados": 2}),
            patch("socket.socket.connect", side_effect=AssertionError("Rede proibida no teste")),
        ]
        for item in self.patches:
            item.start()
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
        for ref in ("1234/26", "1/2", "1/2026", "012329", "007/27AB", "007/27d"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                identifier(ref)
        with self.assertRaisesRegex(ValueError, "mais de uma vez"):
            self.flow.parse_contracts("7/27D, 007/27 D")

    async def test_mixed_groups_confirmation_and_exact_payload(self):
        summary = await self.prepare()
        self.assertIn("374/26D", summary)
        self.assertEqual([i["valorFixacao"] for i in self.flow.load()["contratos"]], [221.25, 221.25, 219.05])
        self.fix_send.assert_not_called()
        self.fix_send.return_value = fixation_result(("374/26D", "375/26", "037/26"))
        output = await self.flow.handle("confirmo")
        body = self.fix_send.await_args.args[0]
        self.assertEqual(body["contratos"][1], {"numeroVenda": "375/26", "letraVenda": "", "fixacaoContrato": [{"valorFixacao": 221.25}]})
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
        self.assertIn("200.32", summary)
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
        self.assertIn("AA", await self.flow.handle("A14"))
        summary = await self.flow.handle("nao")
        self.assertIn('"lancaa": "Nao"', summary)
        self.assertIn('"valor": 102.1', summary)
        self.hedge_send.return_value = hedge_result(("375/26",))
        report = await self.flow.handle("sim")
        body = self.hedge_send.await_args.args[0]
        self.assertEqual(len(body["movimentos"]), 1)
        self.assertEqual(body["movimentos"][0]["corret"], "A14")
        self.assertEqual(body["movimentos"][0]["account"], "A14")
        self.assertIn("375/26 = Nível: 102.1 — Hedge = SIM", report)
        self.assertIn("374/26D = Nível: 102.1 — Hedge = NAO", report)

    async def hedge_ready(self):
        await self.fixed()
        await self.flow.handle("sim corretora A14")
        # AA é obrigatório e coletado individualmente para cada movimento.
        for _ in range(3):
            await self.flow.handle("sim")
        self.assertEqual(self.flow.load()["stage"], "confirm_hedge")

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
        async def fast_wait(tasks, timeout):
            self.assertEqual(timeout, 90)
            return await real_wait(tasks, timeout=0)
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

    def test_tool_rejects_internal_code_and_premature_confirmation(self):
        tool = FixacaoTools("teste", True)
        self.assertIn("VALOR_INVALIDO", tool.cadastrar_valor_contrato(numero_venda="012329", valor_fixacao=5))
        result = tool.cadastrar_valor_contrato(contratos_json=json.dumps([
            {"numeroVenda": "7/27", "fixacaoContrato": [{"valorFixacao": 5}]}]), confirmar_envio=True)
        self.assertIn("AGUARDANDO_CONFIRMACAO", result)
        self.fix_send.assert_not_called()


class BatchTransportTest(unittest.IsolatedAsyncioTestCase):
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
