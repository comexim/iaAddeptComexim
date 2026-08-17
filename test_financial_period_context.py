from datetime import date

from app.services.financial_period_context import (
    build_financial_period_context,
    filter_financial_rows_by_calendar,
    resolve_business_day_range,
)


def test_next_seven_calendar_days_reports_missing_weekend():
    rows = [{"vencimento": f"202608{day:02d}"} for day in (17, 18, 19, 20, 21)]
    context = build_financial_period_context(
        "próximos 7 dias corridos", "20260817", "20260823", rows, date_field="vencimento"
    )
    assert "17/08/2026 a 23/08/2026 (dias corridos)" in context
    assert "sábado 22/08/2026" in context
    assert "domingo 23/08/2026" in context


def test_next_seven_business_days_expands_across_weekend():
    start, end = resolve_business_day_range(
        "próximos 7 dias úteis", "20260817", "20260823", today=date(2026, 8, 17)
    )
    assert (start, end) == ("20260817", "20260825")


def test_business_days_exclude_weekend_rows_and_explain_calendar():
    rows = [
        {"vencimento": "20260821"},
        {"vencimento": "20260822"},
        {"vencimento": "20260824"},
    ]
    filtered = filter_financial_rows_by_calendar(
        rows,
        date_field="vencimento",
        start="20260821",
        end="20260825",
        business_days=True,
    )
    assert [row["vencimento"] for row in filtered] == ["20260821", "20260824"]
    context = build_financial_period_context(
        "dias úteis", "20260821", "20260825", filtered, date_field="vencimento"
    )
    assert "Sábados e domingos não foram consultados" in context
    assert "terça-feira 25/08/2026" in context


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"financial_period_context: {len(tests)} tests OK")
