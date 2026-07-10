from pathlib import Path


SQL_TOOLS = Path(__file__).parent / "app" / "agents" / "sql_tools.py"


def test_sales_valor_total_is_documented_as_usd():
    source = SQL_TOOLS.read_text(encoding="utf-8")

    assert "coluna valorTotal SEMPRE está em USD" in source
    assert "Valor Total: USD" in source
    assert "USD {_fmt_decimal(valor)}" in source
    assert "Nunca rotule valorTotal como R$" in source


def test_sales_rules_require_conversion_before_brl_comparison():
    source = SQL_TOOLS.read_text(encoding="utf-8")

    assert "comparação com valores em BRL" in source
    assert "converter usando uma cotação de câmbio" in source
    assert "sem converter primeiro para a mesma moeda" in source


if __name__ == "__main__":
    test_sales_valor_total_is_documented_as_usd()
    test_sales_rules_require_conversion_before_brl_comparison()
    print("sales_currency_rules: OK")
