from pathlib import Path


SQL_TOOLS = Path(__file__).parent / "app" / "agents" / "sql_tools.py"


def test_sales_market_uses_mercado_column_not_pais():
    source = SQL_TOOLS.read_text(encoding="utf-8")

    assert "MERCADO=INTERNO" in source
    assert "MERCADO=EXTERNO" in source
    assert "filter_sales_by_market(results, \"interno\")" in source
    assert "filter_sales_by_market(results, \"externo\")" in source


def test_sales_market_direct_response_is_user_facing():
    source = SQL_TOOLS.read_text(encoding="utf-8")
    market_block = source[
        source.index("No período consultado"):
        source.index("# ESTRAT", source.index("No período consultado"))
    ]

    assert "coluna MERCADO" not in market_block
    assert "MERCADO =" not in market_block
    assert "RESULTADO DETERMIN" not in market_block
    assert "REGRAS OBRIGAT" not in market_block


if __name__ == "__main__":
    test_sales_market_uses_mercado_column_not_pais()
    test_sales_market_direct_response_is_user_facing()
    print("sales_market_output: OK")
