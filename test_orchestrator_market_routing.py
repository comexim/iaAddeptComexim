from pathlib import Path


ORCHESTRATOR = Path(__file__).parent / "app" / "agents" / "orchestrator.py"


def test_sales_market_query_forces_vendas_tool_route():
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "_should_force_vendas_market_query" in source
    assert "mercado interno" in source
    assert "mercado externo" in source
    assert "sql_tools._pesquisa_vendas(periodo=periodo_forcado)" in source


def test_sales_market_route_requires_period():
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "De qual período você gostaria de consultar as vendas por mercado?" in source
    assert "_extract_sales_period_from_message" in source


def test_batch_route_precedes_legacy_hedge_and_records_history():
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    route = source.index("batch_output = await ContractBatchFlow(")
    legacy = source.index("hedge_output = await self._process_hedge_flow(message)")
    assert route < legacy
    assert 'has_permission=self.user.has_permission("Fixacao")' in source
    assert "self.message_history.add_ai_message(batch_output)" in source


def test_batch_result_is_not_rewritten_by_llm():
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "RESULTADO_LOTE:" in source
    assert "last_response_is_contract_batch = True" in source


if __name__ == "__main__":
    test_sales_market_query_forces_vendas_tool_route()
    test_sales_market_route_requires_period()
    test_batch_route_precedes_legacy_hedge_and_records_history()
    test_batch_result_is_not_rewritten_by_llm()
    print("orchestrator_market_routing: OK")
