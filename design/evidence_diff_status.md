# Evidence Diff Status (Updated 2025-11-27)

## 1. Current Snapshot
- **Phase 2** work to expose diff metadata end-to-end is functionally complete: `/rag/query` now returns previous anchor/quote data, the dashboard renders diff badges & removed evidence banners, and Storybook has diff on/off scenarios.
- TimelineSparkline hover linking and mark line highlights landed; no further Phase 2 polish planned.
- Evidence snapshot retention has *not* been implemented yet—snapshots continue to accumulate without pruning.

## 2. Completed Deliverables
- RAG API & schema (`schemas/api/rag.py`, `web/routers/rag.py`): added `meta.evidence_diff`, previous anchors, and diff types.
- Snapshot capture pipeline (`parse/tasks.py`, `services/evidence_service.py`): normalizes metadata and stamps diff status.
- Frontend diff UI (`web/dashboard/src/components/evidence/EvidencePanel.tsx` + store/stories/tests): diff toggle, removed evidence callout, telemetry for usage.
- QA assets updated (`design/qa_phase2_matrix.md`, pytest & vitest suites) to cover diff toggles and retention telemetry placeholders.

## 3. Outstanding / Next Phase (Phase 3)
- **Retention & cleanup**: define policy with Product & Legal, implement pruning + archival job (Cloud Scheduler → Cloud Run), ensure DSAR deletions span hot/warm/cold storage.
- **TimelineSparkline**: ongoing enhancements (if any) will be tracked with Phase 3 alerts/retention scope.
- **Docs & runbooks**: finalize retention SOPs, update Phase 3 release notes with diff/alert interplay.

## 4. Open Questions for Product & Legal
1. How long should evidence history stay user-visible (e.g., 90 days)?
2. What archival window (e.g., additional 6 months) is required for audit/legal defense?
3. What’s the DSAR SLA for removing evidence snapshots across hot + archival storage?
4. Are there plan-tier differences (e.g., Enterprise needs longer retention)?

Answers to the above feed directly into the Phase 3 retention deliverables (see `design/phase3_plan.md`). Once confirmed, we can schedule the automation work and close out the remaining Phase 2 UI polish.
