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

## Deployment

Build the Docker image:

```bash
docker build -t flask-proxy-dashboard .
```

The resulting container listens on port `8000`; ideal for Railway deployment.

