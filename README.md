## K-Finance AI Research Copilot

Backend copilot that ingests Korean filings, news, and documents to produce research signals. This README focuses on restoring the **M2 Market Mood** pipeline while keeping M1/M3 context.

### 1. Prerequisites
- Python 3.11+ (project is validated on 3.13)
- Poetry or `pip` for dependency management
- Docker & Docker Compose (optional but recommended)
- Redis, PostgreSQL, Qdrant, Langfuse, Telegram bot, and LiteLLM credentials if you intend to run the full stack

### 2. Installation
```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. Configuration
- Copy `.env.example` to `.env` and fill the secrets.
- Set at minimum:
  - `NEWS_FEEDS` – comma separated RSS/Atom URLs
  - `NEWS_AGGREGATION_MINUTES`, `NEWS_TOPICS_LIMIT`, `NEWS_NEUTRAL_THRESHOLD`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` if you want notifications
  - `GEMINI_API_KEY`/`OPENAI_API_KEY` for LiteLLM routing
- Optional integrations: `LANGFUSE_*`, `MINIO_*`, `QDRANT_*`

### 4. Running Locally
#### 4.1 Docker Compose
```bash
docker compose up --build api worker beat litellm redis postgres
```
- `api`: FastAPI app (`web/main.py`)
- `worker`: Celery worker (`parse.worker`)
- `beat`: Celery beat scheduling `m1.seed_recent_filings` and `m2.aggregate_news`
- `litellm`: Model gateway for all LLM calls

#### 4.2 Celery (bare metal)
```bash
celery -A parse.worker worker --loglevel=info
celery -A parse.worker beat --loglevel=info
```
Ensure Redis/Postgres/Qdrant services are reachable via `.env`.

#### 4.3 Triggering Market Mood ingestion
1. Fetch news articles:
   ```python
   from ingest.news_fetcher import fetch_news_batch
   articles = fetch_news_batch(limit_per_feed=5, use_mock_fallback=False)
   ```
2. Dispatch each article to Celery:
   ```python
   from parse.celery_app import app
   for article in articles:
       app.send_task("m2.process_news", args=[article.model_dump()])
   ```
3. Aggregation runs every 15 minutes via `m2.aggregate_news`. You can trigger it manually:
   ```python
   from parse.tasks import aggregate_news_data
   aggregate_news_data()
   ```

### 5. Common Commands
- `pytest tests/test_news_fetcher.py tests/test_news_metrics.py` – Market Mood unit tests
- `pytest tests/test_parse_tasks.py tests/test_llm_service.py tests/test_rag_api.py` – critical regressions
- `make lint` – optional lint pass if GNU Make is available
- `alembic upgrade head` – run DB migrations (when migration scripts are present)

### 6. Deployment Notes
- Use Docker Compose overrides or Kubernetes manifests to run `api`, `worker`, `beat`, `litellm`, `redis`, `postgres`, and `qdrant`.
- Configure persistent volumes for Postgres and Qdrant.
- Provide environment variables through secrets managers (AWS SSM, GCP Secret Manager, etc.).
- For production telemetry enable Langfuse (`LANGFUSE_*`) and route notifications through a restricted Telegram chat.

### 7. Observability Checklist
- **Langfuse**: verify spans exist for `analyze_news_article`
- **Logs**: `parse/tasks.py` logs Market Mood processing at INFO level
- **Alerts**: Telegram bot message `*[Market Mood]*` confirms aggregation

### 8. Performance Snapshot
- `tally_news_window` processes ~5,000 articles in `~0.004s` on a laptop (see `python -c` benchmark in ops notes).
- Dominant costs remain RSS fetching and LLM calls (`analyze_news_article`). Use Celery concurrency or LiteLLM batching to scale analysis throughput.

### 9. Interactive Analyst
- Call `POST /api/v1/rag/query` with `question`, `filing_id`, and optional `top_k`, `run_self_check` (defaults to `true`).
- Ensure Celery worker/beat are running so `m3.run_rag_self_check` can log Langfuse telemetry.
- Tests: `pytest tests/test_rag_api.py tests/test_rag_self_check.py tests/test_llm_service.py`.
- Vector store prerequisites: Qdrant reachable, embeddings configured via `.env` (`EMBEDDING_MODEL`, `QDRANT_*`).
- Guardrail violations return the `SAFE_MESSAGE`; see `original_answer` for the redacted text.

### Dashboard UI (Frontend)
- 위치: `web/dashboard`
- Next.js 기반 데이터 대시보드 UI. 디자인 시스템 문서: `design/ui_design_system.md`, `design/dashboard_wireframes.md`.
- 개발: 패키지 설치 후 `pnpm dev` 또는 `npm run dev`, Storybook은 `pnpm storybook`.
