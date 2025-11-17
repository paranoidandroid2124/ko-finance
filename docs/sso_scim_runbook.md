# SSO & SCIM Rollout Runbook

## 1. Service Overview

| Component | Endpoint | Notes |
| --- | --- | --- |
| **SAML 2.0** | `POST /api/v1/auth/saml/{provider}/acs`, `GET /api/v1/auth/saml/{provider}/metadata` | Providers are created with `/api/v1/admin/sso/providers`; fallback `/api/v1/auth/saml/acs` uses the legacy env config. |
| **OIDC** | `GET /api/v1/auth/oidc/{provider}/authorize` → `GET /api/v1/auth/oidc/callback` | State now carries `providerSlug`. Use the admin API to rotate client ids/secrets. |
| **SCIM v2 (Users/Groups)** | `/scim/v2/Users`, `/scim/v2/Groups` | Bearer tokens are issued per provider via `/api/v1/admin/sso/providers/{id}/scim-tokens`. |

## 2. Configuration Checklist

1. **State/nonce secrets**
   - `AUTH_SSO_STATE_SECRET` (or reuse `AUTH_JWT_SECRET`) – keep in 1Password.
   - `AUTH_SSO_STATE_TTL_SECONDS` default 600s; increase only if IdP latency >10m.
2. **Provider registry**
   - Call `POST /api/v1/admin/sso/providers` with the org slug, issuer, ACS/Authorize URLs, and attribute mapping. Repeat per tenant (use `slug` to identify).
   - Upload certificates or client secrets via `POST /api/v1/admin/sso/providers/{id}/credentials`.
   - Optional: auto-provision orgs by setting `autoProvisionOrgs=true` or overriding default plan/role per provider.
3. **SCIM tokens**
   - Generate per-provider tokens with `POST /api/v1/admin/sso/providers/{id}/scim-tokens`. Store the plaintext token securely (it is shown once).
   - Use `GET /api/v1/admin/sso/providers/{id}/scim-tokens` to audit prefixes/expiry and rotate as needed.
4. **Fallback / legacy**
   - The old env-vars (`AUTH_SAML_*`, `AUTH_OIDC_*`, `SCIM_BEARER_TOKEN`) are still loaded as the “default” provider for small installs. Plan the migration by creating a matching provider via the admin API, then switching clients to `/auth/saml/{slug}` and `/auth/oidc/{slug}` endpoints.
5. **Deployment**
   - Apply `20251115_create_sso_providers.sql` in every environment.
   - Run `docker compose down && docker compose up -d` after adding new providers or rotating credentials so caches clear cleanly.

## 3. Pilot Status (Target: 3 Design Partners)

| Org | Channel | Status | Next Action |
| --- | --- | --- | --- |
| **Hanseong Securities** | SAML + SCIM | Metadata exchanged, user create/delete validated. Need to finalize group→`org_slug` mapping before enabling auto-provision. |
| **Toss Card** | OIDC + SCIM | OIDC authorize/callback verified in staging; waiting on SCIM provisioning token approval from security (ETA 11/20). |
| **Mirae Asset WM** | SAML only (manual SCIM) | IdP ready but RBAC shadow issues still 2.1% – run 48h selective enforcement soak before turning on global flag. |

> Track pilots in Ops sheet + #ops-support. Update this table after every enablement or incident.

## 4. Rollback / Recovery

1. **Disable login**
   - Disable specific providers via `PATCH /api/v1/admin/sso/providers/{id}` (`enabled=false`) and recycle pods to flush caches.
   - Revoke SCIM tokens via the admin API; removing the token immediately blocks provisioning.
2. **User quarantine**
   - `DELETE /scim/v2/Users/{id}` → marks user inactive (sets `locked_until = 'infinity'`).
   - Remove org memberships manually via `DELETE FROM user_orgs WHERE user_id=...` if SCIM unavailable.
3. **RBAC incidents**
   - Flip `RBAC_ENFORCE=false` to fall back to shadow mode.
   - Re-enable per-endpoint `enforce=True` toggles once root cause is fixed.

## 5. Observability

- **Logs**: `audit_logs` (`source=rbac|auth|scim`) aggregated into Looker tile “RBAC/SSO”.
- **Metrics**: `sso_login_total{protocol,provider,result}` and `scim_requests_total{provider,resource,method,result}` (available via `/metrics`).
- **Alerts**:
  - SCIM 5xx rate >2/min for 5 minutes → page #ops-support.
  - RBAC shadow rate >1% while `RBAC_ENFORCE=false` → create incident.

Keep this runbook alongside the environment spreadsheet so infra + CS can fast-follow the rollout.
