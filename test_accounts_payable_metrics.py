from decimal import Decimal

from app.services.accounts_payable_metrics import (
    deduplicate_payables,
    reconcile_payables,
)


def test_same_business_fields_without_id_are_preserved():
    rows = [
        {"numero": "10", "parcela": "1", "filial": "05", "fornecedor": "A", "natureza": "CAFE", "valor": 100},
        {"numero": "10", "parcela": "1", "filial": "05", "fornecedor": "A", "natureza": "TARIFA", "valor": 100},
    ]

    unique, duplicates = deduplicate_payables(rows)

    assert len(unique) == 2
    assert duplicates == 0


def test_only_repeated_id_protheus_is_deduplicated():
    rows = [
        {"idProtheus": "ABC123", "numero": "10", "valor": 100},
        {"idProtheus": "ABC123", "numero": "10", "valor": 100},
        {"idProtheus": "XYZ789", "numero": "10", "valor": 100},
    ]

    unique, duplicates = deduplicate_payables(rows)

    assert [row["idProtheus"] for row in unique] == ["ABC123", "XYZ789"]
    assert duplicates == 1


def test_complete_detail_reconciles_total_and_count():
    rows = [{"valor": "100,25"}, {"valor": Decimal("50.75")}]

    result = reconcile_payables(rows, aggregate_total=151, declared_count=2)

    assert result["valido"] is True
    assert result["soma_detalhes"] == Decimal("151.00")


def test_divergent_sum_and_count_are_blocked():
    rows = [{"valor": 100}, {"valor": 50}]

    result = reconcile_payables(rows, aggregate_total=140, declared_count=3)

    assert result["valido"] is False
    assert "soma_detalhes" in result["violacoes"]
    assert "quantidade_titulos" in result["violacoes"]


def test_title_greater_than_period_is_blocked():
    result = reconcile_payables([{"valor": 120}], aggregate_total=100, declared_count=1)

    assert result["valido"] is False
    assert "titulo_maior_total:1" in result["violacoes"]


def test_partial_page_is_identified_and_not_compared_to_complete_total():
    result = reconcile_payables(
        [{"valor": 100}],
        aggregate_total=300,
        declared_count=1,
        partial=True,
        complete_count=3,
    )

    assert result["valido"] is True
    assert result["parcial"] is True
    assert result["quantidade_completa"] == 3


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"accounts_payable_metrics: {len(tests)} tests OK")
