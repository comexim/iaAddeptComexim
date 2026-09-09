from decimal import Decimal

from app.services.database_detail import (
    TRUSTED_DATABASE_DETAIL_PREFIX,
    calculate_field_totals_by_currency,
    database_detail_request,
    format_trusted_database_detail,
    select_database_detail_rows,
)


def test_detects_explicit_database_detail_requests():
    assert database_detail_request("Liste os 3 maiores títulos")["requested"] is True
    assert database_detail_request("Quais contratos foram vendidos?")["requested"] is True
    assert database_detail_request("Qual o total vendido?")["requested"] is False
    assert database_detail_request("Liste as vendas por cliente")["requested"] is False
    assert database_detail_request("Quais clientes têm contas vencidas?")["requested"] is False


def test_selects_only_existing_rows_and_orders_largest_values():
    rows = [
        {"numero": "A", "valor": Decimal("10")},
        {"numero": "B", "valor": Decimal("30")},
        {"numero": "C", "valor": Decimal("20")},
    ]

    selected = select_database_detail_rows(rows, limit=2, largest_first=True)

    assert selected == [rows[1], rows[2]]
    assert all(row in rows for row in selected)


def test_formats_each_selected_database_row_once_without_completing_the_list():
    rows = [
        {"numero": "973669", "parcela": "01", "fornecedor": "LAUDELINO", "valor": Decimal("100.25")},
        {"numero": "971764", "parcela": "02", "fornecedor": "RONDINI", "valor": Decimal("80.50")},
        {"numero": "100001", "parcela": "01", "fornecedor": "COOPERATIVA", "valor": Decimal("20")},
    ]

    output = format_trusted_database_detail(
        rows,
        source_name="usp_IA_ContasPagas",
        query="Liste os 2 maiores títulos",
        preferred_fields=("numero", "parcela", "fornecedor", "valor"),
    )

    assert output is not None
    assert output.startswith(TRUSTED_DATABASE_DETAIL_PREFIX)
    assert "Registros retornados após os filtros: 3." in output
    assert "Registros exibidos: 2." in output
    assert "Registros não exibidos: 1." in output
    assert "numero=973669" in output
    assert "numero=971764" in output
    assert "numero=100001" not in output
    assert "100.25" in output
    assert "80.50" in output


def test_preserves_distinct_rows_even_when_the_document_number_repeats():
    rows = [
        {"numero": "973669", "fornecedor": "A", "valor": 10},
        {"numero": "973669", "fornecedor": "B", "valor": 20},
    ]

    selected = select_database_detail_rows(rows, limit=0, largest_first=False)

    assert selected == rows
    assert len(selected) == 2


def test_calculates_totals_on_full_result_before_limiting_details():
    rows = [
        {"numero": "A", "valor": Decimal("100")},
        {"numero": "B", "valor": Decimal("80")},
        {"numero": "C", "valor": Decimal("20")},
    ]
    calculator_received = []

    def calculate_totals(source_rows):
        calculator_received.extend(source_rows)
        return {
            "valor_total": sum((row["valor"] for row in source_rows), Decimal("0")),
        }

    output = format_trusted_database_detail(
        rows,
        source_name="teste",
        query="Liste os 2 maiores títulos",
        preferred_fields=("numero", "valor"),
        totals_calculator=calculate_totals,
    )

    assert calculator_received == rows
    assert "Registros exibidos: 2." in output
    assert "Registros não exibidos: 1." in output
    assert "Totais calculados sobre os 3 registros antes do corte:" in output
    assert "- valor_total: 200" in output


def test_field_totals_keep_currencies_separate():
    totals = calculate_field_totals_by_currency(
        [
            {"moeda": "BRL", "valor": "100,50", "saldo": "80,25"},
            {"moeda": "BRL", "valor": "20", "saldo": "10"},
            {"moeda": "USD", "valor": "30", "saldo": "15"},
        ],
        "valor",
        "saldo",
    )

    assert totals == {
        "saldo_total_BRL": Decimal("90.25"),
        "saldo_total_USD": Decimal("15"),
        "valor_total_BRL": Decimal("120.50"),
        "valor_total_USD": Decimal("30"),
    }


if __name__ == "__main__":
    test_detects_explicit_database_detail_requests()
    test_selects_only_existing_rows_and_orders_largest_values()
    test_formats_each_selected_database_row_once_without_completing_the_list()
    test_preserves_distinct_rows_even_when_the_document_number_repeats()
    test_calculates_totals_on_full_result_before_limiting_details()
    test_field_totals_keep_currencies_separate()
    print("database_detail: 6 tests OK")
