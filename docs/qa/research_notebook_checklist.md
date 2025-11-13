## Research Notebook QA Checklist (MVP)

Use this list before tagging a release that contains the Research Notebook feature set.

### Database & migrations
- [ ] Apply `ops/migrations/add_research_notebooks.sql` on staging and confirm `notebooks`, `notebook_entries`, `notebook_shares` exist with triggers.
- [ ] Verify insert/update/delete on `notebook_entries` increments `notebooks.entry_count` + `last_activity_at`.

### API (FastAPI `/api/v1/notebooks`)
- [ ] `GET /api/v1/notebooks` returns org-scoped notebooks with tag filtering + pagination guard.
- [ ] `POST /api/v1/notebooks` requires `x-user-id/x-org-id`, emits `collab.notebook.create`.
- [ ] Notebook detail returns entries filtered by `entryTags` query param.
- [ ] Entry CRUD endpoints honor RBAC role threshold (`viewer` read, `editor` write).
- [ ] Share endpoints (`GET|POST|DELETE /{id}/shares`) enforce max active links (20) and password hashing.
- [ ] `POST /api/v1/notebooks/shares/access` handles happy path + password_required + revoked/expired codes.

### Frontend (Next.js `labs/notebook`)
- [ ] Notebook creation form validates empty title/duplicate tags.
- [ ] Markdown editor toggles between edit/preview and persists tags/source metadata.
- [ ] Inline entry edit & delete reflect in list without hard refresh.
- [ ] Share panel creates TTL/password links and copies `/labs/notebook/share/{token}` URL to clipboard.
- [ ] Public share page (no login) loads, prompts for password when required, and renders highlight cards.

### Audit & logging
- [ ] `services/audit_log` contains `collab.notebook.*` events for notebook/entry/share actions with `org_id`, `user_id`, `target_id`.
- [ ] RBAC middleware logs `rbac.shadow.*` if headers missing (dev mode) without blocking when `RBAC_ENFORCE=false`.

### Regression / smoke
- [ ] Existing dashboard routes (`labs/evidence`, `/watchlist`, `/chat`) continue to render (no shared state errors).
- [ ] Middleware allows `/labs/notebook/share/*` without session redirect; authenticated routes still enforce login.

Document any deviations plus remediation steps before sign-off.
