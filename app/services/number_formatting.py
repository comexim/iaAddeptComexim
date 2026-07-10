"""Normalização de números em texto para o padrão brasileiro."""

import re


_US_DECIMAL_NUMBER = re.compile(
    r"(?<![\w/.-])(?P<number>-?\d{1,3}(?:,\d{3})+\.\d+)(?![\w/.-])"
)
_US_INTEGER_NUMBER = re.compile(
    r"(?<![\w/.-])(?P<number>-?\d{1,3}(?:,\d{3})+)(?![\w/.-])"
)
_PLAIN_DECIMAL_NUMBER = re.compile(
    r"(?<![\w/.-])(?P<sign>-?)(?P<int>\d+)\.(?P<dec>\d+)(?![\w/.,-])"
)


def _convert_us_number_to_pt_br(value: str) -> str:
    return value.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _format_plain_decimal(match: re.Match) -> str:
    integer = int(match.group("int"))
    decimals = match.group("dec")
    sign = match.group("sign")
    integer_part = f"{integer:,}".replace(",", ".")
    return f"{sign}{integer_part},{decimals}"


def normalize_numbers_pt_br(text: str) -> str:
    """Converte números como 102,218.95 para 102.218,95 em texto livre.

    A regra é propositalmente conservadora: só converte números com separador
    de milhar americano (vírgula) para evitar mexer em datas, contratos e
    números já escritos em padrão brasileiro.
    """
    if not text:
        return text

    text = _US_DECIMAL_NUMBER.sub(
        lambda match: _convert_us_number_to_pt_br(match.group("number")),
        text,
    )
    text = _PLAIN_DECIMAL_NUMBER.sub(_format_plain_decimal, text)
    text = _US_INTEGER_NUMBER.sub(
        lambda match: match.group("number").replace(",", "."),
        text,
    )
    return text
