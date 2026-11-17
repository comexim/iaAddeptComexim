"""Testes offline da SP de aplicações/empréstimos e da conversa de detalhamento."""
import ast
from copy import deepcopy
from decimal import Decimal
import logging
import re
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import applications_loans as service
from app.services.database_detail import TRUSTED_DATABASE_DETAIL_PREFIX
from test_scheduled_report_read_only import ROOT, load_definitions


def record(number="001", currency="Reais", total="102.35"):
    return dict(Filial="COBRA", Numero=number, DataInc="20261117", Tipo="APL", Banco="BB",
                Moeda=currency, Valor=Decimal("100"), Saldo=Decimal("90"), Vencimento="2026-12-17",
                Taxa=Decimal("1.20"), Dias=30, Juros=Decimal("2.35"), Total=Decimal(total))


class ApplicationsLoansTest(unittest.TestCase):
    def setUp(self):
        self.scope = dict(sql_validator=MagicMock(), sql_client=MagicMock(), logger=logging.getLogger(__name__))
        self.scope["sql_validator"].validate_permission.return_value = (True, None)
        load_definitions("app/agents/sql_tools.py", {"_pesquisa_aplicacoes_emprestimos"}, self.scope, "SQLTools")
        self.sql = types.SimpleNamespace(user=object(), session_id="teste", _report_read_only=False,
                                         _salvar_resultado_scheduler=MagicMock())
        self.query = self.scope["_pesquisa_aplicacoes_emprestimos"]

    def test_total_field_only_decimal_precision_and_separate_currencies(self):
        rows = [record(total="0.10"), record("002", "BRL", "0.20"), record("003", "Dolares", "20.01")]
        original = deepcopy(rows)
        output = service.format_position({"APL": rows})
        self.assertIn("• Total: 0,30", output)
        self.assertIn("• Total: 20,01", output)
        self.assertIn("• Lançamentos: 2", output)
        self.assertNotIn("Total: 20,31", output)
        self.assertIn(service.DETAIL_QUESTION, output)
        self.assertEqual(rows, original)

    def test_detail_blocks_all_fields_dates_and_rates_without_invented_percent(self):
        output = service.format_position({"APL": [record()]}, detail=True)
        for expected in ("• Número: 001", "• Filial: COBRA", "• Banco: BB", "• Inclusão: 17/11/2026",
                         "• Tipo: APL", "• Moeda: BRL", "• Valor: 100,00", "• Saldo: 90,00",
                         "• Vencimento: 17/12/2026", "• Taxa: 1,20", "• Dias: 30", "• Juros: 2,35",
                         "• Total: 102,35", service.SEPARATOR):
            self.assertIn(expected, output)
        self.assertNotIn("%", output)

    def test_exact_procedure_parameters_both_types_and_snapshot(self):
        self.scope["sql_client"].execute_procedure.side_effect = [[record()], [record("002", "USD")]]
        with patch.object(service, "save_snapshot") as save:
            output = self.query(self.sql, "AMBOS")
        self.assertEqual(self.scope["sql_client"].execute_procedure.call_args_list,
                         [unittest.mock.call("dbo.usp_IA_AplEmp", {"Tipo": "APL"}),
                          unittest.mock.call("dbo.usp_IA_AplEmp", {"Tipo": "EMP"})])
        self.assertTrue(output.startswith(TRUSTED_DATABASE_DETAIL_PREFIX))
        self.assertIn("*Aplicações", output)
        self.assertIn("*Empréstimos", output)
        save.assert_called_once()
        self.assertEqual(len(self.sql.last_apl_emp_rows), 2)

    def test_permission_denial_before_query_cache_or_export(self):
        self.scope["sql_validator"].validate_permission.return_value = (False, "Sem acesso a Financeiro")
        with patch.object(service, "load_snapshot") as load:
            self.assertEqual(self.query(self.sql, "APL", reutilizar=True), "Sem acesso a Financeiro")
        self.scope["sql_client"].execute_procedure.assert_not_called()
        load.assert_not_called()
        self.sql._salvar_resultado_scheduler.assert_not_called()
        self.scope["sql_validator"].validate_permission.assert_called_once_with(self.sql.user, "usp_IA_AplEmp")

    def test_reuse_does_not_query_again_and_filters_currency(self):
        with patch.object(service, "load_snapshot", return_value={"APL": [record(), record("002", "USD")]}):
            output = self.query(self.sql, "APL", detalhar=True, moeda="USD", reutilizar=True)
        self.assertIn("• Número: 002", output)
        self.assertNotIn("• Número: 001", output)
        self.scope["sql_client"].execute_procedure.assert_not_called()

    def test_filtered_summary_cache_and_export_have_same_rows(self):
        self.scope["sql_client"].execute_procedure.return_value = [record(), record("002", "USD")]
        with patch.object(service, "save_snapshot") as save:
            self.query(self.sql, "APL", moeda="USD")
        self.assertEqual([row["Numero"] for row in save.call_args.args[1]["APL"]], ["002"])
        self.assertEqual([row["Numero"] for row in self.sql.last_apl_emp_rows], ["002"])

    def test_report_does_not_replace_interactive_snapshot(self):
        self.sql._report_read_only = True
        self.scope["sql_client"].execute_procedure.return_value = [record()]
        with patch.object(service, "save_snapshot") as save:
            output = self.query(self.sql, "EMP")
        self.assertIn("*Empréstimos", output)
        save.assert_not_called()

    def test_empty_expired_failed_query_and_invalid_total_are_distinct(self):
        self.scope["sql_client"].execute_procedure.return_value = []
        with patch.object(service, "save_snapshot"):
            output = self.query(self.sql, "APL")
        self.assertIn("Nenhum lançamento encontrado", output)
        self.assertNotIn(service.DETAIL_QUESTION, output)
        with patch.object(service, "load_snapshot", return_value=None):
            self.assertIn("expirou", self.query(self.sql, "APL", reutilizar=True))
        self.scope["sql_client"].execute_procedure.side_effect = RuntimeError("SP indisponível")
        self.assertIn("Não foi possível consultar", self.query(self.sql, "EMP"))
        for value in (None, "inválido", "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                service.format_position({"APL": [{"Total": value, "Moeda": "USD"}]})

    def test_cache_failure_does_not_offer_unavailable_detail(self):
        self.scope["sql_client"].execute_procedure.return_value = [record()]
        with patch.object(service, "save_snapshot", side_effect=RuntimeError("Redis indisponível")):
            output = self.query(self.sql, "APL")
        self.assertIn("102,35", output)
        self.assertNotIn(service.DETAIL_QUESTION, output)

    def test_permission_mapping_is_financeiro(self):
        tree = ast.parse((ROOT / "app/utils/sql_validator.py").read_text(encoding="utf-8"))
        mapping = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.AnnAssign) and node.target.id == "FUNCTION_PERMISSIONS")
        self.assertEqual(mapping["usp_IA_AplEmp"], "Financeiro")


class ApplicationsLoansConversationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        class AIMessage:
            def __init__(self, content):
                self.content = content
        self.AI = AIMessage
        self.sql = MagicMock()
        self.sql._pesquisa_aplicacoes_emprestimos.return_value = TRUSTED_DATABASE_DETAIL_PREFIX + "Consulta formatada"
        self.scope = dict(re=re, AIMessage=AIMessage, SQLTools=MagicMock(return_value=self.sql),
                          TRUSTED_DATABASE_DETAIL_PREFIX=TRUSTED_DATABASE_DETAIL_PREFIX)
        load_definitions("app/agents/orchestrator.py", {"_process_apl_emp_query"}, self.scope, "AgentOrchestrator")
        self.agent = types.SimpleNamespace(user=object(), session_id="teste", message_history=MagicMock())
        self.agent.message_history.messages = [AIMessage(service.format_position({"APL": [record()]}))]

    async def test_yes_details_previous_total_and_returns_exact_tool_output(self):
        output = await self.scope["_process_apl_emp_query"](self.agent, "Sim")
        self.assertEqual(output, "Consulta formatada")
        self.sql._pesquisa_aplicacoes_emprestimos.assert_called_once_with(
            tipo="APL", detalhar=True, moeda=None, reutilizar=True)

    async def test_process_message_routes_financial_query_before_fixation(self):
        self.scope["_normalize_query_text"] = service.normalize
        load_definitions("app/agents/orchestrator.py", {"process_message"}, self.scope, "AgentOrchestrator")
        self.agent._process_apl_emp_query = types.MethodType(self.scope["_process_apl_emp_query"], self.agent)
        self.agent.read_only = False
        result = await self.scope["process_message"](self.agent, "Qual o total de aplicações?")
        self.assertEqual(result, "Consulta formatada")
        self.assertFalse(self.agent.last_response_is_contract_batch)
        self.sql._pesquisa_aplicacoes_emprestimos.assert_called_once_with(
            tipo="APL", detalhar=False, moeda=None, reutilizar=False)

    async def test_both_types_and_currency_specific_followup(self):
        await self.scope["_process_apl_emp_query"](self.agent, "Qual o total de aplicações e empréstimos?")
        self.assertEqual(self.sql._pesquisa_aplicacoes_emprestimos.call_args.kwargs["tipo"], "AMBOS")
        await self.scope["_process_apl_emp_query"](self.agent, "Detalhe os dólares")
        self.sql._pesquisa_aplicacoes_emprestimos.assert_called_with(
            tipo="APL", detalhar=True, moeda="USD", reutilizar=True)

    async def test_does_not_steal_fixation_confirmation_or_schedule_request(self):
        self.agent.message_history.messages = [self.AI("Resumo da fixação. Confirma o envio?")]
        self.assertIsNone(await self.scope["_process_apl_emp_query"](self.agent, "Sim"))
        self.assertIsNone(await self.scope["_process_apl_emp_query"](
            self.agent, "Agende aplicações todos os dias úteis às 18:15"))
        self.sql._pesquisa_aplicacoes_emprestimos.assert_not_called()

    async def test_report_queries_immediately_without_touching_conversation_cache(self):
        output = await self.scope["_process_apl_emp_query"](
            self.agent, "Gere o relatório de empréstimos. Não agende nada.", read_only=True)
        self.assertEqual(output, "Consulta formatada")
        self.assertTrue(self.sql._report_read_only)
        self.sql._pesquisa_aplicacoes_emprestimos.assert_called_once_with(
            tipo="EMP", detalhar=False, moeda=None, reutilizar=False)


if __name__ == "__main__":
    unittest.main()
