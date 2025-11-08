from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple


@dataclass
class SalesRecord:
    store_name: str
    order_date: date
    cups: int
    total_cash: Decimal
    packages_kg: Decimal

    def as_dict(self) -> Dict[str, Any]:
        return {
            "store_name": self.store_name,
            "order_date": self.order_date.isoformat(),
            "cups": int(self.cups),
            "total_cash": float(self.total_cash),
            "packages_kg": float(self.packages_kg),
        }


def merge_sales_with_packages(
    sales_rows: Sequence[Dict[str, Any]],
    packages_rows: Sequence[Dict[str, Any]],
) -> List[SalesRecord]:
    package_lookup: MutableMapping[Tuple[str, date], Decimal] = defaultdict(Decimal)

    for row in packages_rows:
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = normalize_date(row.get("ORDER_DATE") or row.get("order_date"))
        packages = decode_decimal(row.get("PACKAGES_KG") or row.get("packages_kg"))

        if not store_name or not order_date:
            continue
        package_lookup[(store_name, order_date)] += packages

    merged: List[SalesRecord] = []
    for row in sales_rows:
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = normalize_date(row.get("ORDER_DATE") or row.get("order_date"))
        cups = int(row.get("ALLCUP") or row.get("allcup") or 0)
        total_cash = decode_decimal(row.get("TOTAL_CASH") or row.get("total_cash"))

        if not store_name or not order_date:
            continue

        packages = package_lookup.get((store_name, order_date), Decimal("0"))
        merged.append(
            SalesRecord(
                store_name=store_name,
                order_date=order_date,
                cups=cups,
                total_cash=total_cash,
                packages_kg=packages,
            )
        )

    merged.sort(key=lambda record: (record.store_name.lower(), record.order_date))
    return merged


def summarize_sales(records: Iterable[SalesRecord]) -> Dict[str, Any]:
    records_list = list(records)
    total_cups = sum(record.cups for record in records_list)
    total_cash = sum(record.total_cash for record in records_list)
    total_packages = sum(record.packages_kg for record in records_list)
    stores = {record.store_name for record in records_list}

    if records_list:
        start_date = min(record.order_date for record in records_list)
        end_date = max(record.order_date for record in records_list)
    else:
        start_date = end_date = None

    return {
        "stores_count": len(stores),
        "total_cups": total_cups,
        "total_cash": float(total_cash),
        "total_packages": float(total_packages),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }


def sort_records(records: Sequence[SalesRecord], sort_key: str) -> List[SalesRecord]:
    if sort_key == "store":
        return sorted(records, key=lambda record: (record.store_name.lower(), record.order_date))
    if sort_key == "sum":
        return sorted(records, key=lambda record: record.total_cash, reverse=True)
    if sort_key == "cups":
        return sorted(records, key=lambda record: record.cups, reverse=True)
    if sort_key == "packages":
        return sorted(records, key=lambda record: record.packages_kg, reverse=True)
    return sorted(records, key=lambda record: (record.order_date, record.store_name.lower()))


def decode_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    return Decimal(str(value).replace(",", "."))


def normalize_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Fallback to fromisoformat which handles microseconds, timezone (strip offset)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None

