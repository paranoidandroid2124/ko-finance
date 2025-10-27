# Storybook Assets

All Phase 2 UI explorations (EvidencePanel v2, TimelineSparkline) live here.

- Create stories next to the component they document (e.g., `EvidencePanel.stories.tsx`).
- Use dev-only imports: fixtures from `fixtures/evidence` and mock hooks/components under `stories/`.
- Exclude this directory from production builds; run Storybook via `yarn storybook` or CI visual regression workflows.
- Enable reduced-motion variants in each story to satisfy accessibility requirements.
