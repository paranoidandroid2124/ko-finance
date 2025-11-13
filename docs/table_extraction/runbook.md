## Table Extraction v1 Runbook

### 1. QA & CI Automation
1. **Sample 준비**: 운영 PDF 루트를 마운트 후 `python scripts/table_extraction_eval.py --samples 50 --input /data/filings --output reports/table_extraction/quality_report.json`.
2. **CI 연동**:
   - 아티팩트: `reports/table_extraction/quality_report.json` 업로드.
   - 게이트: `passRate < 0.90` 또는 `avgCoreAccuracy < 0.9` 시 빌드 실패 + Slack 알림.
   - 데이터 없음 시(`RuntimeError: No PDF files`) → 잡 새로 큐잉.
3. **지속 모니터링**: 주 1회 스케줄러에서 같은 명령 실행, 결과를 Ops 시트에 기록.

### 2. Table Explorer UI 연동 플랜
1. **API 사용**:
   - 리스트: `GET /api/v1/table-explorer/tables?receiptNo=...`.
   - 상세: `GET /api/v1/table-explorer/tables/{id}` (Pro/Enterprise only).
   - 다운로드: `GET /api/v1/table-explorer/export?id=...&fmt=csv|json`.
2. **Front 구성**:
   - 좌측: 표 카드(타입/Confidence/페이지).
   - 우측: 원문 미리보기 iframe + 정규화 테이블(react-table).
   - Pro 이상에서만 셀 뷰/다운로드 버튼 렌더링.
3. **권한 처리**: Next.js에서 plan context 가져와 `plan.tier`가 `pro|enterprise`일 때만 상세 호출.

### 3. 운영/백필 흐름
1. **Celery 잡**:
   - 재처리: `tables.extract_receipt.delay("20251110000235")`.
   - 실패 시 DLQ(`task_name=tables.extract`, payload=receipt_no) 확인 후 재시도.
2. **환경 변수**:
   - `.env`: `TABLE_EXTRACTION_MAX_PAGES=30`, `TABLE_EXTRACTION_TAT_SECONDS=15`, `TABLE_EXTRACTION_INCLUDE_UNKNOWN=false`.
   - 변경 시 `docker compose down && docker compose up -d`.
3. **메트릭/알림**:
   - Prometheus gauge `table_extract_success_rate`(source별 성공률), `table_cell_accuracy`(유형별 셀 정확도).
   - Alert: 성공률 <99% 5분 지속 → #ops-support.
4. **장애 대응**:
   - CSV/JSON artefact 손상 시 `services/table_extraction_service._write_artifacts` 경로 삭제 후 재실행.
   - 파서 오류는 `ingest_dead_letters` 테이블에서 receipt별로 확인.
