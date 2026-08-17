from datetime import date

from app.services.financial_position_scope import (
    CURRENT_OPEN_PAST_NOTICE,
    append_scope_notice,
    build_receivables_current_open_query,
    compact_financial_date,
    current_open_scope_notice,
    is_past_financial_period,
)


TODAY = date(2026, 8, 17)


def test_previous_day_requires_current_open_notice():
    assert is_past_financial_period("20260816", "20260816", today=TODAY)
    assert current_open_scope_notice("20260816", "20260816", today=TODAY) == CURRENT_OPEN_PAST_NOTICE


def test_period_that_starts_in_past_requires_notice():
    assert is_past_financial_period("20260801", "20260831", today=TODAY)


def test_future_period_does_not_require_notice():
    assert not is_past_financial_period("20260818", "20260831", today=TODAY)
    assert current_open_scope_notice("20260818", "20260831", today=TODAY) == ""


def test_month_format_is_supported():
    assert is_past_financial_period("202607", "202607", today=TODAY)


def test_notice_does_not_change_original_values_and_is_not_duplicated():
    original = "Total: R$ 123,45 | 1 título"
    formatted = append_scope_notice(original, CURRENT_OPEN_PAST_NOTICE)
    assert original in formatted
    assert formatted.count(CURRENT_OPEN_PAST_NOTICE) == 1
    assert append_scope_notice(formatted, CURRENT_OPEN_PAST_NOTICE) == formatted


def test_receivables_today_uses_accumulated_current_open_source_and_type():
    filters, local_start, local_end = build_receivables_current_open_query(
        "20260817", "20260817", today=TODAY
    )
    assert filters == {
        "data_inicio": "19990101",
        "data_fim": "20260817",
        "tipo": "Receber",
    }
    assert (local_start, local_end) == ("20260817", "20260817")


def test_future_receivables_keep_requested_range_and_type():
    filters, local_start, local_end = build_receivables_current_open_query(
        "20260818", "20260820", today=TODAY
    )
    assert filters["data_inicio"] == "20260818"
    assert filters["data_fim"] == "20260820"
    assert filters["tipo"] == "Receber"
    assert local_start is None and local_end is None


def test_financial_date_normalizes_iso_value():
    assert compact_financial_date("2026-08-17T00:00:00") == "20260817"


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"financial_position_scope: {len(tests)} tests OK")
