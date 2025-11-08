# Flask Proxy Dashboard

Server-rendered Flask application that consumes the Granite proxy API to display store analytics via a mobile-friendly dashboard.

## Getting Started

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (see `env.example`) and provide the proxy API credentials.

## Run Locally

```bash
flask --app app run --debug
```

## Tests

```bash
pytest
```

## Data Loading Mode

- Интерфейс загружается без обращений к Proxy API.
- Нажмите «Загрузить данные» на главной странице или в разделе продаж, чтобы инициировать запросы.
- После первой загрузки можно менять фильтры; параметр `load=1` останется в запросе.

## Railway Deployment

1. Push this repository to GitHub (already configured).
2. On Railway, create a new service from this repository and select the Dockerfile build strategy.
3. Define the required environment variables (`SECRET_KEY`, `PROXY_PRIMARY_TOKEN`, `PROXY_FALLBACK_TOKEN`, etc.).
4. Deploy; Railway will expose port `8000` automatically.

### Local Docker build

```bash
docker build -t flask-proxy-dashboard .
docker run -p 8000:8000 --env-file .env flask-proxy-dashboard
```

