"""Classificação determinística do escopo temporal de consultas financeiras."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Optional, Union


CURRENT_OPEN_PAST_NOTICE = (
    "Esta consulta considera apenas os títulos que permanecem em aberto atualmente. "
    "Títulos que existiam na data consultada, mas já foram pagos ou baixados, não estão incluídos. "
    "Portanto, o resultado representa a posição atual filtrada pela data informada, e não uma posição histórica completa."
)


def _parse_compact_date(value: Optional[str], *, end: bool = False) -> Optional[date]:
    text = "".join(character for character in str(value or "") if character.isdigit())
    try:
        if len(text) == 8:
            return datetime.strptime(text, "%Y%m%d").date()
        if len(text) == 6:
            year, month = int(text[:4]), int(text[4:])
            day = monthrange(year, month)[1] if end else 1
            return date(year, month, day)
    except (TypeError, ValueError):
        return None
    return None


def is_past_financial_period(
    start: Optional[str],
    end: Optional[str] = None,
    *,
    today: Optional[Union[date, datetime]] = None,
) -> bool:
    """Retorna True quando ao menos parte do período consultado antecede hoje."""
    current = today or date.today()
    if isinstance(current, datetime):
        current = current.date()
    start_date = _parse_compact_date(start)
    end_date = _parse_compact_date(end or start, end=True)
    return bool((start_date and start_date < current) or (end_date and end_date < current))


def current_open_scope_notice(
    start: Optional[str],
    end: Optional[str] = None,
    *,
    today: Optional[Union[date, datetime]] = None,
) -> str:
    """Gera o aviso obrigatório apenas para consultas de datas passadas."""
    if is_past_financial_period(start, end, today=today):
        return CURRENT_OPEN_PAST_NOTICE
    return ""


def append_scope_notice(text: str, notice: str) -> str:
    """Anexa o aviso sem modificar números ou o conteúdo original da consulta."""
    if not notice or notice in text:
        return text
    return f"{text.rstrip()}\n\n⚠️ Escopo da consulta: {notice}"

