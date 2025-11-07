- [ ] Configure GCS bucket lifecycle: keep Standard 7 days then transition/delete (daily-brief prefix).
- [ ] Schedule Celery task m4.cleanup_daily_briefs daily with 7-day retention for PDFs/ZIPs.
- [ ] Migrate storage provider to GCS (set STORAGE_PROVIDER=gcs, supply service account, verify).
- [ ] Set GCS lifecycle rule for daily-brief/ prefix (Standard ? Coldline/Deletion after 7 days).
- [ ] 설계: 워치리스트 다이제스트 즐겨찾기/최근 대상 백엔드 저장 API (계정 단위 동기화)
- [ ] Introduce shared storage/config repository layer so local uploads/ usage can later swap to Firestore/GCS with minimal app changes.
- [ ] Mirror .state/ cursor persistence behind the same abstraction; target Firestore document (sync_state/{name}) once on GCP.
- [ ] Plan secrets migration: move Langfuse/API keys into Secret Manager and load via Cloud Run env injection.
- [ ] Replace ops_api_keys file store with OpsSecretStore abstraction backed by Secret Manager (console writes call add_secret_version, metadata in Firestore).

