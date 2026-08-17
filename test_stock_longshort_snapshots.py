from decimal import Decimal

from app.services.stock_metrics import (
    analyze_stock_weight_composition,
    build_longshort_snapshot,
    build_stock_snapshot,
    convert_weight_sacks,
    format_standard_weight_conversion,
    format_longshort_snapshot,
    snapshot_fingerprint,
)


def test_stock_snapshot_removes_only_exact_duplicate_rows():
    row = {
        "filial": "05", "armazem": "A", "lote": "L1", "linha": "PVA",
        "sacas": 10, "sacasConsumo": 4, "sacasExportacao": 6, "peso": 600,
    }
    different_lot = dict(row, lote="L2")

    snapshot = build_stock_snapshot([row, dict(row), different_lot])

    assert snapshot["linhas_recebidas"] == 3
    assert snapshot["linhas_unicas"] == 2
    assert snapshot["duplicatas_exatas"] == 1
    assert snapshot["total_sacas"] == Decimal("20")
    assert snapshot["total_lotes"] == 2


def test_global_lot_is_not_counted_twice_across_groups():
    rows = [
        {"filial": "05", "armazem": "A", "lote": "L1", "linha": "PVA", "sacas": 5},
        {"filial": "05", "armazem": "A", "lote": "L1", "linha": "GRD", "sacas": 7},
    ]

    snapshot = build_stock_snapshot(rows)

    assert snapshot["total_sacas"] == Decimal("12")
    assert snapshot["total_lotes"] == 1
    assert snapshot["repeticoes_chave_lote"] == 1


def test_longshort_components_come_from_one_row():
    row = {
        "netPosition": 1,
        "totalEstoqueExportacao": 2,
        "vendasExportacao": 3,
        "basisExportacao": 4,
        "mercadoAFixar": 5,
        "mercadoFixadas": 6,
        "mercadoAfixarEmbarcadas": 7,
        "bolsaLotes": 8,
        "bolsaSacas": 9,
    }

    snapshot = build_longshort_snapshot(row)

    assert list(snapshot.values()) == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_longshort_official_format_is_preserved():
    snapshot = build_longshort_snapshot({
        "netPosition": 1,
        "totalEstoqueExportacao": 2,
        "vendasExportacao": 3,
        "basisExportacao": 4,
        "mercadoAFixar": 5,
        "mercadoFixadas": 6,
        "mercadoAfixarEmbarcadas": 7,
        "bolsaLotes": 8,
        "bolsaSacas": 9,
    })
    result = format_longshort_snapshot(snapshot)

    for label in (
        "Posição Net LS", "Estoque Total Exportação", "Vendas Totais Exportação",
        "Basis Saldo Sacas", "Vendas Mercado A fixar", "Vendas Fixadas",
        "Vendas A Fixar Embarcadas", "Bolsa Lotes",
    ):
        assert label in result


def test_snapshot_fingerprint_changes_when_data_changes():
    first = snapshot_fingerprint([{"sacas": 10}])
    assert first == snapshot_fingerprint([{"sacas": 10}])
    assert first != snapshot_fingerprint([{"sacas": 11}])


def test_real_weight_has_priority_and_preserves_effective_59kg_ratio():
    composition = analyze_stock_weight_composition([
        {"peso": 1056.8, "sacas": 17.91},
        {"peso": 671.2, "sacas": 11.37},
    ])

    assert composition["peso_real_kg"] == Decimal("1728.0")
    assert Decimal("58.9") < composition["fator_efetivo_kg_por_saca"] < Decimal("59.1")
    assert composition["peso_estimado_kg"] == 0
    assert composition["itens"][0]["tipo"] == "aprox. 59 kg/saca"


def test_missing_real_weight_uses_explicit_60kg_standard():
    composition = analyze_stock_weight_composition([{"peso": None, "sacas": 10}])
    conversion = convert_weight_sacks(10, from_unit="sacas")

    assert composition["peso_estimado_kg"] == Decimal("600")
    assert composition["fator_padrao_kg_por_saca"] == Decimal("60")
    assert conversion["resultado"] == Decimal("600")


def test_mixed_weights_and_units_are_reported_as_composition():
    composition = analyze_stock_weight_composition([
        {"peso": 590, "sacas": 10, "embalagem": "SACA"},
        {"peso": 600, "sacas": 10, "embalagem": "SACA"},
        {"peso": 1000, "sacas": 1, "embalagem": "BIG BAG"},
    ])

    assert composition["misto"] is True
    assert {item["tipo"] for item in composition["itens"]} == {
        "SACA — aprox. 59 kg/saca",
        "SACA — aprox. 60 kg/saca",
        "BIG BAG — aprox. 1000 kg/unidade",
    }


def test_explicit_standard_conversion_is_calculated_and_explained_in_code():
    answer = format_standard_weight_conversion("Quantos kg equivalem a 100 sacas?")

    assert "6.000,00 kg" in answer
    assert "fator padrão de 60 kg por saca" in answer
    assert "peso real deve prevalecer" in answer


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"stock_longshort_snapshots: {len(tests)} tests OK")
