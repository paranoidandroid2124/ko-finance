# RAG 재색인 운영 체크리스트

재색인 작업이 완료될 때마다 아래 순서를 따라 후속 조치를 수행합니다.
이 문서는 `/api/v1/admin/rag/reindex` 플로우와 `uploads/admin` 스토리지를 기준으로 작성되었습니다.

## 1. Langfuse 상태 점검
- [ ] 재색인 Task ID에 대응하는 span이 `completed` 상태인지 확인한다.
- [ ] 오류율이 5% 이상이거나 `failed` 상태가 있으면 Slack `#ops-alerts` 채널에 공유한다.
- [ ] Retry 작업인 경우 `previousTraceId`·`previousSpanId`가 metadata에 연결되어 있는지 확인한다.

## 2. 감사 로그 확인
- [ ] `rag_event_brief_generated` 항목에 Task ID·scope·actor가 기록되었는지 확인한다.
- [ ] `rag_audit.jsonl`에 추가된 payload의 `pdfObject`, `zipObject` 값이 비어 있지 않은지 검증한다.
- [ ] 이상이 있으면 `services/admin_audit.append_audit_log` 호출 로그를 확인하고 재실행한다.

## 3. 첨부 및 링크 검증
- [ ] `uploads/admin/event_briefs/{taskId-*}` 디렉터리에 `event_brief.pdf`, `event_brief.json`, `evidence_package.zip`, `manifest.json`이 존재한다.
- [ ] MinIO/GCS presigned URL이 200 응답을 반환하며 만료까지 6시간 이상 남아 있다.
- [ ] 필요 시 `scripts/render_daily_brief.py --task-id ... --verify` 명령으로 재검증한다.

## 4. 워치리스트 영향 파악
- [ ] `services/watchlist_service.collect_watchlist_alerts` 결과에서 재색인 대상 scope가 포함된 최근 이벤트를 확인한다.
- [ ] 영향도가 높은 경우 워치리스트 다이제스트 재전송 혹은 고객 알림이 필요한지 판단한다.
- [ ] 조치가 필요하면 `templates/email/watchlist_digest.html.jinja` 기반 템플릿으로 공지 초안을 작성한다.

## 5. Admin 패널 반영
- [ ] `/api/v1/admin/rag/reindex/history` UI에서 상태가 `completed`로 표시되는지 확인한다.
- [ ] Queue에 잔류 중인 동일 scope 항목이 있다면 `remove_rag_reindex_queue_entry` 혹은 재시도를 수행한다.
- [ ] `ops_run_history.jsonl`에 해당 Task ID가 기록되었는지 확인하고, 없으면 `services/admin_ops_service.append_run_history`를 호출한다.

## 6. 기록 & 보고
- [ ] 체크리스트 결과를 `docs/ops/run-log.md` 또는 Ops Notion 보드에 `{날짜, Task ID, 담당자, 비고}`로 남긴다.
- [ ] 장애·재시도 발생 시 회고 항목을 추가로 작성하고 다음 스탠드업에서 공유한다.

---

### 자동화 메모
- Celery/Cloud Scheduler에 재색인 완료 Webhook이 있을 경우 Slack Workflow로 본 체크리스트를 담당자에게 전달하도록 설정한다.
- 장기적으로는 `scripts/sync_audit_traces.py`나 별도 Ops 봇에서 1~5단계 상태를 자동 체크 후 결과만 사람이 확인하도록 개선할 수 있다.
