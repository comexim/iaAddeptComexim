"""Rastreabilidade estruturada e segura das consultas realizadas pelo Aron."""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from app import __version__


logger = logging.getLogger("app.query_trace")
SENSITIVE_TERMS = ("password", "senha", "token", "secret", "credential", "api_key")


@dataclass(frozen=True)
class QueryTraceContext:
    message_id: str
    environment: str
    app_version: str
    started_at: str


_context: ContextVar[Optional[QueryTraceContext]] = ContextVar("query_trace_context", default=None)


def start_query_trace(message_id: Optional[str], environment: Optional[str] = None) -> Token:
    context = QueryTraceContext(
        message_id=str(message_id or f"internal-{uuid.uuid4()}"),
        environment=str(environment or os.getenv("APP_ENV") or "unknown"),
        app_version=__version__,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    return _context.set(context)


def reset_query_trace(token: Token) -> None:
    _context.reset(token)


def current_query_trace() -> QueryTraceContext:
    context = _context.get()
    if context is None:
        start_query_trace(None)
        context = _context.get()
    return context


def _safe(value: Any, key: str = "") -> Any:
    if any(term in key.lower() for term in SENSITIVE_TERMS):
        return "***"
    if isinstance(value, Mapping):
        return {str(k): _safe(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def log_database_execution(
    *,
    source_kind: str,
    source_name: str,
    parameters: Optional[Mapping[str, Any]],
    record_count: int,
    executed_at: str,
    duration_ms: float,
) -> None:
    event = {
        "event": "database_execution",
        **asdict(current_query_trace()),
        "source_kind": source_kind,
        "source_name": source_name,
        "parameters": _safe(parameters or {}),
        "executed_at": executed_at,
        "duration_ms": round(duration_ms, 2),
        "record_count": int(record_count),
    }
    logger.info("[QUERY_TRACE] %s", json.dumps(event, ensure_ascii=False, sort_keys=True))


def log_query_processing(
    *,
    source_name: str,
    original_count: int,
    final_count: int,
    post_filters: Optional[Mapping[str, Any]] = None,
    calculated_totals: Optional[Mapping[str, Any]] = None,
    status_criterion: Optional[str] = None,
    unit: Optional[str] = None,
    currency: Optional[str] = None,
) -> None:
    event = {
        "event": "query_processing",
        **asdict(current_query_trace()),
        "source_name": source_name,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "original_count": int(original_count),
        "final_count": int(final_count),
        "post_filters": _safe(post_filters or {}),
        "calculated_totals": _safe(calculated_totals or {}),
        "status_criterion": status_criterion,
        "unit": unit,
        "currency": currency,
    }
    logger.info("[QUERY_TRACE] %s", json.dumps(event, ensure_ascii=False, sort_keys=True))


def friendly_update_metadata(record_count: int, *, unit: str = "registros", currency: str = "") -> str:
    now = datetime.now().astimezone()
    currency_text = f" Moeda: {currency}." if currency else ""
    return (
        f"Dados atualizados às {now.strftime('%H:%M:%S')} de {now.strftime('%d/%m/%Y')}. "
        f"Foram analisados {record_count} {unit}.{currency_text}"
    )

