from datetime import date
from decimal import Decimal

from services.analytics import (
    SalesRecord,
    build_pivot_table,
    merge_cups_sums_packages,
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
        SalesRecord("Store", date(2024, 1, 1), cups=10, mono_cup=4, blend_cup=5, caotina_cup=1, all_cup=10, total_cash=Decimal("20.00"), packages_kg=Decimal("1.2")),
        SalesRecord("Store", date(2024, 1, 2), cups=5, mono_cup=2, blend_cup=3, caotina_cup=0, all_cup=5, total_cash=Decimal("8.00"), packages_kg=Decimal("0.3")),
    ]

    summary = summarize_sales(records)

    assert summary["stores_count"] == 1
    assert summary["total_cups"] == 15
    assert summary["total_mono_cup"] == 6
    assert summary["total_blend_cup"] == 8
    assert summary["total_caotina_cup"] == 1
    assert summary["total_all_cup"] == 15
    assert summary["total_cash"] == 28.0
    assert summary["total_packages"] == 1.5
    assert summary["start_date"] == "2024-01-01"
    assert summary["end_date"] == "2024-01-02"


def test_normalize_date_understands_isoformat_with_time():
    normalized = normalize_date("2024-01-05T10:30:00")
    assert normalized == date(2024, 1, 5)


def test_build_pivot_table_orders_by_store_list():
    records = [
        SalesRecord("Store B", date(2024, 1, 1), cups=5, mono_cup=2, blend_cup=3, caotina_cup=0, all_cup=5, total_cash=Decimal("12"), packages_kg=Decimal("0.5")),
        SalesRecord("Store A", date(2024, 1, 1), cups=3, mono_cup=1, blend_cup=2, caotina_cup=0, all_cup=3, total_cash=Decimal("8"), packages_kg=Decimal("0.2")),
        SalesRecord("Store A", date(2024, 1, 2), cups=7, mono_cup=3, blend_cup=4, caotina_cup=0, all_cup=7, total_cash=Decimal("15"), packages_kg=Decimal("0.4")),
    ]

    pivot = build_pivot_table(records, store_order=["Store A", "Store C", "Store B"])

    assert pivot.stores == ["Store A", "Store B"]
    assert pivot.formatted_dates() == ["2024-01-01", "2024-01-02"]
    assert pivot.data[date(2024, 1, 1)]["Store A"].cups == 3
    assert pivot.data[date(2024, 1, 1)]["Store B"].cups == 5
    assert "Store B" not in pivot.data[date(2024, 1, 2)]


def test_merge_cups_sums_packages():
    """Test new function that merges three separate queries"""
    cups_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "MonoCup": 4, "BlendCup": 5, "CaotinaCup": 1, "AllCup": 10},
    ]
    sums_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "TOTAL_CASH": "15.50"},
    ]
    packages_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "PACKAGES_KG": "2.5"},
    ]

    records = merge_cups_sums_packages(cups_rows, sums_rows, packages_rows)

    assert len(records) == 1
    record = records[0]
    assert record.store_name == "Store A"
    assert record.mono_cup == 4
    assert record.blend_cup == 5
    assert record.caotina_cup == 1
    assert record.all_cup == 10
    assert record.cups == 10
    assert record.total_cash == Decimal("15.50")
    assert record.packages_kg == Decimal("2.5")


def test_merge_sales_backward_compatibility():
    """Test backward compatibility with old format"""
    sales_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "ALLCUP": 10, "TOTAL_CASH": "15.50"},
    ]
    packages_rows = [
        {"STORE_NAME": "Store A", "ORDER_DATE": "2024-05-01", "PACKAGES_KG": "2.5"},
    ]

    records = merge_sales_with_packages(sales_rows, packages_rows)

    assert len(records) == 1
    record = records[0]
    assert record.cups == 10
    assert record.all_cup == 10
    assert record.total_cash == Decimal("15.50")
    assert record.packages_kg == Decimal("2.5")

