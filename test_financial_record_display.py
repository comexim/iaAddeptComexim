from app.services.financial_record_display import (
    MISSING_SUPPLIER,
    format_zero_value_records,
    prepare_financial_record,
    split_zero_value_records,
    supplier_display,
    zero_value_classification,
)


def test_missing_supplier_never_falls_back_to_nature():
    row = {"fornecedor": "", "natureza": "JUROS CTR CAMBIO", "valor": 0}
    assert supplier_display(row) == MISSING_SUPPLIER
    assert zero_value_classification(row) == "Ajuste cambial sem valor"


def test_original_fields_are_preserved():
    row = {"fornecedor": None, "natureza": "AJUSTE CONTABIL", "valor": 0}
    prepared = prepare_financial_record(row)
    assert prepared["fornecedor"] is None
    assert prepared["natureza"] == "AJUSTE CONTABIL"
    assert prepared["fornecedor_exibicao"] == MISSING_SUPPLIER
    assert prepared["classificacao_valor_zero"] == "Ajuste contábil sem valor"


def test_zero_records_are_separated_from_ranking_set():
    nonzero, zero = split_zero_value_records([
        {"numero": "1", "valor": 100},
        {"numero": "2", "valor": 0},
    ])
    assert [row["numero"] for row in nonzero] == ["1"]
    assert [row["numero"] for row in zero] == ["2"]


def test_zero_record_format_keeps_nature_separate_from_supplier():
    text = format_zero_value_records([
        {"numero": "10", "fornecedor": "", "natureza": "JUROS CTR CAMBIO", "valor": 0}
    ])
    assert "Fornecedor não informado | JUROS CTR CAMBIO | Ajuste cambial sem valor" in text


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"financial_record_display: {len(tests)} tests OK")
