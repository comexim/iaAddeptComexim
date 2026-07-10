from pathlib import Path


SQL_TOOLS = Path(__file__).parent / "app" / "agents" / "sql_tools.py"


def test_market_terms_are_not_treated_as_client_names():
    source = SQL_TOOLS.read_text(encoding="utf-8")

    assert r"\bmercado\s+interno\b" in source
    assert r"\bmercado\s+externo\b" in source
    assert "não é cliente" in source


if __name__ == "__main__":
    test_market_terms_are_not_treated_as_client_names()
    print("sales_client_extraction: OK")
