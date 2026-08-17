"""Apresentação segura de campos financeiros sem alterar o retorno original."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, List

from app.services.accounts_payable_metrics import payable_decimal


MISSING_SUPPLIER = "Fornecedor não informado"


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def supplier_display(row: Dict[str, Any]) -> str:
    """Usa exclusivamente fornecedor; nunca natureza ou descrição como fallback."""
    supplier = str(row.get("fornecedor") or "").strip()
    return supplier or MISSING_SUPPLIER


def _record_value(row: Dict[str, Any]):
    value = row.get("valor")
    if value in (None, ""):
        value = row.get("valorStr")
    return payable_decimal(value)


def zero_value_classification(row: Dict[str, Any]) -> str:
    """Classifica um zero somente por indícios explícitos, sem inventar motivo."""
    if _record_value(row) != 0:
        return ""
    context = " ".join(
        _normalized(row.get(field))
        for field in ("natureza", "descricao", "descrição", "tipo", "historico", "histórico")
    )
    if any(term in context for term in ("cambio", "cambial", "juros ctr", "variacao cambial")):
        return "Ajuste cambial sem valor"
    if any(term in context for term in ("ajuste", "contabil", "lancamento")):
        return "Ajuste contábil sem valor"
    return "Registro sem valor"


def prepare_financial_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Copia a linha e acrescenta campos de exibição; campos originais ficam intactos."""
    prepared = dict(row)
    prepared["fornecedor_exibicao"] = supplier_display(row)
    classification = zero_value_classification(row)
    prepared["valor_zerado"] = bool(classification)
    prepared["classificacao_valor_zero"] = classification
    return prepared


def split_zero_value_records(
    rows: Iterable[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nonzero: List[Dict[str, Any]] = []
    zero: List[Dict[str, Any]] = []
    for row in rows:
        (zero if _record_value(row) == 0 else nonzero).append(row)
    return nonzero, zero


def format_zero_value_records(rows: Iterable[Dict[str, Any]]) -> str:
    lines = []
    for row in rows:
        number = str(row.get("numero") or "SEM NÚMERO").strip()
        nature = str(row.get("natureza") or row.get("descricao") or "Natureza não informada").strip()
        lines.append(
            f"- {number} | {supplier_display(row)} | {nature} | "
            f"{zero_value_classification(row)}"
        )
    return "\n".join(lines)
