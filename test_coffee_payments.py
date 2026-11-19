"""Regressões offline da consulta de pagamentos de café."""

from datetime import datetime
from decimal import Decimal
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services import coffee_payments as coffee
from app.utils.date_parser import DateParser
from test_scheduled_report_read_only import load_definitions


class CoffeePaymentsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        today = patch.object(DateParser, "get_current_date", return_value=datetime(2026, 11, 19))
        today.start()
        self.addCleanup(today.stop)
        self.database = Mock()
        self.database.execute_procedure.return_value = [
            {"FILIAL": "01", "SOLICITACAO": "004582", "PEDIDO": "009731",
             "EMISSAO": "20261110", "VENCIMENTO": "20261119",
             "NOME_FORNECEDOR": "Cooperativa Exemplo", "SACAS": 120,
             "VALOR_TOTAL": Decimal("52500.10"), "OUTRO_CAMPO": "Dado da SP"},
            {"FILIAL": "02", "PEDIDO": "009732", "VALOR_TOTAL": Decimal("34949.90")},
        ]
        scope = {"sql_client": self.database}
        load_definitions("app/agents/sql_tools.py", {"_consultar_pagamentos_cafe"}, scope, "SQLTools")
        tools = type("SQLTools", (), scope)
        self.tool_factory = Mock(side_effect=lambda *_: tools())
        self.cache = AsyncMock()
        self.validator = Mock()
        self.validator.validate_permission.return_value = (True, None)
        modules = patch.dict(sys.modules, {
            "app.agents.sql_tools": SimpleNamespace(SQLTools=self.tool_factory),
            "app.core.config": SimpleNamespace(settings=SimpleNamespace(app_env="test")),
            "app.core.redis_client": SimpleNamespace(redis_client=self.cache),
            "app.utils.sql_validator": SimpleNamespace(sql_validator=self.validator),
        })
        modules.start()
        self.addCleanup(modules.stop)
        self.orchestrator = SimpleNamespace(user=SimpleNamespace(telefone="teste"), session_id="teste",
                                            message_history=SimpleNamespace(messages=[]))

    def previous(self, output):
        self.orchestrator.message_history.messages.append(SimpleNamespace(type="ai", content=output))

    def test_relative_and_explicit_periods(self):
        for query, expected in (
            ("hoje", ("20261119", "20261119")),
            ("essa semana", ("20261116", "20261122")),
            ("este mês", ("20261101", "20261130")),
            ("nos próximos três dias", ("20261119", "20261121")),
            ("de 18/11/2026 a 20/11/2026", ("20261118", "20261120")),
            ("20261118", ("20261118", "20261118")),
        ):
            with self.subTest(query=query):
                self.assertEqual(coffee.payment_period(query), expected)
        self.assertIsNone(coffee.payment_period("desde 18/11/2026"))
        self.assertIsNone(coffee.payment_period("Qual o maior pagamento de café?"))
        with self.assertRaises(ValueError):
            coffee.payment_period("de 20/11/2026 a 18/11/2026")

    async def test_period_then_summary_list_and_title_detail_use_same_query(self):
        question = await coffee.handle_query(self.orchestrator, "Quais as contas a pagar de café?")
        self.assertIn(coffee.PERIOD_QUESTION, question)
        self.database.execute_procedure.assert_not_called()
        self.previous(question)
        summary = await coffee.handle_query(self.orchestrator, "próximos três dias")
        self.assertIn("Total de títulos: 2", summary)
        self.assertIn("R$ 87.450,00", summary)
        self.assertIn(coffee.LIST_QUESTION, summary)
        self.previous(summary)
        self.cache.get.return_value = json.loads(self.cache.set.await_args.args[1])
        listing = await coffee.handle_query(self.orchestrator, "Sim")
        for fragment in ("Filial: 01", "Solicitação: 004582", "Pedido: 009731", "Emissão: 10/11/2026",
                         "Vencimento: 19/11/2026", "Fornecedor: Cooperativa Exemplo", "Sacas: 120",
                         "Valor a Pagar: R$ 52.500,10"):
            self.assertIn(fragment, listing)
        self.assertNotIn("OUTRO_CAMPO", listing)
        self.previous(listing)
        detail = await coffee.handle_query(self.orchestrator, "Mostre os outros dados do pedido 9731")
        self.assertIn("OUTRO_CAMPO: Dado da SP", detail)
        self.database.execute_procedure.assert_called_once_with(
            "usp_IA_PagamentoCafe", {"VencIni": "20261119", "VencFim": "20261121"}
        )

    async def test_permission_and_unrelated_messages_do_not_read_database(self):
        self.assertIsNone(await coffee.handle_query(self.orchestrator, "Qual a cotação do café hoje?"))
        self.assertIsNone(await coffee.handle_query(self.orchestrator, "Sim"))
        self.validator.validate_permission.return_value = (False, "Sem permissão de Financeiro")
        self.assertEqual(await coffee.handle_query(self.orchestrator, "Pagamentos de café hoje"),
                         "Sem permissão de Financeiro")
        self.validator.validate_permission.assert_called_once_with(self.orchestrator.user, "usp_IA_PagamentoCafe")
        self.cache.get.assert_not_called()
        self.database.execute_procedure.assert_not_called()

    async def test_duplicate_order_and_empty_results(self):
        self.previous(f"{coffee.HEADING}*\n{coffee.LIST_QUESTION}")
        self.cache.get.return_value = {"rows": [{"PEDIDO": "009", "FILIAL": "01"}, {"PEDIDO": "9", "FILIAL": "02"}]}
        result = await coffee.handle_query(self.orchestrator, "Detalhes do pedido 9")
        self.assertIn("Título 1 — filial 01", result)
        self.assertIn("Título 2 — filial 02", result)
        self.database.execute_procedure.return_value = []
        result = await coffee.handle_query(self.orchestrator, "Pagamentos de café hoje")
        self.assertIn("Nenhum título encontrado", result)
        self.assertNotIn(coffee.LIST_QUESTION, result)

    async def test_multiple_orders_return_unique_titles_and_accept_bare_choice_for_duplicate(self):
        self.previous(f"{coffee.HEADING} — lista*")
        self.cache.get.return_value = {"rows": [
            {"PEDIDO": "976002", "FILIAL": "05", "SOLICITACAO": "027854", "ESTAGIO": "SC7"},
            {"PEDIDO": "976002", "FILIAL": "05", "SOLICITACAO": "027855"},
            {"PEDIDO": "975990", "FILIAL": "05", "CONTRATO_CAFE": "1662/26"},
        ]}
        result = await coffee.handle_query(self.orchestrator, "Quais são os detalhes do pedido 976002 e 975990")
        self.assertIn("Há mais de um registro para o pedido 976002.", result)
        self.assertIn("solicitação 027854", result)
        self.assertIn("solicitação 027855", result)
        self.assertIn("Pedido: 975990", result)
        self.assertIn("Contrato de café: 1662/26", result)
        self.previous(result)
        invalid = await coffee.handle_query(self.orchestrator, "3")
        self.assertIn("Escolha um dos títulos apresentados", invalid)
        self.assertNotIn("Contrato de café: 1662/26", invalid)
        self.previous(invalid)
        selected = await coffee.handle_query(self.orchestrator, "1")
        self.assertIn("Estágio: SC7", selected)
        self.assertIn("Pedido: 976002", selected)
        self.assertNotIn("027855", selected)
        self.database.execute_procedure.assert_not_called()

    def test_details_format_decimal_fields_without_changing_identifiers(self):
        output = coffee.title_block(30, {
            "SACAS": "1342.37", "KILOS": "79200.0", "PRECO_MEDIO": "1607.753450985943",
            "CONSUMO_SACAS": "127.52515", "PEDIDO": "009731", "LOJA": "0001",
            "DT_CANCELAMENTO": "20261119",
        }, extra=True)
        for fragment in ("Sacas: 1.342,37", "Quilos: 79.200", "Preço médio: 1.607,75",
                         "Sacas para consumo: 127,52515", "Pedido: 009731", "Loja: 0001",
                         "Data de cancelamento: 19/11/2026"):
            self.assertIn(fragment, output)

    async def test_scheduled_report_uses_requested_period_not_wrapper_dates(self):
        result = await coffee.handle_query(self.orchestrator, (
            "Hoje é 19/11/2026. Gere e mostre agora o seguinte relatório completo: "
            "pagamentos de café de 18/11/2026 a 20/11/2026. Execute diretamente sem fazer perguntas."
        ), read_only=True)
        self.assertIn("18/11/2026 a 20/11/2026", result)
        self.assertEqual(len(self.orchestrator.last_report_rows), 2)
        self.database.execute_procedure.assert_called_once_with(
            "usp_IA_PagamentoCafe", {"VencIni": "20261118", "VencFim": "20261120"}
        )
        self.cache.set.assert_not_called()
