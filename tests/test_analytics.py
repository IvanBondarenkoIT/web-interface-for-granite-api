from datetime import date
from decimal import Decimal

from services.analytics import (
    SalesRecord,
    merge_sales_with_packages,
    normalize_date,
    summarize_sales,
)


def test_merge_sales_with_packages_handles_missing_packages():
    sales_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "ALLCUP": 10, "TOTAL_CASH": "15.50"},
        {"STORE_NAME": "Store B", "ORDER_DATE": "2024-05-01", "ALLCUP": 5, "TOTAL_CASH": "7.75"},
    ]
    packages_rows = [{"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "PACKAGES_KG": "2.5"}]

    records = merge_sales_with_packages(sales_rows, packages_rows)

    assert len(records) == 2
    record_a = next(record for record in records if record.store_name == "Store A")
    assert record_a.packages_kg == Decimal("2.5")
    record_b = next(record for record in records if record.store_name == "Store B")
    assert record_b.packages_kg == Decimal("0")


def test_summarize_sales_returns_totals():
    records = [
        SalesRecord("Store", date(2024, 1, 1), cups=10, total_cash=Decimal("20.00"), packages_kg=Decimal("1.2")),
        SalesRecord("Store", date(2024, 1, 2), cups=5, total_cash=Decimal("8.00"), packages_kg=Decimal("0.3")),
    ]

    summary = summarize_sales(records)

    assert summary["stores_count"] == 1
    assert summary["total_cups"] == 15
    assert summary["total_cash"] == 28.0
    assert summary["total_packages"] == 1.5
    assert summary["start_date"] == "2024-01-01"
    assert summary["end_date"] == "2024-01-02"


def test_normalize_date_understands_isoformat_with_time():
    normalized = normalize_date("2024-01-05T10:30:00")
    assert normalized == date(2024, 1, 5)

