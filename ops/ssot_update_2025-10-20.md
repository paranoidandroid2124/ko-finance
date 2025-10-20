# SSoT Update — 2025-10-20

> M1, M2 핵심 흐름을 최신 구현 기준으로 정리했습니다. (Codex 실행 로그 기반)

## M1. DART Watcher+

- **수집**  
  - `ingest/dart_client.py`  
    - OpenDART 공시 목록 조회 (`list_recent_filings`)  
    - 공시원문 ZIP 다운로드 (`download_document_package`)  
  - `ingest/dart_seed.py`  
    - ZIP → XML/PDF/첨부 분해 (`extract_filing_package`)  
    - `filings.source_files`(JSON) 및 MinIO 업로드/프리사인 URL 기록  
    - Celery 태스크 큐잉 (`process_filing_file.delay`)
- **파싱/처리**  
  - `parse/tasks.py.process_filing_file`  
    - XML 우선 Chunk 생성 (`parse/xml_parser.extract_chunks_from_xml`)  
    - PDF 존재시 보조 Chunk 추가 (`parse/pdf_parser.extract_chunks`)  
    - LLM 분류/추출/셀프체크/요약 → DB 반영 (`models.filing / fact / summary`)  
    - 텔레그램 알림 발송 & RAG 인덱싱 큐잉 (`services.notification_service.send_telegram_message`, `rag.embed_and_index`)
- **임베딩/RAG**  
  - `services/vector_service.py`  
    - lazy Qdrant 연결 + 재시도  
    - Chunk 임베딩 → Qdrant 컬렉션 저장 (`embed_and_store_chunks`)  
    - 질의 벡터 검색 (`query_vector_store`)
- **자동화/관측**  
  - `parse/celery_app.py`  
    - beat 스케줄: `seed-dart-filings-hourly`  
    - Langfuse 통합 (`llm/llm_service.py`), MinIO 연계 (`services/minio_service.py`)  
  - CLI/문서: `scripts/migrate_schema.py`, `ops/m1_schema_migration_checklist.md`, `ops/m1_pipeline_smoke.md`, `ops/m1_performance_notes.md`

## M2. Market Mood

- **수집**  
  - `ingest/news_fetcher.py`  
    - `NEWS_FEEDS` 환경변수 기반 RSS/Atom 기사 수집 (`feedparser`)  
    - XML/HTML 본문 병합 & `NewsArticleCreate` 변환  
    - feedparser 미설치/피드 오류 시 graceful fallback
  - `ingest/news_client.py.MockNewsClient`  
    - 목업 뉴스 4건 제공 (테스트용)
- **시딩/자동화**  
  - `scripts/seed_news.py.seed_news(use_mock, limit)`  
    - 실피드 시도 → 기사 없으면 목업으로 폴백  
    - Celery 태스크 `process_news_article` 호출  
  - `parse/tasks.fetch_latest_news_task`  
    - beat 스케줄 `fetch-latest-news-quarter-hour` (15분 주기)
- **분석/저장/알림**  
  - `parse/tasks.process_news_article`  
    - LLM 감성·토픽 분석 (`llm.llm_service.analyze_news_article`)  
    - 결과 저장 (`models.news.NewsSignal`), Langfuse 로깅  
    - 텔레그램 알림: 감성/토픽/원문 링크 포함
- **DB 스키마**  
  - `scripts/migrate_schema.py` → `news_signals` 테이블 생성  
  - `schemas/api/news.py`, `schemas/news.py` → API 응답/입력 모델

## 공통/테스트

- `requirements.txt` → `lxml`, `feedparser`, `python-multipart` 추가  
- `tests/test_parse_tasks.py` → XML등 외부 모듈 스텁  
- `tests/test_news_fetcher.py` → RSS 파서 모킹 단위 테스트  
- Celery beat / worker 컨테이너 재빌드 가이드 (`docker-compose build api worker beat`, `docker-compose up -d --force-recreate ...`)

## 다음 TODO

- `NEWS_FEEDS`에 실서비스 피드 추가 및 실패 접수번호 재시도 전략 정의  
- Langfuse/Grafana 대시보드에서 뉴스 감성·토픽 성공률 모니터링  
- Market Mood UI에 실데이터 연결 (프론트엔드 반영 필요)  
- DART 문서미등록 케이스(“파일이 존재하지 않습니다.”) 재처리 스케줄링
