# Event Study Export Runbook

Event Study PDF/ZIP Export는 `reports.event_export` 엔타이틀먼트와 `timeline.full` 권한을 모두 보유한 사용자가 이벤트 스터디 결과를 PDF와 증거 ZIP으로 내려받을 수 있게 해 주는 기능입니다. 이 문서는 운영팀이 해당 기능을 관리할 때 확인해야 하는 설정, 보관 정책, 모니터링 지표를 정리합니다.

## 1. RBAC / 플랜 노출

- 백엔드는 `services/plan_guard.ensure_entitlement("reports.event_export")` 체크를 사용합니다. 플랜이 권한을 갖고 있지 않으면 `plan.entitlement_required` 오류와 함께 `"이벤트 리포트 Export (Pro+)"` 메시지를 돌려줍니다.
- 프론트엔드는 `usePlanStore().featureFlags.reportsEventExport` 플래그를 기반으로 Export 버튼 활성화 여부를 결정하고, 플랜 요약/마케팅 카드에 “Event Study 리포트를 PDF·ZIP으로 내보내기” 항목을 추가했습니다.
- 운영자가 플랜 설정 UI (`PlanSettingsForm`)에서 엔타이틀먼트를 직접 부여하려면 “이벤트 리포트 Export” 항목을 체크하면 됩니다.

## 2. 저장 위치 및 보관 정책

- 생성된 PDF/ZIP, manifest, trace JSON 등은 기본적으로 `EVENT_BRIEF_OUTPUT_DIR` (기본값 `uploads/admin/event_briefs`) 아래의 타임스탬프 폴더에 저장됩니다.
- MinIO/S3 업로드 시 객체 prefix는 `EVENT_BRIEF_OBJECT_PREFIX` (기본값 `event-briefs`)를 따릅니다.
- 로컬 보관 기간은 `.env`의 `EVENT_BUNDLE_RETENTION_DAYS`로 제어합니다. 0으로 설정하면 정리가 비활성화되고, 양수면 해당 일수보다 오래된 디렉터리를 삭제합니다. `.env.example`에 주석과 기본값(30일)이 포함돼 있으니 환경 변수를 잊지 말고 맞춰 주세요.
- `EVENT_BUNDLE_RETENTION_DAYS` 변경 후에는 API 프로세스를 재시작해야 새 값을 읽습니다.
- **환경별 확인 절차**
  - `prod`, `staging`, `dev` 등 각 배포 환경의 `.env`(혹은 Secret Manager)에서 위 세 개 변수가 모두 설정돼 있는지 체크합니다.
  - IaC 또는 배포 파이프라인 템플릿에 변수가 누락돼 있다면 PR을 열어 기본값을 추가하고, 적용 이후 `printenv | grep EVENT_BUNDLE` 등으로 런타임 값을 검증합니다.

## 3. 삭제 배치와 모니터링

- `services/evidence_package._purge_expired_bundles`가 신규 번들을 만들 때마다 보관 기간보다 오래된 폴더를 정리합니다.
- 정리 결과는 Prometheus에 다음 메트릭으로 노출됩니다(`services/report_metrics.py`):
  - `event_bundle_cleanup_total{result="deleted|failed"}` : 삭제 성공/실패 횟수.
  - `event_bundle_directories` : 현재 로컬에 남아 있는 번들 디렉터리 수.
  - `event_bundle_retention_days` : 현재 적용 중인 보관 일수.
- Grafana 대시보드 정의 `configs/grafana/event_export_dashboard.json`을 불러오면 다음 패널이 생성됩니다.
  1. **Deleted bundles (15m rate)** : `increase(event_bundle_cleanup_total{result="deleted"}[15m])`
  2. **Cleanup failures** : `increase(event_bundle_cleanup_total{result="failed"}[15m])`
  3. **Bundle directories** : `event_bundle_directories`
  4. **Retention window** : `event_bundle_retention_days`
- 대시보드는 5분/15분 이동평균으로 삭제율과 실패를 모니터링하고, 남은 디렉터리 수가 계속 늘어나는지 확인하는 용도로 사용합니다.

## 4. 운영 체크리스트

1. **샘플 Export**  
   - `/labs/event-study` 화면에서 Pro 플랜 계정을 사용해 Export를 실행합니다. 토스트가 presigned URL을 안내하는지와 생성된 PDF/ZIP 구조를 확인합니다.
2. **보관 디렉터리 확인**  
   - `ls uploads/admin/event_briefs` 혹은 `find uploads/admin/event_briefs -maxdepth 1 -type d` 명령으로 생성 시각별 폴더를 점검합니다.
   - `EVENT_BUNDLE_RETENTION_DAYS`보다 오래된 폴더가 자동으로 제거되는지 로그(`Removed expired event bundle directory ...`)를 확인합니다.
3. **Grafana**  
   - Export 후 5~10분 내에 `event_bundle_directories` 값이 증가했다가 유지되는지, `event_bundle_cleanup_total` 그래프에 삭제 이벤트가 찍히는지 확인합니다.
4. **Plan/RBAC 메시지**  
   - Free/Starter 계정으로 Export 버튼을 눌러 “이벤트 리포트 Export (Pro+)” 오류가 노출되는지 확인해 업셀 메시지가 정상인지 검증합니다.

이 가이드는 운영/온콜 문서에 포함되어야 하며, Grafana 패널과 `.env` 설정을 함께 점검해야 안정적으로 Event Study Export 기능을 제공할 수 있습니다.

## 5. Grafana Import & Alert Rule 가이드

1. 운영 Grafana에 로그인한 뒤 **Dashboards → New → Import → Upload JSON file** 순서로 `configs/grafana/event_export_dashboard.json`을 업로드하고, 데이터 소스로 Prometheus 인스턴스를 선택합니다.
2. 각 패널(Deleted bundles, Cleanup failures, Bundle directories)에 대해 **Create alert rule**을 선택하여 임계값을 설정합니다. 예시:
   - Deleted bundles: `increase(event_bundle_cleanup_total{result="deleted"}[6h]) < 1` → 정리 작업이 멈추면 Warning.
   - Cleanup failures: `increase(event_bundle_cleanup_total{result="failed"}[15m]) > 0` → Slack/PagerDuty Critical.
   - Bundle directories: `event_bundle_directories > 200` → 디스크 누적 경고.
3. Alert rule 이름/폴더는 `Reports/EventStudy` 등으로 통일하고, Notification policy에 Slack·이메일을 연결합니다. 추후 운영 데이터를 보면서 임계값을 재조정하세요.
4. 운영 Grafana 설정과 저장소 JSON이 일치하도록, 변경 후 `git add configs/grafana/event_export_dashboard.json` 상태를 유지하고 PR에서 리뷰받습니다.
