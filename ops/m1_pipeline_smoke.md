# M1 Pipeline Smoke Test

목표: DART Watcher+ 파이프라인의 ingest → 분석 → 알림 → RAG 인덱싱 흐름이 최신 스키마에서 정상 동작하는지 단시간 내 검증한다.

## 0. 환경 준비
- `.env` : `DATABASE_URL`, `REDIS_URL`, `LITELLM_CONFIG`, `TELEGRAM_*` 확인
- 서비스 구성
  - `docker-compose up redis postgres qdrant`
  - Celery 워커: `celery -A parse.tasks worker --loglevel=INFO`
  - FastAPI: `uvicorn web.main:app --reload`

## 1. 샘플 공시 처리
1. 테스트용 PDF 확보 (`uploads/` 디렉터리)
2. API 업로드  
   ```bash
   http --form POST :8000/api/v1/filings/upload file@./uploads/sample.pdf
   ```
   또는 `scripts/seed_data.py --days-back 1`
3. Celery 로그 확인:  
   - `Parsing PDF into chunks`  
   - `Classifying content`  
   - `Saving verified facts`  
   - `Triggering RAG indexing`

## 2. 결과 검증
- DB 확인 (psql/pgcli)
  ```sql
  SELECT id, report_name, status, analysis_status FROM filings ORDER BY created_at DESC LIMIT 5;
  SELECT fact_type, value, anchor_page FROM extracted_facts ORDER BY created_at DESC LIMIT 5;
  SELECT who, what, confidence_score FROM summaries ORDER BY created_at DESC LIMIT 5;
  ```
- Qdrant 확인
  ```bash
  http GET :6333/collections/k-finance-rag-collection
  ```
- 텔레그램 봇 메시지 수신 여부

## 3. RAG 질의 시험
```bash
http POST :8000/api/v1/rag/query question="요약된 핵심 내역은?" filing_id=<UUID>
```
- 응답 필드 `answer`, `context` 확인  
- 로그: `RAG answer generated via ...`

## 4. 회귀 점검 항목
- LLM 오류 시 fallback 로그 확인  
- `analysis_status` 상태 전이 (`ANALYZED` → `INDEXED`)  
- `chunks` JSON 저장 및 `raw_md` 텍스트 길이 검증

## 5. 문제 발생 시
- Celery 재시도 / 실패 태스크 추적 (`celery -A parse.tasks inspect active`)
- 모델 응답 JSON 파싱 실패 → `llm/llm_service.py` 로그 확인  
- Qdrant 연결 실패 → `services/vector_service.py` 재시도 로그 및 환경변수 점검
