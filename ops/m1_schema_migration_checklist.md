# M1 Schema Migration Checklist

> 목적: 새 ORM/스키마 정합성 유지 및 Celery 파이프라인 회귀 방지를 위한 운영 절차  
> 대상: `filings`, `extracted_facts`, `summaries` 주요 테이블

## 0. 사전 준비
- DB 백업: 최신 스냅샷 확보 (예: `pg_dump`, RDS snapshot 등)
- Celery 워커, API, 스케줄러 중지
- `.env` 내 `DATABASE_URL` 설정 확인

## 1. 마이그레이션 실행
```bash
python scripts/migrate_schema.py
```

- 로그에서 `Schema migration completed successfully.` 메시지 확인
- 오류 시 즉시 중단하고 백업으로 롤백

## 2. 구조 확인
```sql
\d filings
\d extracted_facts
\d summaries
```
- `filings` : `report_name`, `file_path`, `category_confidence`, `analysis_status`, `chunks` 존재 여부 확인  
- `extracted_facts` : `fact_type`, `unit`, `currency`, `anchor_page`, `confidence_score` 등 존재 확인  
- `summaries` : `who`, `what`, `when`, `where`, `how`, `why`, `insight`, `confidence_score` 존재 확인

## 3. 데이터 검증
- 기존 레코드: NULL → 기본값(`analysis_status='PENDING'`, `method='llm_extraction'`) 적용 여부 점검
- `summaries` 테이블의 `fiveW1H` JSON이 분해되었는지 확인 (`SELECT who, what FROM summaries LIMIT 5;`)
- 주요 필드 샘플링: 파이프라인으로 생성된 최신 공시 레코드와 비교

## 4. 서비스 재기동
- Celery 워커, API 서비스 순차 기동
- `scripts/seed_data.py` 또는 수동 업로드로 테스트 공시 투입

## 5. 모니터링 포인트
- Celery 로그: classification/extraction/self-check 단계 에러 여부
- Qdrant 인덱싱: `analysis_status` → `"INDEXED"` 전환 확인
- 텔레그램 알림: 새 필드 기반 포맷 정상 출력 여부

## 6. 롤백 절차
- 이슈 발생 시 서비스 중단 → 백업 복원 → 워커/API 재기동
- 원인 파악 후 수정된 마이그레이션 스크립트 재적용
