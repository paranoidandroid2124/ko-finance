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
- Optional OCR fallback (Google Cloud Vision):
  - `ENABLE_VISION_OCR=true` to activate Vision-backed OCR for image-based filings
  - `GOOGLE_APPLICATION_CREDENTIALS` pointing to the service account JSON with Vision access
  - `OCR_TRIGGER_MIN_TEXT_LENGTH` (default `400`) controls when the fallback runs
  - `OCR_TRIGGER_MAX_PAGES` (default `15`) limits how many pages are rasterised per filing
  - `OCR_VISION_RENDER_DPI` and `OCR_VISION_LANGUAGE_HINTS` fine-tune rendering quality and language hints

#### Email/Password Authentication Checklist
1. **Apply the credential schema.** The combined SQL lives at `ops/migrations/add_email_password_auth.sql`. When using Docker Compose, copy it into the Postgres container and execute:
   ```bash
   docker cp ops/migrations/add_email_password_auth.sql ko-finance-postgres-1:/tmp/add_email_password_auth.sql
   docker exec -i ko-finance-postgres-1 psql -U kfinance -d kfinance_db -v ON_ERROR_STOP=1 -f /tmp/add_email_password_auth.sql
   ```
2. **Backend endpoints.** `web/routers/auth.py` exposes `/api/v1/auth/register|login|email/verify|password-reset/*|session/refresh|logout` backed by `services/auth_service.py` (Argon2 hashing, `auth_tokens`, `session_tokens`, audit logging, rate limits). Error responses follow `{"detail": {"code": "...", "message": "...", "retryAfter"?: number}}` and rate limit violations also emit a `Retry-After` header.
   - 재전송/잠금 플로우: `/auth/email/verify/resend`, `/auth/account/unlock/request`, `/auth/account/unlock/confirm`가 추가되어 로그인 화면에서 CTA를 붙일 수 있습니다.
3. **Next.js Credentials provider.** `web/dashboard/src/lib/authOptions.ts` calls `POST /api/v1/auth/login`, stores `accessToken`, `refreshToken`, `sessionId`, and `sessionToken` inside the NextAuth JWT/session, and keeps OAuth providers untouched. `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset/[token]`, and `/auth/verify/[token]` are implemented with loading/error states that surface `detail.code/message` from FastAPI.
4. **Env vars.** `DATABASE_URL` must be reachable from both FastAPI and Next.js processes (e.g., override to `postgresql://kfinance:your_strong_password@localhost:5432/kfinance_db` when running tests on the host). Set `AUTH_JWT_SECRET`, `NEXTAUTH_URL`, and `NEXT_PUBLIC_API_BASE_URL` for the dashboard.
5. **Docs & tests.** See `docs/auth/email_password_design.md` for the latest API contract/error table and run `pytest tests/test_auth_api.py` plus `npm run test -- --run tests/auth/formatAuthError.test.ts` after making auth changes.

### Guest/Public Preview
- `GET /api/v1/public/filings` · `POST /api/v1/public/chat` 는 인증 없이 최신 공시 목록과 간단한 챗 답변 미리보기를 제공합니다. 기본 rate limit(시간당 5회)이 적용됩니다.
- Next.js `/public` 페이지에서 위 API를 호출해 “로그인 없이 둘러보기” 경험을 제공합니다. 로그인/가입 CTA가 함께 노출되므로 체험 → 가입 전환 흐름을 구성할 수 있습니다.

### 4. Running Locally
#### 4.1 Docker Compose
```bash
docker compose up --build api worker beat litellm redis postgres
```
- `api`: FastAPI app (`web/main.py`)
- `worker`: Celery worker (`parse.worker`)
- `beat`: Celery beat scheduling `m1.seed_recent_filings`, `m2.aggregate_news`, `m4.generate_daily_brief`
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
- `make eval` – execute prompt-based regression checks (promptfoo) and optional RAG scoring. Provide `EVAL_ARGS="--filing-id=<uuid> --question='...'"` when you want to include Ragas metrics.

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
