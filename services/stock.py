"""Сервис для обработки данных об остатках товаров."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class StockRecord:
    """Запись об остатке товара."""

    group_name: str
    group_id: int
    good_id: int
    good_name: str
    quantity: Decimal
    price: Decimal
    total_sum: Decimal

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StockRecord":
        """Создать StockRecord из словаря API ответа."""
        return cls(
            group_name=str(data.get("GROUP_NAME", "")),
            group_id=int(data.get("GROUP_ID", 0)),
            good_id=int(data.get("GOOD_ID", 0)),
            good_name=str(data.get("GOOD_NAME", "")),
            quantity=Decimal(str(data.get("QUANTITY", 0))),
            price=Decimal(str(data.get("PRICE", 0))),
            total_sum=Decimal(str(data.get("TOTAL_SUM", 0))),
        )


@dataclass
class StockSummary:
    """Итоговая информация по остаткам."""

    total_items: int
    total_quantity: Decimal
    total_sum: Decimal
    groups_count: int


def parse_stock_data(stock_rows: List[Dict[str, Any]]) -> List[StockRecord]:
    """
    Преобразовать сырые данные API в список StockRecord.

    Args:
        stock_rows: Список словарей из API ответа.

    Returns:
        Список StockRecord объектов.
    """
    return [StockRecord.from_dict(row) for row in stock_rows]


def filter_stock_by_groups(
    stock_records: List[StockRecord], group_ids: Optional[Sequence[int]] = None
) -> List[StockRecord]:
    """
    Отфильтровать остатки по группам товаров.

    Args:
        stock_records: Список записей об остатках.
        group_ids: Список ID групп для фильтрации. Если None, возвращаются все записи.

    Returns:
        Отфильтрованный список записей.
    """
    if not group_ids:
        return stock_records
    group_ids_set = set(group_ids)
    return [record for record in stock_records if record.group_id in group_ids_set]


def search_stock(
    stock_records: List[StockRecord], search_query: Optional[str] = None
) -> List[StockRecord]:
    """
    Поиск по остаткам (по названию группы или товара).

    Args:
        stock_records: Список записей об остатках.
        search_query: Поисковый запрос. Если None или пустой, возвращаются все записи.

    Returns:
        Отфильтрованный список записей.
    """
    if not search_query or not search_query.strip():
        return stock_records

    query_lower = search_query.lower().strip()
    return [
        record
        for record in stock_records
        if query_lower in record.group_name.lower() or query_lower in record.good_name.lower()
    ]


def get_unique_groups(stock_records: List[StockRecord]) -> List[Dict[str, Any]]:
    """
    Получить список уникальных групп товаров из остатков.

    Args:
        stock_records: Список записей об остатках.

    Returns:
        Список словарей с ID и названием групп, отсортированный по названию.
    """
    groups_dict: Dict[int, str] = {}
    for record in stock_records:
        if record.group_id not in groups_dict:
            groups_dict[record.group_id] = record.group_name

    groups = [{"id": gid, "name": name} for gid, name in groups_dict.items()]
    return sorted(groups, key=lambda g: g["name"])


def calculate_stock_summary(stock_records: List[StockRecord]) -> StockSummary:
    """
    Рассчитать итоговую информацию по остаткам.

    Args:
        stock_records: Список записей об остатках.

    Returns:
        StockSummary с итоговыми данными.
    """
    if not stock_records:
        return StockSummary(
            total_items=0,
            total_quantity=Decimal("0"),
            total_sum=Decimal("0"),
            groups_count=0,
        )

    total_quantity = sum(record.quantity for record in stock_records)
    total_sum = sum(record.total_sum for record in stock_records)
    unique_groups = len(set(record.group_id for record in stock_records))

    return StockSummary(
        total_items=len(stock_records),
        total_quantity=total_quantity,
        total_sum=total_sum,
        groups_count=unique_groups,
    )


def paginate_stock(
    stock_records: List[StockRecord], page: int = 1, per_page: int = 50
) -> tuple[List[StockRecord], int]:
    """
    Разбить список остатков на страницы.

    Args:
        stock_records: Список записей об остатках.
        page: Номер страницы (начиная с 1).
        per_page: Количество записей на странице.

    Returns:
        Кортеж (записи для текущей страницы, общее количество страниц).
    """
    if not stock_records:
        return [], 0

    total_pages = (len(stock_records) + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    return stock_records[start_idx:end_idx], total_pages

