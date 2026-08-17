from datetime import date

from app.services.commercial_metrics import (
    aggregate_purchases,
    aggregate_sales_by_branch,
    aggregate_sales_totals,
    build_monthly_commercial_series,
    detect_sales_branch_from_query,
    filter_sales_by_market,
    format_pt_br,
    month_keys_between,
    parse_last_weekday_date,
    reconcile_monthly_commercial_series,
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


def test_purchase_aggregation_preserves_rows_with_the_same_order_number():
    rows = [
        {
            "numero": "001380", "fornecedor": "COMEXIM OURO FINO",
            "sacas": 338.9830508475, "peso": 20000, "valorTotal": 143873.67,
        },
        {
            "numero": "001380", "fornecedor": "COMEXIM OURO FINO",
            "sacas": 338.9830508475, "peso": 20000, "valorTotal": 143873.67,
        },
        {
            "numero": "001380", "fornecedor": "COMEXIM OURO FINO",
            "sacas": 338.9830508475, "peso": 20000, "valorTotal": 143873.67,
        },
    ]

    result = aggregate_purchases(rows)

    assert result["total_contratos"] == 3
    assert result["peso_total_kg"] == 60000.0
    assert round(result["totais_por_moeda"][0]["quantidade_total"], 8) == 1016.94915254
    assert result["totais_por_moeda"][0]["valor_total"] == 431621.01
    assert result["fornecedores"][0]["contratos"] == 3


def test_purchase_aggregation_does_not_relabel_unknown_currency_as_brl():
    result = aggregate_purchases(
        [{"numero": "1", "fornecedor": "Cafe A", "sacas": 2, "valor": 900}]
    )

    assert result["totais_por_moeda"][0]["moeda"] == "N/I"


def test_purchase_aggregation_uses_real_weight_without_converting_sacks():
    result = aggregate_purchases([
        {
            "numero": "027370", "fornecedor": "Cafe A", "sacas": 244.0677966102,
            "peso": 14400, "valorTotal": 384000,
        },
        {
            "numero": "027371", "fornecedor": "Cafe B", "sacas": 1128.813559322,
            "peso": 66600, "valorTotal": 1998000,
        },
    ])

    assert result["total_contratos"] == 2
    assert round(result["totais_por_moeda"][0]["quantidade_total"], 8) == 1372.88135593
    assert result["peso_total_kg"] == 81000.0
    assert round(result["kg_por_saca_real"], 2) == 59.0
    assert result["totais_por_moeda"][0]["valor_total"] == 2382000.0


def test_pt_br_number_format_is_stable():
    assert format_pt_br(102218.95) == "102.218,95"


def test_last_weekday_expression_resolves_previous_occurrence():
    assert parse_last_weekday_date("última quinta-feira", date(2026, 8, 17)) == "20260813"
    assert parse_last_weekday_date("sexta passada", date(2026, 8, 17)) == "20260814"
    assert parse_last_weekday_date("última segunda-feira", date(2026, 8, 17)) == "20260810"


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


def test_sales_market_filters_use_mercado_column():
    rows = [
        {"contrato": "1", "MERCADO": "INTERNO", "pais": "ALEMANHA"},
        {"contrato": "2", "MERCADO": "EXTERNO", "pais": "BRASIL"},
        {"contrato": "3", "mercado": "Externo", "pais": "BRASIL"},
    ]

    assert [row["contrato"] for row in filter_sales_by_market(rows, "interno")] == ["1"]
    assert [row["contrato"] for row in filter_sales_by_market(rows, "externo")] == ["2", "3"]


def test_sales_totals_are_in_usd_and_deduplicated():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "sacas": 10, "valorTotal": 1000},
        {"contrato": "1", "filial": "05", "cliente": "A", "sacas": 10, "valorTotal": 1000},
        {"contrato": "2", "filial": "60", "cliente": "B", "sacas": 30, "valorTotal": 6000},
    ]

    result = aggregate_sales_totals(rows)

    assert result["contratos"] == 2
    assert result["sacas"] == 40.0
    assert result["valor_usd"] == 7000.0


def test_sales_monthly_series_reports_missing_months_without_filling_them():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
        {"contrato": "2", "filial": "05", "cliente": "B", "mesEmbarque": "2026/09", "sacas": 30, "valorTotal": 6000},
    ]

    result = build_monthly_commercial_series(
        rows,
        "sales",
        month_keys_between("2026/07", "2026/10"),
    )

    assert [item["mes"] for item in result["meses_com_dados"]] == ["2026/07", "2026/09"]
    assert result["meses_sem_registros"] == ["2026/08", "2026/10"]
    assert result["meses_com_dados"][0]["sacas"] == 10.0
    assert result["meses_com_dados"][1]["valor_usd"] == 6000.0


