# Phase 0 Deliverables Tracker

## Scope
- Information architecture & wireframes
- Motion/interaction token documentation
- Output to feed Phase 1 component build and Storybook setup

## Artifacts
| Artifact | Path | Status | Notes |
| --- | --- | --- | --- |
| UX modernization wireframes | design/ux_modernization_wireframes.md | In progress | Screen-by-screen layout, data bindings, plan locks |
| Motion & interaction tokens | design/motion_tokens.md | Complete (2025-10-27) | Referenced by `web/dashboard/src/styles/motion.css` & Storybook token preview |
| IA checklist | ops/long_term_must_do.md §1–3 | In progress | Requirements captured in long-term tracker; needs formal checklist export |

## Open Actions
- [ ] Produce low-fi sketches (paper/Figma) covering Sections 1–5 of the wireframes doc and attach export.
- [x] Update `design/ui_design_system.md` to reference motion tokens and plan lock patterns. (2025-10-27)
- [x] Create Storybook placeholder (`web/dashboard/stories/TokenPreview.stories.tsx`) now that Tailwind tokens exist.
- [ ] Validate API field availability for newly surfaced KPIs (market returns, sector mapping, source reliability) and record gaps.

## Review Checklist
- [ ] Wireframe coverage aligns with all user journeys (search, company, filing, sector, chat).
- [x] Motion tokens mapped to at least one component per interaction type.
- [x] Plan lock UX documented for Free/Pro/Enterprise.
- [x] Accessibility notes captured (reduce motion, keyboard).

## Sign-off
- Design review: _TBD_
- Product/PM approval: _TBD_
- Target completion for Phase 0: 2025-11-05
