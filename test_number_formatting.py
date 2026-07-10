from app.services.number_formatting import normalize_numbers_pt_br


def test_converts_us_decimal_numbers_to_pt_br():
    text = "102,218.95 / R$ 43,494,260.80 / 4,276,335.13 kg"

    assert normalize_numbers_pt_br(text) == (
        "102.218,95 / R$ 43.494.260,80 / 4.276.335,13 kg"
    )


def test_converts_us_integer_thousands_to_pt_br():
    assert normalize_numbers_pt_br("Total de registros: 1,234") == "Total de registros: 1.234"


def test_converts_plain_dot_decimals_to_pt_br():
    assert normalize_numbers_pt_br("Preço médio 1694.91 e peso 115.5 kg") == (
        "Preço médio 1.694,91 e peso 115,5 kg"
    )


def test_does_not_change_pt_br_numbers_dates_or_contracts():
    text = "R$ 43.494.260,80 em 10/07/2026 no contrato 433/25"

    assert normalize_numbers_pt_br(text) == text


if __name__ == "__main__":
    test_converts_us_decimal_numbers_to_pt_br()
    test_converts_us_integer_thousands_to_pt_br()
    test_converts_plain_dot_decimals_to_pt_br()
    test_does_not_change_pt_br_numbers_dates_or_contracts()
    print("number_formatting: OK")