def test_monthly_series_with_no_rows_contains_no_fabricated_values():
    result = build_monthly_commercial_series(
        [],
        "purchases",
        month_keys_between("2026/01", "2026/03"),
    )

    assert result["meses_com_dados"] == []
    assert result["meses_sem_registros"] == ["2026/01", "2026/02", "2026/03"]


def test_purchase_monthly_series_uses_only_returned_months():
    rows = [
        {"numero": "1", "filial": "05", "emissao": "20260115", "sacas": 12, "valor": 1200, "moeda": "BRL"},
        {"numero": "2", "filial": "05", "emissao": "20260310", "sacas": 8, "valor": 2000, "moeda": "USD"},
    ]

    result = build_monthly_commercial_series(
        rows,
        "purchases",
        month_keys_between("20260101", "20260331"),
    )

    assert [item["mes"] for item in result["meses_com_dados"]] == ["2026/01", "2026/03"]
    assert result["meses_sem_registros"] == ["2026/02"]
    assert result["meses_com_dados"][0]["totais_por_moeda"][0]["valor_total"] == 1200.0


def test_monthly_reconciliation_detects_contract_repeated_across_months():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/08", "sacas": 10, "valorTotal": 1000},
    ]
    series = build_monthly_commercial_series(rows, "sales", ["2026/07", "2026/08"])

    reconciliation = reconcile_monthly_commercial_series(rows, "sales", series)

    assert reconciliation["valido"] is False
    assert reconciliation["agregado"]["contratos"] == 1
    assert reconciliation["soma_meses"]["contratos"] == 2
    assert reconciliation["diferencas"]["contratos"] == 1
    assert "contratos" in reconciliation["violacoes"]


def test_monthly_reconciliation_detects_row_without_month():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
        {"contrato": "2", "filial": "05", "cliente": "B", "mesEmbarque": None, "sacas": 20, "valorTotal": 3000},
    ]
    series = build_monthly_commercial_series(rows, "sales", ["2026/07"])

    reconciliation = reconcile_monthly_commercial_series(rows, "sales", series)

    assert reconciliation["valido"] is False
    assert reconciliation["diferencas"]["sacas"] == -20
    assert reconciliation["diferencas"]["valor_usd"] == -3000


def test_monthly_reconciliation_accepts_justifiable_rounding_difference():
    rows = [
        {"contrato": "1", "filial": "05", "cliente": "A", "mesEmbarque": "2026/07", "sacas": 10, "valorTotal": 1000},
    ]
    series = build_monthly_commercial_series(rows, "sales", ["2026/07"])
    series["meses_com_dados"][0]["sacas"] = 10.005
    series["meses_com_dados"][0]["valor_usd"] = 1000.005

    reconciliation = reconcile_monthly_commercial_series(rows, "sales", series)

    assert reconciliation["valido"] is True


def test_purchase_reconciliation_detects_month_greater_than_period():
    rows = [
        {"numero": "1", "filial": "05", "emissao": "20260115", "sacas": 10, "valor": 1000, "moeda": "BRL"},
    ]
    series = build_monthly_commercial_series(rows, "purchases", ["2026/01"])
    series["meses_com_dados"][0]["totais_por_moeda"][0]["quantidade_total"] = 11

    reconciliation = reconcile_monthly_commercial_series(rows, "purchases", series)

    assert reconciliation["valido"] is False
    assert "mes_maior_quantidade:2026/01:BRL" in reconciliation["violacoes"]


if __name__ == "__main__":
    test_purchase_aggregation_uses_purchase_fields_and_weighted_average()
    test_purchase_aggregation_does_not_relabel_unknown_currency_as_brl()
    test_purchase_aggregation_uses_real_weight_without_converting_sacks()
    test_pt_br_number_format_is_stable()
    test_last_weekday_expression_resolves_previous_occurrence()
    test_sales_branch_mapping_and_aggregation()
    test_sales_branch_detection_from_query()
    test_sales_market_filters_use_mercado_column()
    test_sales_totals_are_in_usd_and_deduplicated()
    test_sales_monthly_series_reports_missing_months_without_filling_them()
    test_monthly_series_with_no_rows_contains_no_fabricated_values()
    test_purchase_monthly_series_uses_only_returned_months()
    test_monthly_reconciliation_detects_contract_repeated_across_months()
    test_monthly_reconciliation_detects_row_without_month()
    test_monthly_reconciliation_accepts_justifiable_rounding_difference()
    test_purchase_reconciliation_detects_month_greater_than_period()
    print("commercial_metrics: OK")
