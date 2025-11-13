# SSO & SCIM Rollout Runbook

## 1. Service Overview

| Component | Endpoint | Notes |
| --- | --- | --- |
| **SAML 2.0** | `POST /api/v1/auth/saml/acs` + `GET /api/v1/auth/saml/metadata` | Accepts HTTP-POST bindings, asserts are parsed via attribute mapping (`AUTH_SAML_*`). |
| **OIDC** | `GET /api/v1/auth/oidc/authorize` → `GET /api/v1/auth/oidc/callback` | Generates signed state + nonce (`AUTH_SSO_STATE_*`), exchanges code via provider token/userinfo endpoints. |
| **SCIM v2 (Users/Groups)** | `/scim/v2/Users`, `/scim/v2/Groups` | Protected via `SCIM_BEARER_TOKEN`, maps resources to `users` / `orgs` / `user_orgs`. |

## 2. Configuration Checklist

1. **State/nonce secrets**
   - `AUTH_SSO_STATE_SECRET` (or reuse `AUTH_JWT_SECRET`) – keep in 1Password.
   - `AUTH_SSO_STATE_TTL_SECONDS` default 600s; increase only if IdP latency >10m.
2. **SAML Provider (per tenant)**
   - `AUTH_SAML_SP_ENTITY_ID`, `AUTH_SAML_ACS_URL`, `AUTH_SAML_METADATA_URL`.
   - Upload X.509 signing cert via `AUTH_SAML_SP_CERT` if IdP requires.
   - Map attributes (email/name/orgSlug/role) using `AUTH_SAML_*_ATTRIBUTE`.
   - Optional org auto-provision via `AUTH_SAML_AUTO_PROVISION_ORG=true`.
3. **OIDC Provider**
   - Set `AUTH_OIDC_*` endpoints plus `AUTH_OIDC_SCOPES`.
   - Configure redirect URI (default `http://localhost:8000/api/v1/auth/oidc/callback`).
   - Customize attribute → RBAC role via `AUTH_OIDC_ROLE_MAPPING`.
4. **SCIM**
   - Issue long-lived token in vault and set `SCIM_BEARER_TOKEN`.
   - Bound page size with `SCIM_MAX_PAGE_SIZE` (default 100).
   - Optional org auto-creation with `SCIM_AUTO_PROVISION_ORG=true`.
5. **Deployment**
   - Document new env vars in `README.md` and run `docker compose down && docker compose up -d` whenever toggles change.

## 3. Pilot Status (Target: 3 Design Partners)

| Org | Channel | Status | Next Action |
| --- | --- | --- | --- |
| **Hanseong Securities** | SAML + SCIM | Metadata exchanged, user create/delete validated. Need to finalize group→`org_slug` mapping before enabling auto-provision. |
| **Toss Card** | OIDC + SCIM | OIDC authorize/callback verified in staging; waiting on SCIM provisioning token approval from security (ETA 11/20). |
| **Mirae Asset WM** | SAML only (manual SCIM) | IdP ready but RBAC shadow issues still 2.1% – run 48h selective enforcement soak before turning on global flag. |

> Track pilots in Ops sheet + #ops-support. Update this table after every enablement or incident.

## 4. Rollback / Recovery

1. **Disable login**
   - Set `AUTH_SAML_ENABLED=false` or `AUTH_OIDC_ENABLED=false` and recycle containers.
   - Rotate `SCIM_BEARER_TOKEN` if leaked; removing the value blocks provisioning immediately.
2. **User quarantine**
   - `DELETE /scim/v2/Users/{id}` → marks user inactive (sets `locked_until = 'infinity'`).
   - Remove org memberships manually via `DELETE FROM user_orgs WHERE user_id=...` if SCIM unavailable.
3. **RBAC incidents**
   - Flip `RBAC_ENFORCE=false` to fall back to shadow mode.
   - Re-enable per-endpoint `enforce=True` toggles once root cause is fixed.

## 5. Observability

- **Logs**: `audit_logs` (`source=rbac|auth|scim`) aggregated into Looker tile “RBAC/SSO”.
- **Metrics**: add counters `sso.saml.login.success`, `sso.oidc.login.success`, `scim.users.provisioned`.
- **Alerts**:
  - SCIM 5xx rate >2/min for 5 minutes → page #ops-support.
  - RBAC shadow rate >1% while `RBAC_ENFORCE=false` → create incident.

Keep this runbook alongside the environment spreadsheet so infra + CS can fast-follow the rollout.
