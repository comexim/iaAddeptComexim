"""Reconciliação determinística de contas a pagar."""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
