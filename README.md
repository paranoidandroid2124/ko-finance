## Nuvien AI Research Copilot

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
- Python dependencies are managed via `pip-compile`. After editing `requirements.in`, run `pip-compile --annotate --output-file requirements.txt requirements.in` (or `make lint`, which checks this) to refresh the lockfile. Install `pip-tools` (`python -m pip install pip-tools`) if you don't already have it.

### 3. Configuration
- Copy `.env.example` to `.env` and fill the secrets.
- Set at minimum:
  - `NEWS_FEEDS` – comma separated RSS/Atom URLs
  - `NEWS_AGGREGATION_MINUTES`, `NEWS_TOPICS_LIMIT`, `NEWS_NEUTRAL_THRESHOLD`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` if you want notifications
  - `GEMINI_API_KEY`/`OPENAI_API_KEY` for LiteLLM routing
  - `PLAN_CONFIG_FILE` / `PLAN_CATALOG_FILE` / `PLAN_SETTINGS_FILE` to override the default `uploads/admin/*.json` persistence paths (point these to `tmp/` when running tests to avoid dirty git state; CI uses `/tmp/...` automatically via `scripts/ci_tmp_env.sh`)
  - `NEWS_SUMMARY_CACHE_PATH` for redirecting the news summary cache (set this to a tmp location in CI)
  - `NEXT_PUBLIC_ENABLE_PLAN_DEBUG_TOOLS` (set to 1 only in non-production dashboards when you need plan debug overrides)
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
   docker cp ops/migrations/add_email_password_auth.sql nuvien-postgres-1:/tmp/add_email_password_auth.sql
   docker exec -i nuvien-postgres-1 psql -U kfinance -d kfinance_db -v ON_ERROR_STOP=1 -f /tmp/add_email_password_auth.sql
   ```
2. **Backend endpoints.** `web/routers/auth.py` exposes `/api/v1/auth/register|login|email/verify|password-reset/*|session/refresh|logout` backed by `services/auth_service.py` (Argon2 hashing, `auth_tokens`, `session_tokens`, audit logging, rate limits). Error responses follow `{"detail": {"code": "...", "message": "...", "retryAfter"?: number}}` and rate limit violations also emit a `Retry-After` header.
   - 재전송/잠금 플로우: `/auth/email/verify/resend`, `/auth/account/unlock/request`, `/auth/account/unlock/confirm`가 추가되어 로그인 화면에서 CTA를 붙일 수 있습니다.
3. **Next.js Credentials provider.** `web/dashboard/src/lib/authOptions.ts` calls `POST /api/v1/auth/login`, stores `accessToken`, `refreshToken`, `sessionId`, and `sessionToken` inside the NextAuth JWT/session, and keeps OAuth providers untouched. `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset/[token]`, and `/auth/verify/[token]` are implemented with loading/error states that surface `detail.code/message` from FastAPI.
4. **Env vars.** `DATABASE_URL` must be reachable from both FastAPI and Next.js processes (e.g., override to `postgresql://kfinance:your_strong_password@localhost:5432/kfinance_db` when running tests on the host). Set `AUTH_JWT_SECRET`, `NEXTAUTH_URL`, and `NEXT_PUBLIC_API_BASE_URL` for the dashboard.
5. **Docs & tests.** See `docs/auth/email_password_design.md` for the latest API contract/error table and run `pytest tests/test_auth_api.py` plus `npm run test -- --run tests/auth/formatAuthError.test.ts` after making auth changes.

### 4. CI / Quality Gates

- Run `make ci` locally or in CI to execute the default pipeline: `pip-compile` consistency check → `pytest -q` → `ruff check` → `mypy`.
- To avoid polluting the repo with file-based plan/news state, wrap any pytest/migration command with `scripts/ci_tmp_env.sh`. Example: `./scripts/ci_tmp_env.sh make test` or `./scripts/ci_tmp_env.sh docker-compose run --rm api pytest -q`.
- The script pins `PLAN_SETTINGS_FILE`, `PLAN_CONFIG_FILE`, `PLAN_CATALOG_FILE`, and `NEWS_SUMMARY_CACHE_PATH` to `/tmp/nuvien_state/...`; customize via `CI_STATE_ROOT` if your CI provides a different tmpfs mount.
- Long term we are migrating these JSON stores into PostgreSQL/Cloud Storage—see `docs/state_storage_migration.md` for the roadmap.

#### SSO & SCIM (Enterprise)
- Single Sign-On now supports multiple tenants via `/api/v1/admin/sso/providers` and `/api/v1/auth/saml|oidc/{provider}/*`. Use the admin API to register IdP metadata, rotate credentials, and issue SCIM bearer tokens per org. The legacy `AUTH_SAML_*` / `AUTH_OIDC_*` env vars remain available as a fallback for single-provider deployments.
- SCIM provisioning (`/scim/v2/Users`, `/scim/v2/Groups`) is protected by `SCIM_BEARER_TOKEN` and maps directly to `users`, `orgs`, and `user_orgs`. See `docs/sso_scim_runbook.md` for the rollout checklist and pilot dashboard.

### Core schema migrations
새로운 엔타이틀먼트/RBAC/Alert 스키마는 `ops/migrations/apply_all.sh`로 한 번에 적용할 수 있습니다.
```bash
# 로컬 환경 (DATABASE_URL 사용)
DATABASE_URL=postgresql://kfinance:your_strong_password@localhost:5432/kfinance_db \
  ./ops/migrations/apply_all.sh

# Docker Compose 컨테이너 내부에서 실행
DOCKER_POSTGRES_CONTAINER=nuvien-postgres-1 \
POSTGRES_USER=kfinance \
POSTGRES_DB=kfinance_db \
  ./ops/migrations/apply_all.sh
```
스크립트는 실패 시 즉시 중단하며, 순서를 보장하므로 수동 `psql -f …` 반복을 피할 수 있습니다. 필요하다면 `DOCKER_POSTGRES_CONTAINER` 대신 `DATABASE_URL`만 지정해도 됩니다.

### Guest/Public Preview
- `GET /api/v1/public/filings` · `POST /api/v1/public/chat` 는 인증 없이 최신 공시 목록과 간단한 챗 답변 미리보기를 제공합니다. 기본 rate limit(시간당 5회)이 적용됩니다.
- Next.js `/public` 페이지에서 위 API를 호출해 “로그인 없이 둘러보기” 경험을 제공합니다. 로그인/가입 CTA가 함께 노출되므로 체험 → 가입 전환 흐름을 구성할 수 있습니다.

### 4. Running Locally
#### 4.1 Docker Compose
```bash
docker compose up --build api worker beat litellm redis postgres
```
- `api`: FastAPI app (`web/main.py`)
- `admin-api`: Admin FastAPI surface (`web/admin_main.py`, port `8100`)
- `worker`: Celery worker (`parse.worker`)
- `beat`: Celery beat scheduling `m1.seed_recent_filings`, `m2.aggregate_news`
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

#### 4.4 Ingest reliability quick actions
- **Viewer fallback + DLQ runbook:** `docs/ops/ingest_reliability.md` covers issuer-level fallback flags, robots/ToS logging fields, Celery retry knobs, DLQ triage, and the Grafana import file (`configs/grafana/ingest_reliability_dashboard.json`).
- **Backfill CLI:** run `python scripts/ingest_backfill.py --start-date 2024-10-01 --end-date 2024-10-07 --chunk-days 2` to reseed filings idempotently (add `--corp-code 00123456` to scope to one issuer). Each run updates the `ingest_backfill_duration_seconds` Prometheus metric for alerting.

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
- QA: `python scripts/qa/sample_documents.py --total 60 --min-chunks 10 --min-ocr 15` → `python scripts/qa/verify_sentence_offsets.py --manifest scripts/qa/samples/manifest_<ts>.json --fail-on-issues`.
- Docs/Runbook: `docs/ops/rag_deeplink_runbook.md`, `docs/ops/rag_deeplink_rollout.md`.
- QA: `python scripts/qa/sample_documents.py --total 60 --min-chunks 10 --min-ocr 15`로 매니페스트를 뽑은 뒤, `python scripts/qa/verify_sentence_offsets.py --manifest scripts/qa/samples/manifest_<ts>.json --fail-on-issues`로 hash/offset 검사 리포트를 생성할 수 있습니다. CI에서는 `pytest tests/qa/test_sentence_offsets.py`로 리포트 생성 로직을 sanity-check합니다.
- Vector store prerequisites: Qdrant reachable, embeddings configured via `.env` (`EMBEDDING_MODEL`, `QDRANT_*`).
- Guardrail violations return the `SAFE_MESSAGE`; see `original_answer` for the redacted text.
- Hybrid retrieval (BM25 + dense): run `ops/migrations/20251113_add_hybrid_search_indexes.sql`, set `SEARCH_MODE=hybrid`, and tune `BM25_TOPN`, `DENSE_TOPN`, `RRF_K`. Vertex reranking is enabled via `RERANK_PROVIDER=vertex`, `RERANK_MODEL`, and `RERANK_RANKING_CONFIG` (Discovery Engine rankingConfig path); failures automatically fall back to hybrid-without-rerank.
- Evaluation: `python scripts/eval_hybrid.py --dataset eval/datasets/hybrid_v1.jsonl --mode hybrid+vertex --top-k 3 --candidate-k 50` writes `reports/hybrid/<ts>/report.json` containing Top-3 accuracy, MRR@10, NDCG@5, Recall@50, and latency p50/p95 so we can compare against previous baselines with `--baseline-report`.

### Dashboard UI (Frontend)
- 사용자 대시보드: `web/dashboard` (Next.js 기반 메인 사용자 경험). 디자인 시스템 문서: `design/ui_design_system.md`, `design/dashboard_wireframes.md`. `pnpm dev` 또는 `npm run dev`, Storybook은 `pnpm storybook`.
- 운영자 콘솔: `web/admin-dashboard` (Next.js App Router · 별도 번들, 기본 포트 `3100`). 기존 컴포넌트는 `web/dashboard/src`를 alias로 재사용하므로 동작을 바꾸지 않고도 빠르게 독립 배포를 실험할 수 있습니다. `pnpm install && pnpm dev`를 `web/admin-dashboard`에서 실행하면 `localhost:3100`에서 admin UI가 구동되고, API는 `web/admin_main.py`/`docker-compose`의 `admin-api`가 담당합니다.
- Google Workspace SSO를 붙일 경우 `GOOGLE_ADMIN_CLIENT_ID`(OAuth Client ID)와 `GOOGLE_ADMIN_ALLOWED_DOMAIN`을 환경변수로 지정하고, 프런트엔드에서 Google OAuth로 발급받은 `id_token`을 `/api/v1/admin/session`에 전달하면 됩니다. 설정이 없는 경우에는 기존의 정적 토큰(`token`) 흐름이 그대로 유지됩니다.
- Workspace 없이 자체 인증을 쓰려면 `ADMIN_ALLOWED_EMAILS`, `ADMIN_MFA_SECRETS`, `ADMIN_REQUIRE_MFA`를 지정한 뒤 `/api/v1/admin/auth/login`으로 이메일+비밀번호(+TOTP) 검증을 통과해야 운영 세션을 발급받도록 구성했습니다. Admin UI의 로그인 카드도 해당 엔드포인트를 사용합니다.

