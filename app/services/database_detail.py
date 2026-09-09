"""Listagens determinísticas formadas exclusivamente por linhas consultadas."""

from decimal import Decimal
import re
import unicodedata
from typing import Any, Dict, Iterable, Optional, Sequence


TRUSTED_DATABASE_DETAIL_PREFIX = "DETALHE_BANCO_CONFIRMADO:\n"


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def database_detail_request(query: str, explicit_limit: Optional[int] = None) -> Dict[str, Any]:
    """Detecta quando o usuário pediu registros individuais, não um resumo."""
    normalized = _normalize(query)
    asks_to_list = bool(re.search(
        r"\b(list[ea]?|listar|mostr[ea]|exib[ae]|detalh[ae]|quais?|relacione|traga)\b",
        normalized,
    ))
    mentions_rows = bool(re.search(
        r"\b(contratos?|pedidos?|titulos?|documentos?|pagamentos?|registros?|linhas?|"
        r"vendas?|compras?|contas?)\b",
        normalized,
    ))
    asks_for_grouping = bool(re.search(
        r"\b(por|agrupad[oa]s?|separad[oa]s?)\s+"
        r"(cliente|clientes|fornecedor|fornecedores|filial|filiais|qualidade|qualidades|moeda|moedas)\b",
        normalized,
    ))
    asks_for_entities = bool(re.search(
        r"\bquais?\s+(?:os\s+|as\s+)?(clientes|fornecedores|filiais|qualidades|moedas)\b",
        normalized,
    ))
    requested = explicit_limit is not None or (
        asks_to_list and mentions_rows and not asks_for_grouping and not asks_for_entities
    )

    limit = explicit_limit
    if requested and limit is None:
        match = re.search(
            r"\b(?:top\s*)?(\d{1,4})\s+(?:maiores?\s+)?"
            r"(?:contratos?|pedidos?|titulos?|documentos?|pagamentos?|registros?|linhas?|"
            r"vendas?|compras?|contas?)\b",
            normalized,
        )
        if match:
            limit = int(match.group(1))
    if requested and limit is None:
        limit = 50

    return {
        "requested": requested,
        "limit": limit,
        "largest_first": bool(re.search(r"\b(maiores?|mais\s+altos?|top)\b", normalized)),
    }


def _number(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace("R$", "").replace("US$", "").replace(" ", "")
    if "," in text and "." in text:
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except Exception:
        return Decimal("0")


def select_database_detail_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    limit: Optional[int],
    largest_first: bool,
) -> list[Dict[str, Any]]:
    """Seleciona referências aos próprios registros, sem fabricar ou fundir linhas."""
    selected = list(rows)
    if largest_first:
        value_fields = ("valor", "valorTotal", "saldo", "valorStr")

        def row_value(row: Dict[str, Any]) -> Decimal:
            return next(
                (_number(row.get(field)) for field in value_fields if row.get(field) not in (None, "")),
                Decimal("0"),
            )

        selected.sort(key=lambda row: abs(row_value(row)), reverse=True)
    if limit is not None and limit > 0:
        selected = selected[:limit]
    return selected


def _display_value(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value).strip()


def format_trusted_database_detail(
    rows: Iterable[Dict[str, Any]],
    *,
    source_name: str,
    query: str,
    explicit_limit: Optional[int] = None,
    preferred_fields: Sequence[str] = (),
) -> Optional[str]:
    """Formata uma linha de saída para cada linha selecionada da consulta."""
    source_rows = list(rows)
    request = database_detail_request(query, explicit_limit=explicit_limit)
    if not request["requested"]:
        return None

    selected = select_database_detail_rows(
        source_rows,
        limit=request["limit"],
        largest_first=request["largest_first"],
    )
    omitted = len(source_rows) - len(selected)
    lines = []
    for index, row in enumerate(selected, 1):
        ordered_fields = (
            [field for field in preferred_fields if field in row]
            if preferred_fields
            else list(row)
        )
        values = [
            f"{field}={_display_value(row.get(field))}"
            for field in ordered_fields
            if row.get(field) not in (None, "")
        ]
        lines.append(f"{index}. " + " | ".join(values))

    omitted_notice = (
        f"\nRegistros não exibidos: {omitted}." if omitted > 0 else "\nRegistros não exibidos: 0."
    )
    body = (
        f"Detalhes confirmados pelo banco ({source_name}):\n\n"
        f"Registros retornados após os filtros: {len(source_rows)}.\n"
        f"Registros exibidos: {len(selected)}."
        f"{omitted_notice}\n\n"
        "Cada linha abaixo corresponde a uma linha existente no resultado da consulta.\n\n"
        + ("\n".join(lines) if lines else "Nenhum registro para exibir.")
    )
    return TRUSTED_DATABASE_DETAIL_PREFIX + body
