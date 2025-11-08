from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from flask import Flask, flash, redirect, render_template, request, url_for

from config import settings
from proxy_client import ProxyAPIClient, ProxyAPIError
from services.analytics import merge_sales_with_packages, sort_records, summarize_sales


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

                raw_sales = client.get_sales(store_ids, default_start, default_end)
                merged = merge_sales_with_packages(raw_sales["sales"], raw_sales["packages"])
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

        if load_requested:
            try:
                stores = client.get_stores()
                store_ids = selected_store_ids or [store["ID"] for store in stores]
                raw_sales = client.get_sales(store_ids, start_date, end_date)
                merged = merge_sales_with_packages(raw_sales["sales"], raw_sales["packages"])
                sorted_records = sort_records(merged, sort_key)
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


app = create_app()

