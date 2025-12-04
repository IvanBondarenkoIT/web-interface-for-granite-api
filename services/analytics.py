from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple


@dataclass
class SalesRecord:
    store_name: str
    order_date: date
    cups: int  # для обратной совместимости
    mono_cup: int = 0
    blend_cup: int = 0
    caotina_cup: int = 0
    all_cup: int = 0
    total_cash: Decimal = Decimal("0")
    packages_kg: Decimal = Decimal("0")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "store_name": self.store_name,
            "order_date": self.order_date.isoformat(),
            "cups": int(self.cups),
            "mono_cup": int(self.mono_cup),
            "blend_cup": int(self.blend_cup),
            "caotina_cup": int(self.caotina_cup),
            "all_cup": int(self.all_cup),
            "total_cash": float(self.total_cash),
            "packages_kg": float(self.packages_kg),
        }


@dataclass
class PivotTable:
    dates: List[date]
    stores: List[str]
    data: Dict[date, Dict[str, SalesRecord]]
    daily_totals: Optional[Dict[date, SalesRecord]] = field(default=None)

    def formatted_dates(self) -> List[str]:
        return [d.isoformat() for d in self.dates]

    def get_daily_total(self, day: date) -> Optional[SalesRecord]:
        """Получить итоги за день."""
        if self.daily_totals:
            return self.daily_totals.get(day)
        return None


def merge_cups_sums_packages(
    cups_rows: Sequence[Dict[str, Any]],
    sums_rows: Sequence[Dict[str, Any]],
    packages_rows: Sequence[Dict[str, Any]],
) -> List[SalesRecord]:
    # Создаем lookup для сумм
    sums_lookup: MutableMapping[Tuple[str, date], Decimal] = defaultdict(Decimal)
    for row in sums_rows:
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = normalize_date(row.get("ORDER_DATE") or row.get("order_date"))
        total_cash = decode_decimal(row.get("TOTAL_CASH") or row.get("total_cash"))
        if store_name and order_date:
            sums_lookup[(store_name, order_date)] += total_cash

    # Создаем lookup для килограммов
    packages_lookup: MutableMapping[Tuple[str, date], Decimal] = defaultdict(Decimal)
    for row in packages_rows:
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = normalize_date(row.get("ORDER_DATE") or row.get("order_date"))
        packages = decode_decimal(row.get("PACKAGES_KG") or row.get("packages_kg"))
        if store_name and order_date:
            packages_lookup[(store_name, order_date)] += packages

    # Объединяем данные из чашек с суммами и килограммами
    merged: List[SalesRecord] = []
    for row in cups_rows:
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = normalize_date(row.get("ORDER_DATE") or row.get("order_date"))
        if not store_name or not order_date:
            continue

        # Новые поля для типов чашек
        mono_cup = int(row.get("MonoCup") or row.get("monoCup") or 0)
        blend_cup = int(row.get("BlendCup") or row.get("blendCup") or 0)
        caotina_cup = int(row.get("CaotinaCup") or row.get("caotinaCup") or 0)
        all_cup = int(row.get("AllCup") or row.get("allCup") or row.get("ALLCUP") or row.get("allcup") or 0)

        # Для обратной совместимости: если новые поля пустые, используем старое поле
        cups = all_cup if all_cup > 0 else int(row.get("ALLCUP") or row.get("allcup") or 0)

        # Получаем суммы и килограммы из lookup
        total_cash = sums_lookup.get((store_name, order_date), Decimal("0"))
        packages = packages_lookup.get((store_name, order_date), Decimal("0"))

        merged.append(
            SalesRecord(
                store_name=store_name,
                order_date=order_date,
                cups=cups,
                mono_cup=mono_cup,
                blend_cup=blend_cup,
                caotina_cup=caotina_cup,
                all_cup=all_cup if all_cup > 0 else cups,
                total_cash=total_cash,
                packages_kg=packages,
            )
        )

    merged.sort(key=lambda record: (record.store_name.lower(), record.order_date))
    return merged


