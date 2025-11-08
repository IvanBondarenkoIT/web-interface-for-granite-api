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
    STORES_QUERY = "SELECT ID, NAME FROM STORGRP ORDER BY NAME"
    SALES_QUERY_TEMPLATE = """
SELECT 
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    COUNT(*) AS ALLCUP,
    SUM(D.SUMMA) AS TOTAL_CASH
FROM STORZAKAZDT D
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
WHERE D.STORGRPID IN ({store_placeholders})
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
GROUP BY stgp.NAME, D.DAT_
ORDER BY stgp.NAME, D.DAT_
""".strip()

    PACKAGES_QUERY_TEMPLATE = """
SELECT
    stgp.NAME AS STORE_NAME,
    D.DAT_ AS ORDER_DATE,
    SUM(GD.SOURCE) AS PACKAGES_KG
FROM STORZAKAZDT D
JOIN STORZDTGDS GD ON D.ID = GD.SZID
JOIN GOODS G ON GD.GODSId = G.ID
JOIN STORGRP stgp ON D.STORGRPID = stgp.ID
LEFT JOIN GOODSGROUPS GG ON G.OWNER = GG.ID
WHERE D.STORGRPID IN ({store_placeholders})
  AND D.CSDTKTHBID IN ('1', '2', '3', '5')
  AND D.DAT_ >= ? AND D.DAT_ <= ?
  AND (
        (
            (G.NAME LIKE '%250 g%' OR G.NAME LIKE '%250г%' OR
             G.NAME LIKE '%500 g%' OR G.NAME LIKE '%500г%' OR
             G.NAME LIKE '%1 kg%' OR G.NAME LIKE '%1кг%' OR
             G.NAME LIKE '%200 g%' OR G.NAME LIKE '%200г%' OR
             G.NAME LIKE '%125 g%' OR G.NAME LIKE '%125г%' OR
             G.NAME LIKE '%80 g%' OR G.NAME LIKE '%80г%' OR
             G.NAME LIKE '%0.25%' OR G.NAME LIKE '%0.5%' OR
             G.NAME LIKE '%0.2%' OR G.NAME LIKE '%0.125%' OR
             G.NAME LIKE '%0.08%')
            AND (G.NAME LIKE '%Coffee%' OR G.NAME LIKE '%кофе%' OR G.NAME LIKE '%Кофе%' OR G.NAME LIKE '%Blaser%')
        )
        OR (GG.NAME LIKE '%Caotina swiss chocolate drink (package)%')
      )
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

        placeholders = ", ".join(["?"] * len(store_ids))
        params: List[Any] = list(store_ids) + [start_date, end_date]

        sales_rows = self.execute_query(
            self.SALES_QUERY_TEMPLATE.format(store_placeholders=placeholders),
            params=params,
        )
        package_rows = self.execute_query(
            self.PACKAGES_QUERY_TEMPLATE.format(store_placeholders=placeholders),
            params=params,
        )
        return {
            "sales": sales_rows,
            "packages": package_rows,
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

