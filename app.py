from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from flask import Flask, flash, redirect, render_template, request, url_for

from config import settings
from proxy_client import ProxyAPIClient, ProxyAPIError
from services.analytics import (
    build_pivot_table,
    merge_cups_sums_packages,
    merge_sales_with_packages,
    sort_records,
    summarize_sales,
)
from services.stock import (
    calculate_stock_summary,
    filter_stock_by_groups,
    get_unique_groups,
    paginate_stock,
    parse_stock_data,
    search_stock,
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key

    client = ProxyAPIClient(settings)

    @app.route("/")
    def dashboard() -> str:
        default_start, default_end = _default_range()
        load_requested = request.args.get("load") == "1"

        stores: List[Dict[str, Any]] = []
        merged = []
        api_health: Dict[str, Any] = {"status": "not loaded"}

        if load_requested:
            try:
                stores = client.get_stores()
                store_ids = [store["ID"] for store in stores]
                api_health = client.health()

                raw_data = client.get_sales(store_ids, default_start, default_end)
                merged = merge_cups_sums_packages(
                    raw_data["cups"],
                    raw_data["sums"],
                    raw_data["packages"],
                )
            except ProxyAPIError as exc:
                flash(f"Не удалось получить данные от Proxy API: {exc}", category="danger")
                api_health = {"status": "error", "message": str(exc)}

        summary = summarize_sales(merged)
        preview = merged[:10]

        return render_template(
            "dashboard.html",
            summary=summary,
            preview=preview,
            stores=stores,
            filters={
                "start_date": default_start,
                "end_date": default_end,
                "store_ids": [],
                "sort": "date",
            },
            health=api_health,
            loaded=load_requested,
        )

    @app.route("/sales")
    def sales() -> str:
        default_start, default_end = _default_range()
        start_date = request.args.get("start_date") or default_start
        end_date = request.args.get("end_date") or default_end
        sort_key = request.args.get("sort", "date")
        selected_store_ids = _parse_store_ids(request.args.getlist("store"))
        load_requested = request.args.get("load") == "1"

        stores: List[Dict[str, Any]] = []
        sorted_records = []
        pivot_table = None

        if load_requested:
            try:
                stores = client.get_stores()
                store_ids = selected_store_ids or [store["ID"] for store in stores]
                raw_data = client.get_sales(store_ids, start_date, end_date)
                merged = merge_cups_sums_packages(
                    raw_data["cups"],
                    raw_data["sums"],
                    raw_data["packages"],
                )
                sorted_records = sort_records(merged, sort_key)
                pivot_table = build_pivot_table(
                    sorted_records,
                    store_order=[store["NAME"] for store in stores],
                )
            except ProxyAPIError as exc:
                flash(f"Ошибка при запросе продаж: {exc}", "danger")
        else:
            # Attempt to load store list separately; ignore failures to keep page responsive
            try:
                stores = client.get_stores()
            except ProxyAPIError:
                stores = []

        summary = summarize_sales(sorted_records)

        return render_template(
            "sales_table.html",
            records=sorted_records,
            summary=summary,
            stores=stores,
            filters={
                "start_date": start_date,
                "end_date": end_date,
                "store_ids": selected_store_ids,
                "sort": sort_key,
            },
            loaded=load_requested,
            pivot=pivot_table,
        )

    @app.route("/stock")
    def stock() -> str:
        """Страница остатков товаров."""
        load_requested = request.args.get("load") == "1"
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
        search_query = request.args.get("search", "").strip()
        selected_group_ids = _parse_group_ids(request.args.getlist("group"))

        groups: List[Dict[str, Any]] = []
        summary = None
        summary_dict = None
        paginated_records_dict = []
        total_pages = 0

        if load_requested:
            try:
                # Получаем остатки с фильтрацией по группам на уровне SQL
                raw_stock = client.get_stock(group_ids=selected_group_ids if selected_group_ids else None)
                stock_records_list = parse_stock_data(raw_stock)

                # Получаем список уникальных групп для фильтра
                groups = get_unique_groups(stock_records_list)

                # Поиск на уровне приложения (клиентская фильтрация)
                if search_query:
                    stock_records_list = search_stock(stock_records_list, search_query)

                # Пагинация
                paginated_records, total_pages = paginate_stock(stock_records_list, page, per_page)

                # Преобразуем StockRecord в словари для шаблона (Decimal -> float)
                paginated_records_dict = [
                    {
                        "group_name": r.group_name,
                        "group_id": r.group_id,
                        "good_id": r.good_id,
                        "good_name": r.good_name,
                        "quantity": float(r.quantity),
                        "price": float(r.price),
                        "total_sum": float(r.total_sum),
                    }
                    for r in paginated_records
                ]

                # Итоговая информация (по всем записям, не только текущей странице)
                summary = calculate_stock_summary(stock_records_list)

                # Преобразуем Decimal в float для шаблона
                summary_dict = {
                    "total_items": summary.total_items,
                    "total_quantity": float(summary.total_quantity),
                    "total_sum": float(summary.total_sum),
                    "groups_count": summary.groups_count,
                }
            except ProxyAPIError as exc:
                flash(f"Ошибка при загрузке остатков: {exc}", "danger")
                summary_dict = None
        else:
            # Пытаемся загрузить список групп для фильтра (без загрузки всех остатков)
            try:
                # Получаем все остатки только для списка групп (можно оптимизировать отдельным запросом)
                raw_stock = client.get_stock()
                stock_records_list = parse_stock_data(raw_stock)
                groups = get_unique_groups(stock_records_list)
            except ProxyAPIError:
                groups = []
            summary_dict = None

        return render_template(
            "stock_table.html",
            stock_records=paginated_records_dict,
            summary=summary_dict,
            groups=groups,
            filters={
                "group_ids": selected_group_ids,
                "search": search_query,
                "page": page,
                "per_page": per_page,
            },
            loaded=load_requested,
            total_pages=total_pages,
        )

    @app.errorhandler(404)
    def page_not_found(_: Exception) -> str:
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_: Exception) -> str:
        return render_template("500.html"), 500

    return app


def _default_range() -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    start_of_month = today.replace(day=1)
    return start_of_month.isoformat(), today.isoformat()


def _parse_store_ids(store_values: Sequence[str]) -> List[int]:
    store_ids: List[int] = []
    for value in store_values:
        try:
            store_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return store_ids


def _parse_group_ids(group_values: Sequence[str]) -> List[int]:
    """Парсинг ID групп из параметров запроса."""
    group_ids: List[int] = []
    for value in group_values:
        try:
            group_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return group_ids


app = create_app()