# Функция для обратной совместимости со старым форматом
def merge_sales_with_packages(
    sales_rows: Sequence[Dict[str, Any]],
    packages_rows: Sequence[Dict[str, Any]],
) -> List[SalesRecord]:
    """
    Обратная совместимость: объединяет старый формат (sales + packages) в новый формат.
    Старый формат: sales_rows содержит ALLCUP и TOTAL_CASH вместе.
    """
    # В старом формате sales_rows может содержать и чашки, и суммы
    # Разделяем их на cups_rows и sums_rows
    cups_rows: List[Dict[str, Any]] = []
    sums_rows: List[Dict[str, Any]] = []

    for row in sales_rows:
        # Копируем базовые поля
        store_name = str(row.get("STORE_NAME") or row.get("store_name", "")).strip()
        order_date = row.get("ORDER_DATE") or row.get("order_date")

        # Если есть ALLCUP, это чашки
        if "ALLCUP" in row or "allcup" in row:
            cups_rows.append(row.copy())

        # Если есть TOTAL_CASH, это суммы
        if "TOTAL_CASH" in row or "total_cash" in row:
            sums_rows.append({
                "STORE_NAME": store_name,
                "ORDER_DATE": order_date,
                "TOTAL_CASH": row.get("TOTAL_CASH") or row.get("total_cash"),
            })

    # Если sales_rows содержит оба поля, разделяем
    # Иначе используем как есть
    if not cups_rows and not sums_rows:
        # Старый формат - используем sales_rows как есть и пытаемся извлечь данные
        cups_rows = list(sales_rows)

    return merge_cups_sums_packages(cups_rows, sums_rows, packages_rows)


def summarize_sales(records: Iterable[SalesRecord]) -> Dict[str, Any]:
    records_list = list(records)
    total_cups = sum(record.cups for record in records_list)
    total_mono_cup = sum(record.mono_cup for record in records_list)
    total_blend_cup = sum(record.blend_cup for record in records_list)
    total_caotina_cup = sum(record.caotina_cup for record in records_list)
    total_all_cup = sum(record.all_cup for record in records_list)
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
        "total_mono_cup": total_mono_cup,
        "total_blend_cup": total_blend_cup,
        "total_caotina_cup": total_caotina_cup,
        "total_all_cup": total_all_cup if total_all_cup > 0 else total_cups,
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


def calculate_daily_totals(
    records: Sequence[SalesRecord],
) -> Dict[date, SalesRecord]:
    """Рассчитать итоги по всем магазинам за каждый день."""
    daily_aggregated: Dict[date, Dict[str, Any]] = {}

    for record in records:
        day = record.order_date
        if day not in daily_aggregated:
            daily_aggregated[day] = {
                "mono_cup": 0,
                "blend_cup": 0,
                "caotina_cup": 0,
                "all_cup": 0,
                "cups": 0,
                "total_cash": Decimal("0"),
                "packages_kg": Decimal("0"),
            }

        daily_aggregated[day]["mono_cup"] += record.mono_cup
        daily_aggregated[day]["blend_cup"] += record.blend_cup
        daily_aggregated[day]["caotina_cup"] += record.caotina_cup
        daily_aggregated[day]["all_cup"] += record.all_cup if record.all_cup > 0 else record.cups
        daily_aggregated[day]["cups"] += record.cups
        daily_aggregated[day]["total_cash"] += record.total_cash
        daily_aggregated[day]["packages_kg"] += record.packages_kg

    daily_totals: Dict[date, SalesRecord] = {}
    for day, agg in daily_aggregated.items():
        daily_totals[day] = SalesRecord(
            store_name="Итого",
            order_date=day,
            cups=agg["cups"],
            mono_cup=agg["mono_cup"],
            blend_cup=agg["blend_cup"],
            caotina_cup=agg["caotina_cup"],
            all_cup=agg["all_cup"] if agg["all_cup"] > 0 else agg["cups"],
            total_cash=agg["total_cash"],
            packages_kg=agg["packages_kg"],
        )

    return daily_totals


def build_pivot_table(
    records: Sequence[SalesRecord],
    store_order: Optional[Sequence[str]] = None,
) -> PivotTable:
    unique_dates = sorted({record.order_date for record in records})
    store_set = {record.store_name for record in records}

    ordered_stores: List[str]
    if store_order:
        seen = set()
        ordered_stores = []
        for name in store_order:
            if name in store_set and name not in seen:
                ordered_stores.append(name)
                seen.add(name)
        for remainder in sorted(store_set):
            if remainder not in seen:
                ordered_stores.append(remainder)
    else:
        ordered_stores = sorted(store_set)

    table_data: Dict[date, Dict[str, SalesRecord]] = {
        day: {} for day in unique_dates
    }
    for record in records:
        table_data.setdefault(record.order_date, {})[record.store_name] = record

    # Рассчитываем итоги за день
    daily_totals = calculate_daily_totals(records)

    return PivotTable(dates=unique_dates, stores=ordered_stores, data=table_data, daily_totals=daily_totals)

