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


def test_successful_fixacao_tool_always_offers_hedge():
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "def _fixacao_tool_succeeded" in source
    assert "if _fixacao_tool_succeeded(current_turn_messages):" in source
    assert "Gostaria que eu fizesse o Hedge da bolsa?" in source
    assert "oferta de Hedge aplicada deterministicamente" in source


def test_retry_after_ota_preserves_pending_contract_and_value():
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "retry_after_external_adjustment" in source
    assert "repetindo fixação pendente" in source
    assert "pending_fixacao.is_awaiting_confirmation()" in source
    assert "pending_fixacao.cadastrar_valor_contrato" in source


def test_hedge_imperative_starts_collection_before_no_to_aa():
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "pode\\s+fazer|quero" in source
    assert "if no and not offered_yes:" in source
    assert "valor legítimo de Lançamento" in source


if __name__ == "__main__":
    test_sales_market_query_forces_vendas_tool_route()
    test_sales_market_route_requires_period()
    test_successful_fixacao_tool_always_offers_hedge()
    test_retry_after_ota_preserves_pending_contract_and_value()
    test_hedge_imperative_starts_collection_before_no_to_aa()
    print("orchestrator_market_routing: OK")
