import io
import logging

from app.services.query_trace import (
    log_database_execution,
    log_query_processing,
    reset_query_trace,
    start_query_trace,
)


def test_trace_contains_context_and_masks_sensitive_parameters():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    trace_logger = logging.getLogger("app.query_trace")
    previous_level = trace_logger.level
    trace_logger.setLevel(logging.INFO)
    trace_logger.addHandler(handler)
    token = start_query_trace("message-123", "dev")
    try:
        log_database_execution(
            source_kind="procedure",
            source_name="usp_Teste",
            parameters={"DataIni": "20260817", "password": "segredo"},
            record_count=4,
            executed_at="2026-08-17T12:00:00+00:00",
            duration_ms=10.5,
        )
        log_query_processing(
            source_name="usp_Teste",
            original_count=4,
            final_count=3,
            post_filters={"filial": "05"},
            calculated_totals={"valor": 100},
            status_criterion="aberto",
            unit="títulos",
            currency="BRL",
        )
    finally:
        reset_query_trace(token)
        trace_logger.removeHandler(handler)
        trace_logger.setLevel(previous_level)

    output = stream.getvalue()
    assert '"message_id": "message-123"' in output
    assert '"environment": "dev"' in output
    assert '"source_name": "usp_Teste"' in output
    assert '"record_count": 4' in output
    assert '"password": "***"' in output
    assert "segredo" not in output
    assert '"post_filters": {"filial": "05"}' in output
    assert '"calculated_totals": {"valor": 100}' in output


if __name__ == "__main__":
    test_trace_contains_context_and_masks_sensitive_parameters()
    print("query_trace: 1 test OK")
