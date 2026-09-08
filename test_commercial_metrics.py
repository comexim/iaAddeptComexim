from datetime import date

from app.services.commercial_metrics import (
    aggregate_purchases,
    aggregate_purchases_by_quality,
    aggregate_sales_by_branch,
    aggregate_sales_totals,
    build_monthly_commercial_series,
    collapse_replicated_sales_parent_volumes,
    detect_sales_branch_from_query,
    filter_sales_by_market,
    filter_unfixed_sales_position,
    format_pt_br,
    is_unfixed_sales_position_query,
    is_unfixed_sales_summary_query,
    normalize_sales_sacks_to_60kg,
    month_keys_between,
    parse_last_weekday_date,
    reconcile_monthly_commercial_series,
    sales_fixation_status,
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


def test_purchase_aggregation_defaults_missing_currency_to_brl():
    result = aggregate_purchases(
        [{"numero": "1", "fornecedor": "Cafe A", "sacas": 2, "valor": 900}]
    )

    assert result["totais_por_moeda"][0]["moeda"] == "BRL"


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


def test_purchase_quality_uses_line_field_and_weights_differential_by_sacks():
    result = aggregate_purchases_by_quality([
        {"numero": "1", "linha": "BICA CORRIDA", "diferencial": -48, "sacas": 10, "peso": 600},
        {"numero": "2", "linha": "BICA CORRIDA", "diferencial": -48, "sacas": 20, "peso": 1200},
        {"numero": "3", "linha": "BICA CORRIDA", "diferencial": -40, "sacas": 5, "peso": 300},
    ])

    assert len(result) == 1
    assert result[0]["linha"] == "BICA CORRIDA"
    assert result[0]["pedidos"] == 3
    assert result[0]["sacas"] == 35.0
    assert result[0]["peso_kg"] == 2100.0
    assert round(result[0]["diferencial_medio_ponderado"], 2) == -46.86
    assert [item["identificador"] for item in result[0]["contratos"]] == ["1", "2", "3"]
    assert [item["diferencial"] for item in result[0]["contratos"]] == [-48.0, -48.0, -40.0]


def test_missing_purchase_line_is_explicit_and_never_ordinal():
    result = aggregate_purchases_by_quality([
        {"numero": "1", "linha": "", "diferencial": -48, "sacas": 10},
    ])

    assert result[0]["linha"] == "NÃO INFORMADA"
    assert result[0]["linha"] not in {"1", "01", "LINHA 1", "LINHA 01"}


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


def test_unfixed_parent_volume_is_counted_once_when_repeated_in_parcels():
    rows = [
        {"contrato": "138/21A", "filial": "05", "cliente": "A", "sacas": 508.47},
        {"contrato": "138/21B", "filial": "05", "cliente": "A", "sacas": 508.47},
        {"contrato": "138/21C", "filial": "05", "cliente": "A", "sacas": 508.47},
        {"contrato": "138/21D", "filial": "05", "cliente": "A", "sacas": 508.47},
    ]

    collapsed = collapse_replicated_sales_parent_volumes(rows)
    totals = aggregate_sales_totals(collapsed["rows"])

    assert [row["contrato"] for row in collapsed["rows"]] == ["138/21A"]
    assert collapsed["collapsed_parcel_rows"] == 3
    assert collapsed["collapsed_parent_contracts"] == 1
    assert totals["sacas"] == 508.47


def test_unfixed_parcels_with_distinct_volumes_are_preserved():
    rows = [
        {"contrato": "200/26A", "filial": "05", "cliente": "A", "sacas": 300},
        {"contrato": "200/26B", "filial": "05", "cliente": "A", "sacas": 200},
    ]

    collapsed = collapse_replicated_sales_parent_volumes(rows)

    assert collapsed["rows"] == rows
    assert collapsed["collapsed_parcel_rows"] == 0
    assert collapsed["ambiguous_parent_contracts"] == ["200/26"]


def test_unfixed_parcels_are_not_merged_across_branch_or_client():
    rows = [
        {"contrato": "300/26A", "filial": "05", "cliente": "A", "sacas": 100},
        {"contrato": "300/26B", "filial": "60", "cliente": "A", "sacas": 100},
        {"contrato": "300/26C", "filial": "05", "cliente": "B", "sacas": 100},
    ]

    collapsed = collapse_replicated_sales_parent_volumes(rows)

    assert collapsed["rows"] == rows
    assert collapsed["collapsed_parcel_rows"] == 0


def test_unfixed_parcels_without_volume_are_preserved_for_audit():
    rows = [
        {"contrato": "400/26A", "filial": "05", "cliente": "A", "sacas": None},
        {"contrato": "400/26B", "filial": "05", "cliente": "A", "sacas": None},
    ]

    collapsed = collapse_replicated_sales_parent_volumes(rows)

    assert collapsed["rows"] == rows
    assert collapsed["collapsed_parcel_rows"] == 0


def test_detects_unfixed_position_and_summary_queries():
    assert is_unfixed_sales_position_query("Contratos a fixar") is True
    assert is_unfixed_sales_position_query("Vendas não fixadas") is True
    assert is_unfixed_sales_summary_query("Qual o volume total de vendas a fixar?") is True
    assert is_unfixed_sales_summary_query("Liste os contratos a fixar") is False


def test_unfixed_position_combines_price_mode_and_effective_fixed_value():
    rows = [
        {"contrato": "1", "precoFix": "A fixar", "valorFixado": 0, "sacasSaldo": 0},
        {"contrato": "2", "precoFix": "A", "valorFixado": None},
        {"contrato": "3", "precoFix": "Fixo", "valorFixado": 0},
        {"contrato": "4", "precoFix": "A fixar", "valorFixado": 125},
        {"contrato": "5", "precoFix": "", "valorFixado": 0},
        {"contrato": "6", "precoFix": "A fixar", "valorFixado": "inválido"},
    ]

    result = filter_unfixed_sales_position(rows)

    assert [row["contrato"] for row in result["rows"]] == ["1", "2"]
    assert result["fixed_price_mode_excluded"] == 1
    assert result["already_fixed_excluded"] == 1
    assert result["invalid_mode_excluded"] == 1
    assert result["invalid_value_excluded"] == 1
    assert sales_fixation_status(rows[0]) == "unfixed"
    assert sales_fixation_status(rows[2]) == "fixed"
    assert sales_fixation_status(rows[3]) == "fixed"
    assert sales_fixation_status(rows[4]) == "unknown"


def test_unfixed_position_sacks_use_contract_weight_divided_by_60kg():
    result = normalize_sales_sacks_to_60kg([
        {"contrato": "1", "peso": 30000, "sacas": 508.47},
        {"contrato": "2", "peso": None, "sacas": 10},
    ])

    assert float(result["rows"][0]["sacas"]) == 500.0
    assert result["rows"][1]["sacas"] == 10
    assert result["total_sacks"] == 510.0
    assert result["weight_based_rows"] == 1
    assert result["fallback_rows"] == 1


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
    test_purchase_aggregation_defaults_missing_currency_to_brl()
    test_purchase_aggregation_uses_real_weight_without_converting_sacks()
    test_pt_br_number_format_is_stable()
    test_last_weekday_expression_resolves_previous_occurrence()
    test_sales_branch_mapping_and_aggregation()
    test_sales_branch_detection_from_query()
    test_sales_market_filters_use_mercado_column()
    test_sales_totals_are_in_usd_and_deduplicated()
    test_unfixed_parent_volume_is_counted_once_when_repeated_in_parcels()
    test_unfixed_parcels_with_distinct_volumes_are_preserved()
    test_unfixed_parcels_are_not_merged_across_branch_or_client()
    test_unfixed_parcels_without_volume_are_preserved_for_audit()
    test_detects_unfixed_position_and_summary_queries()
    test_unfixed_position_combines_price_mode_and_effective_fixed_value()
    test_unfixed_position_sacks_use_contract_weight_divided_by_60kg()
    test_sales_monthly_series_reports_missing_months_without_filling_them()
    test_monthly_series_with_no_rows_contains_no_fabricated_values()
    test_purchase_monthly_series_uses_only_returned_months()
    test_monthly_reconciliation_detects_contract_repeated_across_months()
    test_monthly_reconciliation_detects_row_without_month()
    test_monthly_reconciliation_accepts_justifiable_rounding_difference()
    test_purchase_reconciliation_detects_month_greater_than_period()
    print("commercial_metrics: OK")
