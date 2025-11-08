## Project Plan: Flask Proxy Dashboard

### 1. Preparation
- Review provided prompt requirements (`WEB_FLASK_PROMPT.md`) and clarify deliverables.
- Establish local working notes (this plan) to track progress and ensure staged execution.

### 2. Environment Setup
- Create Python 3.11 virtual environment in `.venv`.
- Install base dependencies: `Flask`, `requests`, `python-dotenv`, `gunicorn`.
- Freeze initial dependencies to `requirements.txt`.

### 3. Project Scaffolding
- Create project root structure:
  - Core files: `app.py`, `config.py`, `proxy_client.py`.
  - Package folders: `services/`, `templates/`, `static/css/`.
  - Ancillary files: `env.example`, `.gitignore`, `.dockerignore`, `README.md`, `Dockerfile`.
- Initialize Git repository once structure is laid out.

### 4. Proxy API Integration
- Implement `proxy_client.py`:
  - Configure `requests.Session` with retry strategy.
  - Methods: `health()`, `get_stores()`, `get_sales()`, `execute_query()`, plus helper for package query.
- Load credentials and API base URL via `config.py` using `python-dotenv`.

### 5. Services Layer
- Create `services/analytics.py`:
  - Combine sales and package query results.
  - Provide aggregation helpers for dashboard metrics (totals, stores count).
  - Handle date ranges (default: current month, using timezone-aware UTC).

### 6. Flask Application
- Define routes in `app.py`:
  - `/` dashboard: fetch health, store list, default-period sales; render `dashboard.html`.
  - `/sales`: accept filters (`store`, `start_date`, `end_date`, `sort`), fetch filtered data, render `sales_table.html`.
- Add error handling and flash messages for API failures.
- Register configuration, Jinja filters/helpers as needed.

### 7. Templates & Static Assets
- Build `templates/base.html` with Bootstrap 5 CDN, navbar, footer.
- Create `templates/dashboard.html` with summary cards and condensed table preview.
- Create `templates/sales_table.html` with filters form and responsive table.
- Optional: `static/css/styles.css` for layout tweaks.

### 8. Testing & Validation
- Add smoke tests or service-level unit tests (optional but preferred).
- Run application locally; verify API connectivity (health endpoint) with sample tokens once available.
- Lint/format codebase (black/flake8 optional).

### 9. Deployment Prep
- Author `Dockerfile` per prompt.
- Write `.dockerignore`.
- Complete `README.md` with setup, env var usage, run instructions (local, Docker, Railway hints).
- Ensure `env.example` includes documented variables.

### 10. Version Control & Hosting
- Create GitHub repository; push project with meaningful commit history.
- Configure Railway deployment (Docker-based) once repository is ready.
- Verify deployed app uses environment variables for tokens securely.

### 11. Post-Deployment
- Document verification steps and any known limitations.
- Update TODO list as tasks complete.

