"""Regressões offline do relatório: código real, serviços externos simulados."""
import ast
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
import types
import unicodedata
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).parent


def load_definitions(path, names, scope, class_name=None):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    nodes = tree.body
    if class_name:
        nodes = next(node for node in nodes if isinstance(node, ast.ClassDef) and node.name == class_name).body
    selected = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + selected,
                        type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), path, "exec"), scope)


class ScheduledReportReadOnlyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = types.SimpleNamespace(nome="Renan", telefone="telefone-teste", email="teste@example.com",
                                          has_permission=MagicMock(side_effect=lambda permission: permission == "Estoque"))
        self.sql = MagicMock()
        self.sql._pesquisa_longshort.return_value = "Quadro oficial: vendas a fixar e bolsa lotes"
        self.sql.get_all_tools.return_value = []
        self.scope = {
            "re": re, "unicodedata": unicodedata, "logger": logging.getLogger(__name__),
            "SQLTools": MagicMock(return_value=self.sql),
            "_extract_complete_daily_schedule": MagicMock(side_effect=AssertionError("Não deve agendar")),
        }
        load_definitions("app/agents/orchestrator.py", {"_normalize_query_text"}, self.scope)
        load_definitions("app/agents/orchestrator.py", {"process_message", "_setup_memory"}, self.scope, "AgentOrchestrator")
        self.agent = types.SimpleNamespace(
            user=self.user, session_id=self.user.telefone, read_only=True,
            message_history=MagicMock(), _process_hedge_flow=AsyncMock(),
            _is_contrato_flow=MagicMock(side_effect=AssertionError("Não deve acessar contratos pendentes")),
        )

    async def test_fixar_in_report_never_enters_pending_financial_flows(self):
        batch = MagicMock(side_effect=AssertionError("Não deve entrar na fixação"))
        with patch.dict(sys.modules, {"app.agents.contract_batch_flow": types.SimpleNamespace(ContractBatchFlow=batch)}):
            result = await self.scope["process_message"](
                self.agent, "Gere o relatório Long/Short com vendas a fixar. Não agende nada, apenas execute.")
        self.assertEqual(result, self.sql._pesquisa_longshort.return_value)
        self.scope["SQLTools"].assert_called_once_with(self.user, self.user.telefone)
        self.sql.get_all_tools.assert_called_once_with(read_only=True)
        self.agent._process_hedge_flow.assert_not_called()
        self.agent._is_contrato_flow.assert_not_called()
        self.user.has_permission.assert_not_called()
        batch.assert_not_called()
        self.assertFalse(self.agent.last_response_is_contract_batch)

    async def test_report_preserves_data_permission_denial(self):
        self.sql._pesquisa_longshort.return_value = "Você não tem permissão para acessar informações de Estoque."
        result = await self.scope["process_message"](self.agent, "Relatório Long/Short de vendas a fixar")
        self.assertEqual(result, self.sql._pesquisa_longshort.return_value)

    async def test_interactive_mode_still_checks_fixation_permission(self):
        self.agent.read_only = False
        batch = MagicMock()
        batch.return_value.handle = AsyncMock(return_value="Você não tem permissão para fixar contratos.")
        with patch.dict(sys.modules, {"app.agents.contract_batch_flow": types.SimpleNamespace(ContractBatchFlow=batch)}):
            result = await self.scope["process_message"](self.agent, "Fixar o contrato 339/26 nível 210")
        self.assertEqual(result, "Você não tem permissão para fixar contratos.")
        self.user.has_permission.assert_called_once_with("Fixacao")
        self.assertFalse(batch.call_args.kwargs["has_permission"])
        self.sql.get_all_tools.assert_not_called()

    def test_separate_report_memory_keeps_phone_for_sql_and_attachments(self):
        factory = MagicMock()
        self.scope.update(RedisChatMessageHistory=factory, settings=types.SimpleNamespace(redis_url="offline", redis_memory_ttl=60))
        self.scope["_setup_memory"](self.agent)
        report_key = factory.call_args.kwargs["session_id"]
        self.agent.read_only = False
        self.scope["_setup_memory"](self.agent)
        self.assertNotEqual(report_key, factory.call_args.kwargs["session_id"])
        self.assertEqual(self.agent.session_id, self.user.telefone)

    def test_read_only_toolset_excludes_operations_even_for_authorized_users(self):
        scope = {"StructuredTool": types.SimpleNamespace(from_function=lambda **kw: types.SimpleNamespace(**kw))}
        load_definitions("app/agents/sql_tools.py", {"get_all_tools"}, scope, "SQLTools")
        sql = MagicMock()
        sql.user.has_permission.return_value = True
        tools = scope["get_all_tools"](sql, read_only=True)
        self.assertTrue(tools)
        self.assertTrue(all(tool.name.startswith("pesquisa_") for tool in tools))
        self.assertIn("pesquisa_longshort", [tool.name for tool in tools])
        self.assertIn("pesquisa_vendas", [tool.name for tool in tools])
        sql.get_ada_tool.assert_not_called()
        sql.user.has_permission.assert_not_called()

    async def test_general_report_ignores_history_and_preference_changes(self):
        class Message:
            def __init__(self, content):
                self.content = content
        class ToolMessage(Message):
            pass
        class AIMessage(Message):
            pass
        answer = AIMessage("Títulos em aberto consultados")
        self.scope.update(
            json=json, settings=types.SimpleNamespace(enable_preference_learning=True, redis_memory_window=10),
            format_standard_weight_conversion=MagicMock(return_value=None),
            SystemMessage=Message, HumanMessage=Message, AIMessage=AIMessage, ToolMessage=ToolMessage,
            _current_turn_messages=lambda messages, message: messages,
            _trusted_payable_detail=lambda messages: None,
            _trusted_unfixed_sales_position=lambda messages: None,
            _trusted_database_detail=lambda messages: None,
            _claims_successful_schedule=MagicMock(side_effect=AssertionError("Não é um agendamento")),
            preference_learning=types.SimpleNamespace(process_user_message=AsyncMock()),
        )
        # Sem messages: qualquer tentativa de ler histórico falha.
        self.agent.message_history = types.SimpleNamespace(add_user_message=MagicMock(), add_ai_message=MagicMock())
        self.agent.agent = types.SimpleNamespace(ainvoke=AsyncMock(return_value={"messages": [answer]}))
        self.agent.system_prompt = "Relatório somente consulta"
        self.agent._should_force_vendas_market_query = MagicMock(return_value=False)
        result = await self.scope["process_message"](self.agent, "Relatório de títulos em aberto")
        self.assertEqual(result, answer.content)
        self.scope["preference_learning"].process_user_message.assert_not_called()
        self.sql.get_all_tools.assert_called_once_with(read_only=True)
        sent = self.agent.agent.ainvoke.await_args.args[0]["messages"]
        self.assertEqual([message.content for message in sent], [self.agent.system_prompt, "Relatório de títulos em aberto"])

    def test_longshort_permission_is_checked_before_database_access(self):
        validator = types.SimpleNamespace(validate_permission=MagicMock(return_value=(False, "Sem acesso a Estoque")))
        database = MagicMock()
        scope = dict(sql_validator=validator, sql_client=database, logger=logging.getLogger(__name__))
        load_definitions("app/agents/sql_tools.py", {"_pesquisa_longshort"}, scope, "SQLTools")
        sql = types.SimpleNamespace(user=self.user, user_query_original="Long/Short a fixar")
        self.assertEqual(scope["_pesquisa_longshort"](sql), "Sem acesso a Estoque")
        validator.validate_permission.assert_called_once_with(self.user, "usp_LS_FILIAIS")
        database.execute_procedure.assert_not_called()

    async def test_scheduler_enables_read_only_and_delivers_report(self):
        constructor = MagicMock()
        constructor.return_value.process_message = AsyncMock(return_value="Relatório pronto")
        auth = MagicMock()
        auth.return_value.authenticate_user = AsyncMock(return_value=self.user)
        whatsapp = MagicMock()
        whatsapp.return_value.send_multiple_messages = AsyncMock()
        formatter = types.SimpleNamespace(format_response=AsyncMock(return_value=["Relatório pronto"]))
        database = types.SimpleNamespace(atualizar_next_run=AsyncMock())
        redis_client = types.SimpleNamespace(get_client=AsyncMock(return_value=types.SimpleNamespace(delete=AsyncMock())))
        modules = {
            "app.services.auth": types.SimpleNamespace(AuthService=auth),
            "app.agents.orchestrator": types.SimpleNamespace(AgentOrchestrator=constructor),
            "app.services.whatsapp": types.SimpleNamespace(WhatsAppService=whatsapp),
            "app.services.formatter": types.SimpleNamespace(response_formatter=formatter),
            "app.services.email": types.SimpleNamespace(email_service=MagicMock()),
            "app.core.config": types.SimpleNamespace(settings=types.SimpleNamespace(app_env="test")),
            "app.core.redis_client": types.SimpleNamespace(redis_client=redis_client),
            "app.services.query_trace": types.SimpleNamespace(reset_query_trace=MagicMock(), start_query_trace=MagicMock()),
        }
        scope = dict(datetime=datetime, TZ=timezone.utc, logger=logging.getLogger(__name__),
                     supabase_client=database, calcular_next_run=MagicMock(return_value=datetime.now(timezone.utc)))
        load_definitions("app/services/scheduler.py", {"_executar_relatorio"}, scope)
        with patch.dict(sys.modules, modules):
            await scope["_executar_relatorio"]({
                "telefone": self.user.telefone, "descricao": "Long/Short com vendas a fixar", "id": "relatorio-teste",
                "frequencia": "diario", "horario": "18:15", "canal": "whatsapp",
            })
        constructor.assert_called_once_with(user=self.user, session_id=self.user.telefone, read_only=True)
        constructor.return_value.process_message.assert_awaited_once()
        whatsapp.return_value.send_multiple_messages.assert_awaited_once_with(self.user.telefone, ["Relatório pronto"])
        database.atualizar_next_run.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
