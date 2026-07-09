"""Métricas determinísticas para consultas comerciais.

Este módulo não conhece LLM nem WhatsApp. Ele recebe linhas retornadas pelo
banco e calcula totais sem misturar o esquema de vendas com o de compras.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def format_pt_br(value: Any, decimals: int = 2) -> str:
    number = _decimal(value)
    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def normalize_currency(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {
        "R$": "BRL",
        "REAL": "BRL",
        "REAIS": "BRL",
        "US$": "USD",
        "DOLAR": "USD",
        "DÓLAR": "USD",
        "DOLARES": "USD",
        "DÓLARES": "USD",
        "€": "EUR",
        "EURO": "EUR",
        "EUROS": "EUR",
    }
    return aliases.get(text, text if text in {"BRL", "USD", "EUR"} else "N/I")


def row_currency(row: Dict[str, Any]) -> str:
    for field in ("moeda", "currency", "moedaContrato", "moedaFixacao"):
        if row.get(field) not in (None, ""):
            return normalize_currency(row[field])
    return "N/I"


def aggregate_purchases(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega somente campos do esquema de compras."""
    unique: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        identifier = str(
            row.get("numero") or row.get("solicitacao") or row.get("pedido") or index
        ).strip()
        branch = str(row.get("filial") or "").strip()
        key = f"{identifier}|{branch}"
        unique.setdefault(key, row)

    totals_by_currency = defaultdict(lambda: {"value": Decimal("0"), "quantity": Decimal("0")})
    suppliers = defaultdict(lambda: {"value": Decimal("0"), "quantity": Decimal("0"), "contracts": 0})

    for row in unique.values():
        currency = row_currency(row)
        value = _decimal(row.get("valor") or row.get("valorTotal") or row.get("valorContrato"))
        quantity = _decimal(row.get("sacas") or row.get("quantidade") or row.get("qtd"))
        supplier = str(row.get("fornecedor") or row.get("produtor") or "SEM FORNECEDOR").strip()

        totals_by_currency[currency]["value"] += value
        totals_by_currency[currency]["quantity"] += quantity
        suppliers[supplier]["value"] += value
        suppliers[supplier]["quantity"] += quantity
        suppliers[supplier]["contracts"] += 1

    currency_totals: List[Dict[str, Any]] = []
    for currency in sorted(totals_by_currency):
        item = totals_by_currency[currency]
        weighted_average = item["value"] / item["quantity"] if item["quantity"] else None
        currency_totals.append(
            {
                "moeda": currency,
                "valor_total": float(item["value"]),
                "quantidade_total": float(item["quantity"]),
                "media_ponderada": float(weighted_average) if weighted_average is not None else None,
            }
        )

    supplier_totals = [
        {
            "fornecedor": supplier,
            "contratos": values["contracts"],
            "quantidade": float(values["quantity"]),
            "valor": float(values["value"]),
        }
        for supplier, values in suppliers.items()
    ]
    supplier_totals.sort(key=lambda item: abs(item["valor"]), reverse=True)

    return {
        "total_contratos": len(unique),
        "totais_por_moeda": currency_totals,
        "fornecedores": supplier_totals,
    }

