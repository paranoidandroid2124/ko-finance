# Phase 2 – Week 1 Foundation Notes

Author: Solo contributor · Date: 2025-11-20  
Scope: Preparation deliverables required before Week 2 implementation.

## 1. EvidencePanel UX States
Reference mock assets: `docs/mockups/phase2/`

- **Loading:** Skeleton list + disabled timeline sync; motion tokens `motion.fast` for shimmer, reduce-motion drops animation.
- **Populated (free plan):** Paragraph list, highlight gutter, PDF open-in-new-tab CTA. Diff toggle hidden, export button replaced with upgrade tooltip.
- **Populated (pro/enterprise):** Inline PDF viewer with page mini-map, diff toggle active, plan badge in header.
- **Anchor mismatch fallback:** Paragraph cards show warning banner, highlights disabled, PDF CTA falls back to download link.
- **Evidence locked (plan restriction):** Overlay explains required plan tier, CTA button routes to plan picker.

## 2. PDF Viewer Evaluation

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| PDF.js (self-hosted) | Fine-grained highlight control, consistent styling, offline caching | Larger bundle (~350KB gz), needs worker setup | ✅ Primary |
| Native iframe/embed | Zero bundle impact, fastest to wire | Inconsistent rendering across browsers, limited highlight API | ❌ Fallback |

Actions:
- Implement PDF.js wrapper with lazy loading and worker bundling.
- Provide iframe/open-in-new-tab fallback path when PDF.js fails to load (network or cross-origin constraints).
- Document legal review requirement for embedded PDFs; interim note lives in `docs/mockups/phase2/README.md`.

## 3. RAG Schema & Logging Requirements

### 3.1 Response payload

| Field | Type | Notes |
| --- | --- | --- |
| `urn_id` | string | Stable identifier for the evidence unit (replaces `burn_id`). |
| `chunk_id` | string | Vector store chunk identifier. |
| `page_number` | int | 1-based PDF page index; optional for non-PDF sources. |
| `section` | string | Heading or logical section extracted from metadata. |
| `quote` | string | Highlighted excerpt (<= 600 chars). |
| `anchor` | object | `{ paragraph_id, pdf_rect?, similarity }` used for highlight mapping. |
| `self_check.score` | float | Normalised 0–1 confidence score. |
| `self_check.verdict` | enum[`pass`,`warn`,`fail`] | Displayed as badge. |
| `source_reliability` | enum[`high`,`medium`,`low`] | Maps to badge color. |
| `created_at` | datetime | For diff snapshot ordering. |

### 3.2 Evidence snapshot metadata

- Table columns: `urn_id`, `snapshot_hash`, `diff_type`, `author`, `process`, `updated_at`.
- Celery task writes snapshot after each chat response; diff job compares previous hash to detect changes.

### 3.3 Logging additions

- Log name: `rag.evidence_view`.
- Fields: `urn_id`, `chunk_id`, `anchor.paragraph_id`, `self_check.verdict`, `source_reliability`, `plan_tier`, `latency_ms`.
- Emit on EvidencePanel mount, timeline hover-to-highlight, and diff toggle.

### 3.4 Fallback rules (applied when metadata is incomplete)

- `paragraph_id`: fall back to chunk `id`/`chunk_id` hash when explicit paragraph metadata is missing.
- `pdf_rect`: keep `None` unless PDF.js annotator emits coordinates; do not synthesise fake boxes.
- `source_reliability`: map numeric scores ≥0.66 → `high`, ≥0.33 → `medium`, else `low`. Unknown values remain `None`.
- `self_check`: if Celery verdict missing, omit field entirely to avoid presenting stale data.
- `quote`: prioritise `metadata.quote`; otherwise reuse `content` string, clamped to 600 chars at render time.

## 4. Follow-up for Week 2

- Update API schema (`schemas/api/rag.py`) and routers with new payload fields and backwards-compatible flag.
- Prepare fixtures under `fixtures/evidence/` mirroring the table above (happy path, anchor mismatch, low reliability).
- Draft pytest cases for schema validation and snapshot diff logic.
- Create Storybook scaffolding (`stories/`) using the defined UX states once frontend work begins.
