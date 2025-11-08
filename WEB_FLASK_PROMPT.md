# 📝 Prompt: Flask Web Dashboard via Firebird Proxy API

Use this prompt when creating a **new** project (fresh repository) that implements a Flask-based web interface pulling data from our Firebird database through the existing Proxy API. The goal is a mobile-first dashboard with minimal JavaScript, server-side filtering/sorting, and clear architecture for future extensions.

---

## 🔧 Tech Stack
- Python 3.11+
- Flask 3.x
- Requests (for REST calls)
- Jinja2 templates
- Bootstrap 5 (CDN) for responsive UI
- gunicorn (for production)
- python-dotenv (local development)

**No direct DB connection!** All queries must go through the Proxy API (`http://85.114.224.45:8000`).

---

## 📁 Project Structure

```
flask-proxy-dashboard/
├── app.py                 # Flask application entry point
├── config.py              # Load env settings
├── proxy_client.py        # HTTP client for Proxy API
├── services/
│   └── analytics.py       # Transform/aggregate API data
├── templates/
│   ├── base.html          # Layout with Bootstrap
│   ├── dashboard.html     # Summary cards + quick table
│   └── sales_table.html   # Detailed sales table with filters
├── static/
│   └── css/styles.css     # Custom tweaks (optional)
├── requirements.txt
├── env.example            # SECRET_KEY, PROXY tokens
├── Dockerfile             # For deployment (Railway, etc.)
└── README.md              # Setup + run instructions
```

Optionally add `tests/` with pytest for services.

---

## 🔑 Environment Variables (`env.example`)
```
SECRET_KEY=replace_with_secret
PROXY_API_URL=http://85.114.224.45:8000
PROXY_PRIMARY_TOKEN=
PROXY_FALLBACK_TOKEN=
PROXY_TIMEOUT=30
```

Note: tokens must be kept out of Git.

---

## 🔌 Proxy API Client Requirements
- Use a `requests.Session` with retry logic (HTTPAdapter + Retry) for resilience.
- Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`.
- Methods:
  - `health()` → GET `/api/health`.
  - `get_stores()` → POST `/api/query` with `SELECT ID, NAME FROM STORGRP ORDER BY NAME`.
  - `get_sales(store_ids, start_date, end_date)` → see SQL below.
  - `execute_query(query, params)` helper.
- Mask tokens in logs; raise informative exceptions.

---

## 📊 Core SQL Query (IMPORTANT)

Use this SQL, sent to the Proxy API via POST `/api/query` (with `{"query": "...", "params": [...]}`) to retrieve sales data:

```sql
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
```

To capture package quantities (kg), send an additional query:

```sql
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
```

**Parameters**: the `IN (...)` list is built dynamically; parameters array = `[store_id1, store_id2, ..., start_date, end_date]`.

On the client side, merge results by `(STORE_NAME, ORDER_DATE)` to combine cups and packages.

---

## 🖥️ Flask Views
- `/`:
  - Fetch health, stores, and default sales (current month).
  - Show summary cards (`stores_count`, total sales, cups, packages).
  - Display latest rows in a scrollable table.
- `/sales`:
  - Accept GET params: `start_date`, `end_date`, `store`, `sort`.
  - Server-side filtering (re-run query) and sorting (by date/store/sum).
  - Render a detailed table with mobile-friendly layout.
- Use `datetime.now(timezone.utc)` for dates to avoid TZ issues.
- Gracefully handle API errors (flash message or placeholder text).

---

## 📄 Templates
- `base.html`: includes Bootstrap 5, responsive navbar, `{% block content %}`.
- `dashboard.html`: summary cards + quick table preview.
- `sales_table.html`: filter form + full table (submit reloads page). Minimal JS (only for optional niceties).
- `styles.css`: optional tweaks (e.g., fixed table height).

---

## 🐳 Dockerfile

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
```

Add `.dockerignore` (exclude `.venv`, `__pycache__`, etc.).

---

## ✅ Deliverables Checklist
1. `README.md` with setup steps (env, run, Docker, Railway notes).
2. Flask app with routes `/` and `/sales`.
3. Proxy client with robust error handling and retries.
4. Server-rendered dashboard + table (Bootstrap/Mobile-first).
5. Dockerfile + `.dockerignore`.
6. Optionally, basic tests for `services/analytics.py`.

---

Use this entire document as the prompt when generating the new project. It contains all requirements, structure, and the precise SQL needed. Adjust as necessary, but maintain the REST-only database access model and commit clean, well-documented code. 

