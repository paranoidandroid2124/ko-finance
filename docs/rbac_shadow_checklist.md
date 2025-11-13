# Light RBAC Shadow → Enforce Checklist

The RBAC middleware now runs for every `/api/v1` request. While `RBAC_ENFORCE=false`, requests are allowed but audit
events tagged with `source=rbac` are emitted for every inconsistency. Use the following checklist before flipping
`RBAC_ENFORCE=true` or enabling per-endpoint enforcement.

## 1. Instrumentation & Monitoring

- [ ] **Audit log monitor** – Create a Grafana/Looker tile filtered on `action IN ('rbac.shadow.issue','rbac.shadow.membership_missing','rbac.shadow.role_insufficient')`.
- [ ] **Alert** – Page on-call if shadow issues > 20/min or spikes 3× baseline.
- [ ] **Sampling** – Export weekly CSV of audit events (path, method, reason) to spot missing `X-Org-Id` headers.
- [ ] **Metrics** – Optional OTEL counter `rbac.shadow.issues.total` for faster dashboards.

## 2. Data Backfill & Validation

- [ ] Run `ops/migrations/add_light_rbac.sql` in staging/prod and confirm `orgs`, `user_orgs`, `org_roles` populated.
- [ ] Execute `SELECT COUNT(*) FROM user_orgs WHERE status != 'active';` to understand pending/revoked share.
- [ ] For legacy users without orgs, call `rbac_service.ensure_personal_org(user_id)` via a one-off script or trigger it
      through the `/api/v1/orgs/me/memberships` flow to create personal workspaces.
- [ ] Verify `org_subscriptions` rows now reference valid `orgs.id`.

## 3. Client Readiness

- [ ] Web dashboard/CLI include `X-User-Id` + `X-Org-Id` on every authenticated call.
- [ ] Ensure service accounts/batch jobs either include headers or call `require_org_role(..., enforce=False)` dependencies.
- [ ] Document default org usage for personal plans (if header omitted we stay in per-user mode).

## 4. Enforcement Playbook

1. **Shadow soak (Week 0-1)** – Keep `RBAC_ENFORCE=false` and focus on cleaning up `rbac.shadow.*` audit events.
2. **Selective enforce (Week 2)** – For critical mutations (`/orgs/*`, `/alerts/*`, `/reports/*`) call `require_org_role(..., enforce=True)` so violations fail fast without flipping the global switch.
3. **Per-service bake (Week 3)** – Turn on enforcement for low-risk GET endpoints and ensure service accounts/cron jobs always send `X-Org-Id` + `X-User-Id`.
4. **Global enforce (Week 4)** – Flip `RBAC_ENFORCE=true` once <1% of traffic triggers shadow issues for 48h. Keep per-endpoint `enforce=True` calls in place for future regression tests.

## 5. Regression Tests

- [ ] API tests cover: missing headers (401), mismatched org (400), insufficient role (403), inactive membership (403),
      happy-path viewer/editor/admin flows.
- [ ] Load-test ensures middleware adds <2ms per request.
- [ ] Invite & role-change endpoints emit `audit_logs` entries (`rbac.membership.upsert/update`).

Keep this file updated whenever we tweak RBAC behaviour or rollout strategy.
