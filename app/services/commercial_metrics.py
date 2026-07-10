"""Métricas determinísticas para consultas comerciais.

Este módulo não conhece LLM nem WhatsApp. Ele recebe linhas retornadas pelo
banco e calcula totais sem misturar o esquema de vendas com o de compras.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List

SALES_BRANCHES = {
    "05": "COBRA",
    "60": "CUSA",
    "61": "CEU",
}


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


def normalize_text(value: Any) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def sales_branch_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return digits.zfill(2)[-2:]

    normalized = normalize_text(text)
    for code, name in SALES_BRANCHES.items():
        if normalized == normalize_text(name):
            return code
    return text or "N/I"


def sales_branch_name(value: Any) -> str:
    code = sales_branch_code(value)
    return SALES_BRANCHES.get(code, f"FILIAL {code}" if code != "N/I" else "SEM FILIAL")


def detect_sales_branch_from_query(query: str) -> str | None:
    normalized = f" {normalize_text(query)} "
    for code, name in SALES_BRANCHES.items():
        if normalize_text(name) in normalized:
            return code
        if f" filial {int(code)} " in normalized or f" filial {code} " in normalized:
            return code
    return None


def filter_sales_by_branch(rows: Iterable[Dict[str, Any]], branch_code: str) -> List[Dict[str, Any]]:
    normalized_code = sales_branch_code(branch_code)
    return [row for row in rows if sales_branch_code(row.get("filial")) == normalized_code]


def row_market(row: Dict[str, Any]) -> str:
    for field in ("MERCADO", "mercado", "Mercado"):
        if row.get(field) not in (None, ""):
            return normalize_text(row[field]).upper()
    return ""


def filter_sales_by_market(rows: Iterable[Dict[str, Any]], market: str) -> List[Dict[str, Any]]:
    market_normalized = normalize_text(market).upper()
    if market_normalized == "INTERNO":
        return [
            row for row in rows
            if row_market(row) == "INTERNO"
        ]
    if market_normalized == "EXTERNO":
        return [
            row for row in rows
            if row_market(row) == "EXTERNO"
        ]
    return list(rows)


def aggregate_sales_by_branch(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrega vendas por filial/empresa usando linhas de contrato, com valorTotal em USD."""
    unique: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        contract = str(row.get("contrato") or index).strip()
        branch = sales_branch_code(row.get("filial"))
        client = str(row.get("cliente") or "").strip()
        key = f"{contract}|{branch}|{client}"
        unique.setdefault(key, row)

    totals = defaultdict(lambda: {
        "contratos": 0,
        "sacas": Decimal("0"),
        "valor_usd": Decimal("0"),
        "clientes": set(),
    })

    for row in unique.values():
        code = sales_branch_code(row.get("filial"))
        item = totals[code]
        item["contratos"] += 1
        item["sacas"] += _decimal(row.get("sacas"))
        item["valor_usd"] += _decimal(row.get("valorTotal"))
        if row.get("cliente"):
            item["clientes"].add(str(row["cliente"]).strip())

    result = []
    for code, values in totals.items():
        result.append({
            "filial": code,
            "empresa": SALES_BRANCHES.get(code, f"FILIAL {code}" if code != "N/I" else "SEM FILIAL"),
            "contratos": values["contratos"],
            "sacas": float(values["sacas"]),
            "valor_usd": float(values["valor_usd"]),
            "clientes": len(values["clientes"]),
        })

    result.sort(key=lambda item: item["sacas"], reverse=True)
    return result


def aggregate_sales_totals(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega totais de vendas por contrato, com valorTotal em USD."""
    unique: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(rows):
        contract = str(row.get("contrato") or index).strip()
        branch = sales_branch_code(row.get("filial"))
        client = str(row.get("cliente") or "").strip()
        key = f"{contract}|{branch}|{client}"
        unique.setdefault(key, row)

    total_sacas = Decimal("0")
    total_value_usd = Decimal("0")
    clients = set()

    for row in unique.values():
        total_sacas += _decimal(row.get("sacas"))
        total_value_usd += _decimal(row.get("valorTotal"))
        if row.get("cliente"):
            clients.add(str(row["cliente"]).strip())

    return {
        "contratos": len(unique),
        "sacas": float(total_sacas),
        "valor_usd": float(total_value_usd),
        "clientes": len(clients),
    }


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
