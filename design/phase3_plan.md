# Phase 3 Plan — Pro/Enterprise Feature Enablement

> Timebox: 2025-12-05 ? 2025-12-19 · Owner: TBD · Status: Draft

## 1. Scope & Goals
- Deliver plan-specific functionality (alerts, peer comparison exports, upgrade flows) layered on Phase 1–2 foundations.
- Implement payment/plan awareness in the dashboard UI, including lock interactions and upgrade CTAs.
- Add alert scheduling and notification delivery for filings/news/sector triggers.
- Introduce evidence snapshot retention & archival pipeline aligned with legal/plan policies.
- Out-of-scope: Full billing backend (handled separately), enterprise SSO onboarding.

## 2. Deliverables
| Deliverable | Type | Target Path | Notes |
| --- | --- | --- | --- |
| Plan context provider | Frontend infra | web/dashboard/src/store/planStore.ts | Expose planTier, feature flags |
| Lock/Upgrade components | Component | web/dashboard/src/components/ui/PlanLock.tsx | Shimmer animation, tooltip copy |
| Alert builder modal | Component | web/dashboard/src/components/alerts/AlertBuilder.tsx | Conditions for sentiment/returns/news |
| Peer comparison export | Component/API | web/dashboard/src/components/company/PeerTable.tsx, web/routers/companies.py | CSV export & audit logging |
| Notification worker tasks | Backend | parse/tasks.py, services/notification_service.py | Schedule & send alerts |
| Evidence snapshot retention pipeline | Backend/Data | services/evidence_service.py, parse/tasks.py, infra (Cloud Scheduler/Run) | Prune >90d snapshots, archive to GCS, enforce DSAR deletes |
| Analytics events | Instrumentation | web/dashboard/src/lib/analytics.ts | Track upgrade clicks, lock views |
| Documentation update | Doc | design/phase3_release_notes.md | Feature summary, plan matrix |

## 3. Workstreams
### 3.1 Design / UX
- Finalize upgrade modal, pricing comparison banner, and lock icon states with copy variations by plan.
- Design alert builder flow (stepper vs single modal) including success toasts and error handling.
- Provide tooltip microcopy for locked actions referencing unique value props.

### 3.2 Frontend Implementation
- Implement plan context with SSR hydration; ensure fallback to Free when unknown.
- Wire lock component across search cards, evidence panel exports, peer table buttons.
- Build alert builder modal with form validation, schedule preview, persistence via React Query.

### 3.3 Backend / Data
- Define alert schema (table for triggers, thresholds, channels, plan tier) and migrations.
- Implement API endpoints (POST /alerts, GET /alerts) with plan validation and rate limits.
- Integrate with notification channels (email/Telegram) leveraging existing infrastructure; log deliveries.
- Build retention job: generate policy window per plan, move cold data to GCS, hard-delete expired/DSAR snapshots.
- Instrument storage usage dashboards + alerts (Cloud Monitoring + BigQuery exports).

### 3.4 QA & Docs
- Create plan-switch test scenarios (simulate Free?Pro?Enterprise) verifying UI gating.
- Run end-to-end tests for alert creation, firing, and user notification receipt.
- Update documentation: pricing matrix, feature availability chart, alert usage guide.
- Document evidence snapshot retention SOP (product + legal) and DSAR runbook.

## 4. Data Requirements
- Alerts: target_type (filing/news/sector), trigger_metric, operator, threshold, cooldown_minutes, channel.
- Plan store: plan_tier, expires_at, entitlements array for future flexibility.
- Export audit: store user_id, plan_tier, export_type, timestamp, row_count.
- Evidence retention: snapshot_urn_id, snapshot_hash, created_at, plan_tier, storage_location, expires_at, deletion_processed_at.

## 5. Plan Lock Mapping
| Feature | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Alert builder | ? | ? (email) | ? (email + webhook) |
| Peer CSV export | ? | ? (up to 100 rows) | ? (full) |
| Evidence bundle export | ? | ? | ? |
| Upgrade modal | ? (CTA) | ? (manage) | ? (manage) |
| Analytics usage dashboard | ? | ? | ? |

## 6. Risks & Mitigations
- Alert noise leading to churn ? Mitigation: enforce cooldown, default sensible thresholds, include preview before saving.
- Plan detection mismatch (backend vs frontend) ? Mitigation: single source of truth (API), fallback to Free if mismatch, add logging.
- Lock UI frustration ? Mitigation: provide inline value summary, link to documentation, avoid hard blocks on navigation.
- Retention policy drift / compliance gaps ? Mitigation: codify policy in config, add monitoring and periodic audit with legal sign-off.

## 7. Milestones & Checkpoints
| Milestone | Expected Date | Owner | Status |
| --- | --- | --- | --- |
| Upgrade UX finalized | 2025-12-07 | Design | Planned |
| Plan store integrated | 2025-12-09 | Frontend | Planned |
| Alert schema & API ready | 2025-12-12 | Backend | Planned |
| Lock components applied across app | 2025-12-15 | Frontend | Planned |
  | Evidence retention job live (prune + archive) | 2025-12-16 | Backend/Data | Planned |
| Alert E2E test pass | 2025-12-18 | QA | Planned |

## 8. QA Checklist
- Functional: lock badges appear correctly, upgrade modal triggers analytics, alert creation + firing works per plan tier.
- Accessibility: lock tooltips readable, focus trapping in alert modal, screen reader announcements.
- Performance: alert creation API < 500ms, lock animation under 220ms, no re-render thrash when plan changes.
- Data retention: regression for snapshot pruning, GCS archive upload, DSAR wipe end-to-end.
- Analytics/logging: upgrade CTA click event, alert fired event with trigger metadata, export audit log.

## 9. Sign-offs
- Design | Product | Engineering | Compliance

---
- Notes: coordinate with billing/finance team on entitlement mapping before release cutoff. Align evidence snapshot retention policy with legal/compliance prior to launch.
