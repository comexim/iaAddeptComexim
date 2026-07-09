from app.services.commercial_metrics import aggregate_purchases, format_pt_br


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


if __name__ == "__main__":
    test_purchase_aggregation_uses_purchase_fields_and_weighted_average()
    test_purchase_aggregation_does_not_relabel_unknown_currency_as_brl()
    test_pt_br_number_format_is_stable()
    print("commercial_metrics: OK")
