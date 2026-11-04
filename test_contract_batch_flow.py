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
