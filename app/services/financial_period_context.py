"""Períodos e cobertura diária determinísticos para consultas financeiras."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping, Optional

from app.services.financial_position_scope import compact_financial_date


WEEKDAYS_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _plain(text: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def uses_business_days(expression: object) -> bool:
    text = _plain(expression)
    return "dia util" in text or "dias uteis" in text


def _as_date(value: str) -> date:
    return datetime.strptime(compact_financial_date(value), "%Y%m%d").date()


def resolve_business_day_range(
    expression: object,
    start: str,
    end: str,
    *,
    today: datetime | date,
) -> tuple[str, str]:
    """Expande 'próximos/últimos N dias úteis' para seus limites reais."""
    text = _plain(expression)
    match = re.search(r"\b(proximos?|ultimos?)\s+(\d+)\s+dias?\s+uteis\b", text)
    if not match:
        return start, end

    direction, amount_text = match.groups()
    amount = max(1, int(amount_text))
    current = today.date() if isinstance(today, datetime) else today
    step = 1 if direction.startswith("proxim") else -1
    selected: list[date] = []
    cursor = current
    while len(selected) < amount:
        if cursor.weekday() < 5:
            selected.append(cursor)
        cursor += timedelta(days=step)
    return min(selected).strftime("%Y%m%d"), max(selected).strftime("%Y%m%d")


def consulted_dates(start: str, end: str, *, business_days: bool) -> list[date]:
    first, last = _as_date(start), _as_date(end)
    days: list[date] = []
    cursor = first
    while cursor <= last:
        if not business_days or cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def filter_financial_rows_by_calendar(
    rows: Iterable[Mapping[str, Any]],
    *,
    date_field: str,
    start: str,
    end: str,
    business_days: bool,
) -> list[Mapping[str, Any]]:
    allowed = {day.strftime("%Y%m%d") for day in consulted_dates(start, end, business_days=business_days)}
    return [row for row in rows if compact_financial_date(row.get(date_field)) in allowed]


def build_financial_period_context(
    expression: object,
    start: Optional[str],
    end: Optional[str],
    rows: Iterable[Mapping[str, Any]],
    *,
    date_field: str,
) -> str:
    """Descreve intervalo, calendário e todos os dias sem registros."""
    if not start or not end:
        return ""
    text = _plain(expression)
    if not any(token in text for token in ("semana", " dia", "dias")):
        return ""
    business_days = uses_business_days(expression)
    days = consulted_dates(start, end, business_days=business_days)
    dates_with_rows = {
        compact_financial_date(row.get(date_field))
        for row in rows
        if compact_financial_date(row.get(date_field))
    }
    missing = [day for day in days if day.strftime("%Y%m%d") not in dates_with_rows]
    first, last = _as_date(start), _as_date(end)
    calendar_label = "dias úteis" if business_days else "dias corridos"
    weekend_label = (
        "Sábados e domingos não foram consultados."
        if business_days
        else "Sábados e domingos foram incluídos quando existentes no intervalo."
    )
    if missing:
        missing_text = ", ".join(
            f"{WEEKDAYS_PT[day.weekday()]} {day.strftime('%d/%m/%Y')}"
            for day in missing
        )
        movement = f"Dias consultados sem registros: {missing_text}."
    else:
        movement = "Todos os dias consultados possuem registros."
    return (
        f"Período considerado: {first.strftime('%d/%m/%Y')} a {last.strftime('%d/%m/%Y')} "
        f"({calendar_label}). {weekend_label} {movement}"
    )


def append_period_context(text: str, context: str) -> str:
    if not context or context in text:
        return text
    return f"{text.rstrip()}\n\n📅 {context}"
