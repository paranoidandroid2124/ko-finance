# RAG 딥링크/뷰어 Runbook

본 문서는 기존 Prometheus·Audit Log 파이프라인과 동일한 운영 방향성을 유지하면서, 새롭게 도입한 딥링크·뷰어 기능을 온콜 체계에 편입하기 위한 절차를 정리한다. 다른 모듈(인제스트, LightMem 등)과 똑같은 모니터링 구성요소를 재사용하므로, 운영자가 추가 도구를 학습할 필요가 없다.

## 1. 구성요약
- **플래그**: `RAG_LINK_DEEPLINK`, `DEEPLINK_VIEWER` (환경별 단계적 롤아웃).
- **백엔드 로깅**  
  - Prometheus Counter `rag_telemetry_events_total{event,source,reason}` (이미 사용 중인 Prom stack 재사용).  
  - `audit_rag_event`에 `rag.telemetry.<event>`로 기록 → partitioned `audit_logs_*` 테이블에 저장.  
  - Langfuse trace(`rag.self_check`)는 기존 `/rag/query` 요약 플로우 그대로 사용.
- **프런트 로깅**  
  - `logEvent('rag.*')` → `web/dashboard/src/lib/ragTelemetryClient.ts`에서 배치 전송(`navigator.sendBeacon` 우선).  
  - 기존 telemetry hook 구조를 그대로 이용하므로 다른 스토어/컴포넌트와 동일한 방식.

## 2. 모니터링 방법
1. **Prometheus / Grafana**  
   - `rag_telemetry_events_total`을 `event`/`source`/`reason`별로 그래프화.  
   - 기존 인제스트 대시보드에 패널 추가하거나 신규 Row 생성.  
   - 알람 룰 예시:  
     - `increase(rag_telemetry_events_total{event="rag.deeplink_failed"}[5m]) / increase(rag_telemetry_events_total{event="rag.deeplink_opened"}[5m]) > 0.05`.
2. **Audit 로그**  
   - psql:  
     ```sql
     SELECT ts, extra->>'event', extra->>'document_id', extra->>'reason'
     FROM audit_logs
     WHERE source = 'rag'
       AND action LIKE 'rag.telemetry.%'
       AND ts > now() - interval '1 hour';
     ```
   - 기존 On-call이 쓰던 audit inspection 스크립트와 동일.
3. **앱 로그 / Langfuse**  
   - `web/routers/rag.py`에서 WARN/ERROR 레벨 로그가 나오면 기존 ELK/CloudWatch에서 검색.
   - Langfuse trace에서 동일 `traceId`로 연결되는 self-check 요약 존재 여부 확인(기존 절차 동일).

## 3. 온콜 대응 시나리오
| 상황 | 확인 절차 | 조치 |
| --- | --- | --- |
| 딥링크 실패율 급증 | Grafana alert → Prometheus ratio 확인 → Audit 로그에서 `reason` 필드 확인 | 원인별 대응 (권한 오류라면 토큰 만료 확인, 네트워크라면 CDN 상태 확인) |
| 뷰어 로딩 지연 신고 | `rag.deeplink_viewer_error` 이벤트와 `reason` 분석 | PDF 저장소/Minio 가용성 확인 → 필요 시 플래그 롤백 |
| Telemetry API 4xx/5xx | FastAPI logs 및 Sentry 확인 | 잘못된 payload면 프런트 hotfix, 서버 오류면 API 롤백 |

## 4. 접근성/VPAT 체크리스트 업데이트
- 뷰어 페이지(`web/dashboard/src/app/viewer/[token]/page.tsx`)  
  - 키보드 포커스 순서 / ARIA 레이블 확인  
  - 색 대비 (딥링크 상태 배너) 점검  
  - 스크린리더로 "출처 세부정보" 내용 읽히는지 검증  
- ChatMessage 배지  
  - 버튼 역할/aria-label 지정 (추후 개선 항목 기록)  
- QA 자동화 스크립트 문서(`scripts/qa/*.py`) 링크를 사용자 가이드/README에 추가.

## 5. 변경 내역 리뷰 루프
- **릴리즈 노트**: 릴리즈 Wiki에 “RAG Evidence 딥링크/QA/Telemetry” 항목 추가, 플래그·롤백 절차 명시.  
- **코드 리뷰 체크리스트**:  
  1. Telemetry 이벤트 추가 시 `schemas/api/rag.py`와 백엔드 허용 목록에 동시 반영했는가?  
  2. Prometheus 라벨 cardinality 제한 준수(64자 이내) 확인했는가?  
  3. Audit 로그에 민감정보(PII) 없음 확인.  
- **주간 헬스 리뷰**: 기존 ingest/LLM 헬스 미팅 시간에 Telemetry KPI(사용률/실패율) 표 공유.

## 6. 참고 링크
- `services/ingest_metrics.py` (Prometheus collector 패턴)  
- `services/audit_log.py` (분할 테이블 및 쓰기 헬퍼)  
- `docs/ops/ingest_reliability.md` (기존 모니터링 정책)  
- `scripts/qa/README` _(추가 예정)_ – QA 자동화 가이드
