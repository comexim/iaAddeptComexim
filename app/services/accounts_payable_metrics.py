"""Reconciliação e seleção determinística de contas a pagar."""

from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple


TRUSTED_PAYABLE_DETAIL_PREFIX = "DETALHE_CONTAS_A_PAGAR_CONFIRMADO:\n"


def payable_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def payable_title_key(row: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Retorna identidade somente quando o banco fornece um idProtheus confiável."""
    protheus_id = ""
    for field, value in row.items():
        if str(field).replace("_", "").lower() == "idprotheus" and value not in (None, ""):
            protheus_id = str(value).strip().upper()
            break
    return ("idProtheus", protheus_id) if protheus_id else None


def deduplicate_payables(
    rows: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    unique: List[Dict[str, Any]] = []
    seen = set()
    duplicate_count = 0
    for row in rows:
        key = payable_title_key(row)
        # Sem idProtheus não existe evidência determinística de duplicidade.
        # Números, parcelas, fornecedores e valores iguais podem ser títulos
        # legítimos distintos, portanto essas linhas devem ser preservadas.
        if key is not None and key in seen:
            duplicate_count += 1
            continue
        if key is not None:
            seen.add(key)
        unique.append(row)
    return unique, duplicate_count


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def payable_detail_request(query: str, explicit_limit: Optional[int] = None) -> Dict[str, Any]:
    """Identifica pedidos de linhas de títulos que exigem resposta literal da tool."""
    normalized = _normalize_text(query)
    mentions_detail = bool(re.search(r"\b(titulos?|documentos?|linhas?|detalhes?)\b", normalized))
    asks_to_list = bool(re.search(r"\b(list[ea]?|listar|mostr[ea]|exib[ae]|detalh[ae]|quais?)\b", normalized))
    largest_first = bool(re.search(r"\b(maiores?|mais\s+altos?|top)\b", normalized))
    requested = explicit_limit is not None or (mentions_detail and (asks_to_list or largest_first))

    limit = explicit_limit if explicit_limit is not None else None
    if limit is None and requested:
        match = re.search(
            r"\b(?:list[ea]?|mostr[ea]|exib[ae]|top)?\s*(\d{1,3})\s+"
            r"(?:maiores?\s+)?(?:titulos?|documentos?|linhas?|contas?)\b",
            normalized,
        )
        if match:
            limit = int(match.group(1))

    if requested and limit is None:
        limit = 50

    return {
        "requested": requested,
        "largest_first": largest_first,
        "limit": limit,
    }


def select_payable_details(
    rows: Iterable[Dict[str, Any]],
    *,
    limit: Optional[int],
    largest_first: bool,
) -> List[Dict[str, Any]]:
    """Seleciona linhas existentes sem criar, fundir ou redistribuir valores."""
    selected = list(rows)
    if largest_first:
        selected = [row for row in selected if payable_decimal(row.get("valor")) != 0]
        selected.sort(key=lambda row: abs(payable_decimal(row.get("valor"))), reverse=True)
    if limit is not None and limit > 0:
        selected = selected[:limit]
    return selected


def reconcile_payables(
    detail_rows: Iterable[Dict[str, Any]],
    *,
    aggregate_total: Any,
    declared_count: int,
    tolerance: Decimal = Decimal("0.01"),
    partial: bool = False,
    complete_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Compara o total declarado com o mesmo conjunto completo de títulos."""
    details = list(detail_rows)
    detail_sum = sum((payable_decimal(row.get("valor")) for row in details), Decimal("0"))
    total = payable_decimal(aggregate_total)
    difference = detail_sum - total
    violations = []

    if partial:
        return {
            "valido": True,
            "parcial": True,
            "total": total,
            "soma_detalhes": detail_sum,
            "diferenca": difference,
            "quantidade_declarada": declared_count,
            "quantidade_detalhada": len(details),
            "quantidade_completa": complete_count,
            "violacoes": [],
        }

    if abs(difference) > tolerance:
        violations.append("soma_detalhes")
    if len(details) != declared_count:
        violations.append("quantidade_titulos")
    for index, row in enumerate(details):
        if payable_decimal(row.get("valor")) - total > tolerance:
            violations.append(f"titulo_maior_total:{index + 1}")

    return {
        "valido": not violations,
        "parcial": False,
        "total": total,
        "soma_detalhes": detail_sum,
        "diferenca": difference,
        "quantidade_declarada": declared_count,
        "quantidade_detalhada": len(details),
        "quantidade_completa": complete_count or len(details),
        "violacoes": violations,
    }
