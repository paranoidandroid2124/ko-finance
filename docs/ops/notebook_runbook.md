## Research Notebook 운영 & 모니터링 가이드

### 1. 목표
- 조직 단위 Workspace(공유 워치리스트 + 노트북) 가시화
- Notebook API/RBAC 위반 조기 탐지
- Slack/Help Center에 전달할 사용자 대응 메시지 정리

### 2. 데이터 소스
| 항목 | 위치 | 비고 |
| --- | --- | --- |
| 워크스페이스 API | `GET /api/v1/workspaces/current` | org_id 헤더 필수 (`X-Org-Id`). FE에서 팀 첫 화면 진입 시 호출. |
| 감사 로그 | `audit_logs.action = 'collab.notebook.*'` | create/update/delete/share/access 이벤트 구분. |
| RBAC Shadow 이벤트 | `audit_logs.action LIKE 'rbac.shadow.%'` | Notebook 엔드포인트 미스/권한 오류 추적. |
| Watchlist 집계 | `services.watchlist_aggregator` | 워크스페이스 응답에서 `watchlists` 필드로 노출. |

### 3. Grafana 대시보드 구성
1. **Notebook 사용량 패널**
   - 쿼리: `count_over_time({action="collab.notebook.entry.create"}[$__interval])`
   - breakdown: org_id, user_id 별로 topN.
2. **Workspace API 오류율**
   - FastAPI access 로그 기반 `status >= 400` 비율.
   - 400/403가 spike 나면 헤더 누락 혹은 플랜 미스매치 가능.
3. **RBAC Shadow 모니터링**
   - 지표: `sum by (reason) (increase(audit_logs_total{source="rbac", action="rbac.shadow.issue"}[$__interval]))`
   - Notebook 릴리스 이후 48h 동안 `X-Org-Id` 누락 비율을 집중 모니터링.

### 4. 운영 체크리스트
1. **워크스페이스 API 점검**
   - `curl /api/v1/workspaces/current -H "X-Org-Id=..." -H "X-User-Id=..." -H "X-Plan-Entitlements=collab.notebook"`로 응답 확인.
   - members/notebooks/watchlists 배열이 비어 있으면 org_id/plan을 재확인.
2. **Plan 엔타이틀먼트 검증**
   - Notebook 기능은 `collab.notebook` 권한 필요.
   - Pro/Enterprise 조직은 admin 콘솔 혹은 `uploads/admin/plan_config.json`에 해당 엔타이틀먼트가 존재해야 함.
3. **Audit Trail 보존**
   - Notebook/Entry/Share 조작 시 모두 `collab.notebook.*` 이벤트 발생.
   - 주 1회 Looker 추출로 외부 공유 링크 생성·만료 이력 확인.
4. **Help Center 문서 링크**
   - `docs/domain/research_notebook_api.md`와 본 Runbook을 >Help Center·FE QA 팀에 전달.
   - FAQ: “노트북을 공유했는데 상대가 비밀번호 입력창만 본다” → `/notebooks/shares/access` 이벤트 및 `password_required` 오류 안내.

### 5. Incident 대응
| 사례 | 조치 |
| --- | --- |
| 워크스페이스 응답 403 | 플랜 엔타이틀먼트 확인, trial 계정이면 `X-Plan-Entitlements` 헤더 설정 여부 확인 |
| Notebook 엔드포인트 401/403 | `X-User-Id`, `X-Org-Id` 헤더 누락 여부와 RBAC shadow 로그 확인 |
| 공유 링크 오남용 | `notebook_shares`에서 해당 token revoke → `collab.notebook.share.revoke` 감사 이벤트로 기록 |

### 6. 향후 Todo
- Workspace API에 watchlist rule/channel 세부 정보를 단계적으로 추가.
- Slack/Teams Webhook으로 Notebook 생성/공유 이벤트 알림.
- RBAC enforce 단계 진입 전 Notebook 엔드포인트 전용 smoke 테스트 자동화.
