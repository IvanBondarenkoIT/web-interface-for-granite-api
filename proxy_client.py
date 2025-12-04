from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Settings, settings

logger = logging.getLogger(__name__)


class ProxyAPIError(RuntimeError):
    """Base exception raised for proxy API failures."""


class ProxyAPIAuthError(ProxyAPIError):
    """Raised when authentication fails for all provided tokens."""


class ProxyAPIClient:
    # ID групп для чашек
    MONO_CUP_GROUPS = ["24435", "25539", "21671", "25546", "25775", "25777", "25789"]
    BLEND_CUP_GROUPS = ["23076", "21882", "25767", "248882", "25788"]
    CAOTINA_CUP_GROUPS = ["24491", "21385"]
    ALL_CUP_GROUPS = MONO_CUP_GROUPS + BLEND_CUP_GROUPS + CAOTINA_CUP_GROUPS

    # ID групп для килограммов (БЕЗ Caotina!)
    PACKAGES_KG_GROUPS = ["11077", "16279", "16276"]  # Blend (2) + Mono (1)

    STORES_QUERY = "SELECT ID, NAME FROM STORGRP ORDER BY NAME"

    # Запрос 1: Чашки (с JOIN для подсчета товаров по типам)
    CUPS_QUERY_TEMPLATE = """
SELECT 
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    COALESCE(SUM(CASE WHEN G.OWNER IN ({mono_placeholders}) THEN GD.Source ELSE NULL END), 0) AS MonoCup,
    COALESCE(SUM(CASE WHEN G.OWNER IN ({blend_placeholders}) THEN GD.Source ELSE NULL END), 0) AS BlendCup,
    COALESCE(SUM(CASE WHEN G.OWNER IN ({caotina_placeholders}) THEN GD.Source ELSE NULL END), 0) AS CaotinaCup,
    COALESCE(SUM(CASE WHEN G.OWNER IN ({all_placeholders}) THEN GD.Source ELSE NULL END), 0) AS AllCup
FROM STORZAKAZDT D
JOIN STORZDTGDS GD ON D.ID = GD.SZID
JOIN GOODS G ON GD.GODSId = G.ID
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN ({store_placeholders})
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND NOT (
      D.comment LIKE '%мы;%' OR
      D.comment LIKE '%Мы;%' OR
      D.comment LIKE '%Тестирование%')
GROUP BY stgp.NAME, D.DAT_
ORDER BY stgp.NAME, D.DAT_
""".strip()

    # Запрос 2: Суммы (БЕЗ JOIN - чтобы избежать дублирования)
    SUMS_QUERY_TEMPLATE = """
SELECT
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(D.SUMMA) AS TOTAL_CASH
FROM STORZAKAZDT D
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN ({store_placeholders})
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND NOT (
      D.comment LIKE '%мы;%' OR
      D.comment LIKE '%Мы;%' OR
      D.comment LIKE '%Тестирование%')
GROUP BY stgp.NAME, D.DAT_
ORDER BY stgp.NAME, D.DAT_
""".strip()

    # Запрос 3: Килограммы (с фильтром по ID групп, БЕЗ Caotina, БЕЗ фильтра по комментариям)
    PACKAGES_QUERY_TEMPLATE = """
SELECT
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(GD.SOURCE) AS PACKAGES_KG
FROM STORZAKAZDT D
JOIN STORZDTGDS GD ON D.ID = GD.SZID
JOIN GOODS G ON GD.GODSId = G.ID
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN ({store_placeholders})
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND G.OWNER IN ({packages_placeholders})
GROUP BY stgp.NAME, D.DAT_
ORDER BY stgp.NAME, D.DAT_
""".strip()

    def __init__(self, settings_obj: Settings | None = None) -> None:
        self._settings = settings_obj or settings
        self.base_url = self._settings.proxy_api_url.rstrip("/")
        self.tokens = [self._settings.proxy_primary_token]
        if self._settings.proxy_fallback_token:
            self.tokens.append(self._settings.proxy_fallback_token)

        self.session = requests.Session()
        retry_strategy = Retry(
            total=1,
            connect=1,
            read=1,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.timeout = self._settings.proxy_timeout

    def health(self) -> Dict[str, Any]:
        response = self._request("GET", "/api/health")
        return response.json()

    def get_stores(self) -> List[Dict[str, Any]]:
        data = self.execute_query(self.STORES_QUERY)
        return sorted(data, key=lambda row: row.get("NAME", ""))

    def get_sales(
        self,
        store_ids: Sequence[int],
        start_date: str,
        end_date: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not store_ids:
            raise ValueError("At least one store id must be provided for sales query.")

        # Формирование placeholders для магазинов
        store_placeholders = ", ".join(["?"] * len(store_ids))

        # Запрос 1: Чашки
        mono_placeholders = ", ".join(["?"] * len(self.MONO_CUP_GROUPS))
        blend_placeholders = ", ".join(["?"] * len(self.BLEND_CUP_GROUPS))
        caotina_placeholders = ", ".join(["?"] * len(self.CAOTINA_CUP_GROUPS))
        all_placeholders = ", ".join(["?"] * len(self.ALL_CUP_GROUPS))

        cups_query = self.CUPS_QUERY_TEMPLATE.format(
            mono_placeholders=mono_placeholders,
            blend_placeholders=blend_placeholders,
            caotina_placeholders=caotina_placeholders,
            all_placeholders=all_placeholders,
            store_placeholders=store_placeholders,
        )
        # Конвертируем ID групп в целые числа для Firebird
        mono_ids = [int(gid) for gid in self.MONO_CUP_GROUPS]
        blend_ids = [int(gid) for gid in self.BLEND_CUP_GROUPS]
        caotina_ids = [int(gid) for gid in self.CAOTINA_CUP_GROUPS]
        all_ids = [int(gid) for gid in self.ALL_CUP_GROUPS]
        
        cups_params: List[Any] = (
            mono_ids
            + blend_ids
            + caotina_ids
            + all_ids
            + list(store_ids)
            + [start_date, end_date]
        )
        cups_rows = self.execute_query(cups_query, params=cups_params)

        # Запрос 2: Суммы
        sums_query = self.SUMS_QUERY_TEMPLATE.format(store_placeholders=store_placeholders)
        sums_params: List[Any] = list(store_ids) + [start_date, end_date]
        sums_rows = self.execute_query(sums_query, params=sums_params)

        # Запрос 3: Килограммы
        packages_placeholders = ", ".join(["?"] * len(self.PACKAGES_KG_GROUPS))
        packages_query = self.PACKAGES_QUERY_TEMPLATE.format(
            store_placeholders=store_placeholders,
            packages_placeholders=packages_placeholders,
        )
        # Конвертируем ID групп в целые числа для Firebird
        packages_ids = [int(gid) for gid in self.PACKAGES_KG_GROUPS]
        packages_params: List[Any] = list(store_ids) + [start_date, end_date] + packages_ids
        packages_rows = self.execute_query(packages_query, params=packages_params)

        return {
            "cups": cups_rows,
            "sums": sums_rows,
            "packages": packages_rows,
        }

    def execute_query(self, query: str, params: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {"query": query}
        if params is not None:
            payload["params"] = list(params)
        response = self._request("POST", "/api/query", json=payload)
        body = response.json()
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        if isinstance(body, list):
            return body
        raise ProxyAPIError("Unexpected response format from proxy API.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Response:
        last_exception: Optional[ProxyAPIError] = None
        url = f"{self.base_url}{path}"

        for index, token in enumerate(self.tokens):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(token),
                    json=json,
                    params=params,
                    timeout=(self.timeout, self.timeout),
                )
            except requests.RequestException as exc:
                last_exception = ProxyAPIError(f"Proxy API request failed: {exc}")  # type: ignore[assignment]
                logger.exception("Proxy API request failed (%s %s): %s", method, url, exc)
                continue

            if response.status_code in (401, 403) and index < len(self.tokens) - 1:
                logger.warning("Primary token rejected. Trying fallback token.")
                continue

            if response.status_code >= 400:
                raise ProxyAPIError(
                    f"Proxy API returned {response.status_code}: {response.text}"
                )

            return response

        raise last_exception or ProxyAPIAuthError("Authentication failed for all provided tokens.")

    @staticmethod
    def _headers(token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

