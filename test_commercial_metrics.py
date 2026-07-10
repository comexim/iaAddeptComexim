from app.services.commercial_metrics import (
    aggregate_purchases,
    aggregate_sales_by_branch,
    detect_sales_branch_from_query,
    filter_sales_by_market,
    format_pt_br,
)


def test_purchase_aggregation_uses_purchase_fields_and_weighted_average():
    rows = [
        {"numero": "1", "fornecedor": "Cafe A", "sacas": 10, "valor": 1000, "moeda": "BRL"},
        {"numero": "2", "fornecedor": "Cafe B", "sacas": 30, "valor": 6000, "moeda": "BRL"},
    ]

    result = aggregate_purchases(rows)

    assert result["total_contratos"] == 2
    assert result["totais_por_moeda"] == [
        {
            "moeda": "BRL",
            "valor_total": 7000.0,
            "quantidade_total": 40.0,
            "media_ponderada": 175.0,
        }
    ]
    assert result["fornecedores"][0]["fornecedor"] == "Cafe B"


def test_purchase_aggregation_does_not_relabel_unknown_currency_as_brl():
    result = aggregate_purchases(
        [{"numero": "1", "fornecedor": "Cafe A", "sacas": 2, "valor": 900}]
    )

    assert result["totais_por_moeda"][0]["moeda"] == "N/I"


def test_pt_br_number_format_is_stable():
    assert format_pt_br(102218.95) == "102.218,95"


def test_sales_branch_mapping_and_aggregation():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "sacas": 10, "valorTotal": 1000},
        {"contrato": "2", "filial": "60", "cliente": "B", "sacas": 30, "valorTotal": 6000},
        {"contrato": "3", "filial": "61", "cliente": "C", "sacas": 5, "valorTotal": 500},
    ]

    result = aggregate_sales_by_branch(rows)

    assert result[0]["empresa"] == "CUSA"
    assert result[0]["filial"] == "60"
    assert result[0]["sacas"] == 30.0
    assert {item["empresa"] for item in result} == {"COBRA", "CUSA", "CEU"}


def test_sales_branch_detection_from_query():
    assert detect_sales_branch_from_query("Mostre as vendas da COBRA") == "05"
    assert detect_sales_branch_from_query("Quero apenas a filial 61") == "61"


def test_sales_market_filters_use_pais_column():
    rows = [
        {"contrato": "1", "pais": "BRASIL"},
        {"contrato": "2", "pais": "ALEMANHA"},
        {"contrato": "3", "pais": "Estados Unidos"},
    ]

    assert [row["contrato"] for row in filter_sales_by_market(rows, "interno")] == ["1"]
    assert [row["contrato"] for row in filter_sales_by_market(rows, "externo")] == ["2", "3"]


if __name__ == "__main__":
    test_purchase_aggregation_uses_purchase_fields_and_weighted_average()
    test_purchase_aggregation_does_not_relabel_unknown_currency_as_brl()
    test_pt_br_number_format_is_stable()
    test_sales_branch_mapping_and_aggregation()
    test_sales_branch_detection_from_query()
    test_sales_market_filters_use_pais_column()
    print("commercial_metrics: OK")
