# RAG UX 개선 Stage 1: 재색인 패널 현황 점검

## 1. 작업 맥락
- 목적: RAG 재색인 패널의 데이터 흐름과 Langfuse 메타 기록을 재점검하고, 자동 재시도 규칙 및 Evidence diff 하이라이트 요구사항을 명확히 합니다.
- 범위: FastAPI `/api/v1/admin/rag/*` 엔드포인트와 Next.js `AdminRagPanel` 컴포넌트, `uploads/admin` 스토리지에 저장되는 히스토리를 함께 검토했습니다.
- 결과물: 현 구조 요약, 확인된 데이터 필드, 개선에 필요한 요구사항 정리, 추가 검증 항목 목록.

## 2. 재색인 패널 데이터 흐름 요약
- **데이터 적재**
  - `services/admin_rag_service.append_reindex_history`가 `uploads/admin/rag_reindex.jsonl`에 실행 이벤트를 저장합니다.
  - 실패 건은 `enqueue_retry_entry`를 통해 `uploads/admin/rag_reindex_retry.json` 큐로 이동하며, `attempts`, `lastAttemptAt`, `lastSuccessAt` 등 재시도 메타를 유지합니다.
- **API 레이어**
  - `web/routers/admin_rag.py`
    - `GET /reindex/history`: 히스토리 파일을 역순으로 읽어 `AdminRagReindexHistoryResponse(runs=[])`로 반환, `status`, `langfuseTraceUrl`, `langfuseTraceId`, `queueId`가 포함됩니다.
    - `GET /reindex/queue`: 큐 파일을 읽고 상태·검색 필터를 적용해 `entries`를 제공합니다.
    - `POST /reindex/queue/retry`: 큐 항목을 재사용해 `_perform_reindex`를 실행하며, 이전 Langfuse trace/span ID를 메타에 전달합니다.
- **프런트엔드**
  - `web/dashboard/src/hooks/useAdminConfig.ts`에서 React Query 키 `ADMIN_RAG_REINDEX_HISTORY_KEY`, `ADMIN_RAG_REINDEX_QUEUE_KEY`로 데이터를 불러옵니다.
  - `AdminRagPanel.tsx`는
    - 재색인 히스토리를 `taskId` 단위로 그룹화하고 상태 배지, Langfuse 링크, 토스트 복기를 표준 톤으로 안내합니다.
    - 큐 항목의 `attempts`·`lastError`를 표시하지만, 자동 재시도 규칙은 현재 수동 플로우만 제공됩니다.

## 3. Langfuse 메타 구조 정리
- `_perform_reindex`에서 Langfuse span을 생성하고 다음 필드를 저장합니다.
  - `langfuseTraceUrl`: 외부 링크, 프런트는 버튼으로 새 탭을 열어줍니다.
  - `langfuseTraceId`, `langfuseSpanId`: 텍스트/모노스페이스 배지로 출력됩니다.
  - 재시도 시 `previousTraceId`, `previousSpanId`를 metadata에 기록해 Langfuse 측에서 이전 실행을 추적할 수 있도록 해둔 상태입니다.
- 확인된 개선점
  1. Langfuse URL이 없는 경우(내부 span 생성 실패) UI에는 `—`만 노출되므로 사용자가 추가 조치를 알기 어렵습니다.
  2. Trace ID는 history·queue 양쪽에 그대로 노출되지만, 복사 액션이 없어 운영자가 값을 가져가기가 불편합니다.
  3. Langfuse span 메타에 `rag_mode`, `scope`, `judgeDecision` 등을 추가하면 향후 Evidence diff 분석에 도움이 됩니다. 현재 `_perform_reindex` metadata에는 `status`, `taskId`, `queueId`만 포함되어 있습니다.
- 업데이트: `_perform_reindex`에서 `retryMode`, `ragMode`, `scopeDetail`을 Langfuse metadata와 감사 로그에 기록하고, UI에는 Trace ID 복사 버튼과 링크 부재 안내 문구를 추가했습니다.
- 업데이트: 재색인 종료 시 EvidenceSnapshot을 조회해 `created`·`updated` 요약과 샘플을 `evidenceDiff`로 누적하고, Admin 패널 상세 뷰에 강조 배지를 노출합니다.

## 4. 자동 재시도 규칙 요구사항 확정
- **결정한 규칙**
  1. **기본 시도 횟수**: 실패한 큐 항목은 최대 3회까지 자동 재시도합니다.
  2. **쿨다운**: 마지막 시도 후 30분 동안은 동일 큐 항목에 대한 자동 재시도를 지연합니다.
  3. **즉시 성공 기록**: 재시도 성공 시 `lastSuccessAt`에 타임스탬프를 남기고, `status`를 `completed`로 업데이트합니다.
  4. **Langfuse 연동**: 자동 재시도로 생성된 작업은 metadata에 `retryMode: "auto"`를 추가하고, 토스트/감사 로그에서도 “자동 재시도” 문구를 사용합니다.
- **추가 확인 필요**
  - 큐 항목별 사용자 메모(`note`)를 자동 재시도에서 유지할지 업데이트할지 정책 결정.
  - 동일 스코프(all)에서 동시 다발 재색인 시 충돌을 어떻게 방지할지(대기열 락 vs. 병렬 허용) 논의 필요.

## 5. Evidence diff 하이라이트 요구사항
- 현재 RAG 패널에는 Evidence diff UI가 없으며, 챗 경험에서만 `EvidencePanel`이 diff 타입(`added`, `removed`, `changed`)을 표시합니다.
- 향후 구현 방향
  1. 재색인 히스토리에서 Evidence 수집 결과와 이전 버전을 비교할 때 **anchor URN**·**sourceReliability** 정보를 함께 수집해야 합니다.
  2. UI는 `AdminRagPanel` 하단에 “Evidence 변화” 섹션을 추가하고, `diffType`에 따라 색상(친근한 사회적 기업 톤의 긍정/주의/위로 컬러)을 매핑합니다.
  3. Evidence 비교를 위해 RAG 재색인 결과를 저장하는 별도 스냅샷 스토리지(예: `uploads/admin/rag_evidence_snapshot/<taskId>.json`)가 필요합니다.
- 준비 작업
  - 백엔드: RAG 파이프라인에서 재색인 완료 시 새 Evidence 목록을 JSON으로 떨어뜨리고, 이전 버전과의 diff를 계산하는 헬퍼 작성.
  - 프런트: diff 데이터 구조(예: `diffItems: Array<{ urnId: string; diffType: "added" | "removed" | "changed"; summary: string }>`})를 정의하고, React Query cache 키를 설계합니다.

## 6. 추가 검증 및 TODO
- [x] Langfuse metadata에 `rag_mode`, `retryMode`, `scopeDetail`(선택된 소스 배열)을 기록하도록 백엔드 수정.
- [x] 자동 재시도 트리거를 Celery beat 또는 FastAPI 백그라운드 작업으로 구현하는 방안 비교.
- [ ] Evidence diff 계산에 필요한 스냅샷 포맷을 `schemas/api/admin.py`에 정의.
- [ ] UI 토스트 문안을 ‘친근한 사회적 기업’ 톤으로 정리(예: “조금 전 재색인을 다시 시도했어요. 결과를 잠시만 기다려 주세요!”).

---
다음 단계에서는 위 요구사항을 토대로 API·스토리지·UI 변경 분을 설계도에 반영하고, 자동 재시도 스케줄러와 Evidence diff 뷰 구현에 착수할 예정입니다.
