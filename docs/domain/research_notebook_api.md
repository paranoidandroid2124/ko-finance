## Research Notebook API – Entitlements, RBAC, and Limits

This note captures the **backend contract** for `/api/v1/notebooks*`. Use it when coordinating FE wiring, QA checklists, or customer-facing docs.

### Access model
- **Plan entitlement**: every authenticated endpoint now requires `collab.notebook` via `require_plan_feature`. Plans without that entitlement receive `403` with `{"code":"plan.entitlement_required","feature":"collab.notebook"}`.
- **Headers**: `X-Org-Id` and `X-User-Id` are mandatory. Missing or malformed values raise `notebook.org_required` / `notebook.user_required`.
- **RBAC**: the router reuses `require_org_role`:
  - `viewer`: list + get notebook detail.
  - `editor`: create/update/delete notebooks, entries, shares.
  - Public share access (`POST /api/v1/notebooks/shares/access`) is the only unauthenticated endpoint and does **not** require plan/RBAC.

| Endpoint | Method | Notes | Min role | Plan entitlement |
| --- | --- | --- | --- | --- |
| `/api/v1/notebooks` | GET | org-scoped list w/ filters | viewer | collab.notebook |
| `/api/v1/notebooks/{id}` | GET | includes entries (optional tag filter) | viewer | collab.notebook |
| `/api/v1/notebooks` | POST | create notebook | editor | collab.notebook |
| `/api/v1/notebooks/{id}` | PUT/DELETE | update/delete | editor | collab.notebook |
| `/api/v1/notebooks/{id}/entries` | POST | create entry | editor | collab.notebook |
| `/api/v1/notebooks/{id}/entries/{entry_id}` | PUT/DELETE | edit/delete entry | editor | collab.notebook |
| `/api/v1/notebooks/{id}/shares` | GET/POST | list + create share links | editor | collab.notebook |
| `/api/v1/notebooks/{id}/shares/{share_id}` | DELETE | revoke share | editor | collab.notebook |
| `/api/v1/notebooks/shares/access` | POST | resolve share token (public) | n/a | n/a |

### Error codes (API surface)
- `notebook.org_required` / `notebook.user_required`: header missing or invalid.
- `notebook.not_found`: notebook/entry/share is missing or org mismatch.
- `notebook.error`: generic validation error (payload exceeds limits, tag duplication, etc.).
- `notebook.share.not_found|revoked|expired`: share lookup failures; revoked/expired return HTTP 410.
- `notebook.share.password_required|password_invalid`: password gate for share links.
- `plan.entitlement_required`: plan is missing `collab.notebook`.
- `rbac.*`: propagated directly from `require_org_role` (membership missing, role insufficient, etc.).

### Runtime limits (mirrors `services/notebook_service.py`)
- Notebook title ≤ **160** chars, summary ≤ **400** chars, cover color accepts hex `#RGB/#RRGGBB`.
- **Tags**: normalized to lowercase, max **16** unique tags per notebook or entry payload.
- Entries: highlight ≤ **4,000** chars, annotation ≤ **8,000** chars, allowed source keys = `type`, `label`, `url`, `deeplink`, `snippet`, `documentId`, `chunkId`, `page`, `paragraph`, plus nested `metadata`.
- Pagination: default list limit `25`, hard cap `100`.
- Shares: max active links per notebook = **20**, TTL between **10 minutes** and **30 days** (`MIN_SHARE_TTL_MINUTES`, `MAX_SHARE_TTL_MINUTES`), default = 7 days. Password hints max 160 chars; passwords hashed with Argon2 (env-tunable cost factors).

### Audit & observability
- All mutations emit `collab.notebook.*` audit events (`create/update/delete`, `entry.*`, `share.*`). These now appear under `source='collab'` for Grafana/Looker tiles.
- RBAC shadow failures log `rbac.shadow.*` for missing headers or inactive memberships; monitor to decide when to flip `RBAC_ENFORCE=true`.
- Plan guard failures log to standard FastAPI access logs; include them in entitlement gap dashboards if needed.
