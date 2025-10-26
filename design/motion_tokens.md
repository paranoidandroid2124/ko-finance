# Motion & Interaction Tokens (Phase 0 Draft)

> Applied across web/dashboard · aligns with Framer Motion / CSS variables

## 1. Timing Tokens

| Token | Duration | Curve | Usage |
| --- | --- | --- | --- |
| motion.fast | 120ms | cubic-bezier(0.2, 0, 0.38, 0.9) | Hover reveals, focus glow, tooltip fade-in |
| motion.medium | 220ms | cubic-bezier(0.2, 0, 0, 1) | Card entrance, skeleton shimmer cycle, tab transitions |
| motion.slow | 320ms | cubic-bezier(0.33, 1, 0.68, 1) | Panel slide, drawer open/close, alert banners |
| motion.delayed | 500ms | cubic-bezier(0.25, 0.1, 0.25, 1) | Upgrade CTA pulse, background gradients |
| motion.tactile | 80ms | cubic-bezier(0.4, 0, 1, 1) | Button press feedback, lock shake |

## 2. Easing Presets
- ease-emphasize: cubic-bezier(0.05, 0.7, 0.1, 1) – for emphasizing exit/enter transitions.
- ease-soft: cubic-bezier(0.16, 1, 0.3, 1) – used for sliding panels.
- ease-linear: linear – quantitative animations (sparkline updates) to avoid easing distortion.

## 3. Spatial Motion
- **Distance tokens** (transform translateY):
  - motion.translate.sm = 6px
  - motion.translate.md = 12px
  - motion.translate.lg = 24px
- **Scale tokens**:
  - motion.scale.focus = 1.02 (card hover)
  - motion.scale.lock = 1.05 (locked feature bounce)
  - motion.scale.toast = 0.96 → 1 (spring) for appearing toasts.

## 4. Opacity & Blur
- motion.opacity.quick: 0 → 1 in 120ms (tooltips, chips)
- motion.opacity.panel: 0.6 → 1 in 220ms + 4px blur fade (drawers)
- motion.blur.overlay: background blur 12px → 0 over 220ms when overlays close.

## 5. Accessibility Overrides
- Respect prefers-reduced-motion: reduce:
  - Replace translations with opacity/scale-less transitions.
  - Reduce duration to ≤80ms or snap to instant state for repetitive loops (skeleton shimmer becomes static gradient).
  - Provide ria-live="polite" messages when motion is suppressed but state changes occur.

## 6. Implementation Notes
- Define CSS custom properties under :root and .dark scopes in globals.css:
  `css
  :root {
    --motion-fast: 120ms cubic-bezier(0.2, 0, 0.38, 0.9);
    --motion-medium: 220ms cubic-bezier(0.2, 0, 0, 1);
    --motion-slow: 320ms cubic-bezier(0.33, 1, 0.68, 1);
    --motion-delayed: 500ms cubic-bezier(0.25, 0.1, 0.25, 1);
    --motion-tactile: 80ms cubic-bezier(0.4, 0, 1, 1);
  }
  `
- Tailwind config: map to utilities (nimate-fast, 	ransition-motion-medium).
- Framer Motion: centralize in lib/motionTokens.ts exporting constants.

## 7. Component Hooks
- **Tabs**: motion.medium with ease-soft, translateY 6px, opacity offset.
- **Timeline pointer**: motion.fast for hover, motion.medium for focus reveal.
- **Lock tooltip**: press triggers motion.tactile shake, tooltip uses motion.medium fade/slide.
- **Evidence highlights**: motion.slow background fade + scroll into view.
- **Toast stack**: sequential delay 60ms, max 3 items visible.

## 8. QA Checklist
- Verify animation runs ≤3 iterations unless user interaction continues.
- Ensure all motion has an accessible equivalent (state text updates, focus management).
- Document component-level motion in Storybook stories with toggle for Reduced Motion.

## 9. Next Tasks
1. Add CSS variables + Tailwind mapping.
2. Create Storybook “Motion Tokens” page demonstrating transitions.
3. Integrate tokens into GlobalSearchBar, SearchResultCard, TimelineNode prototypes.
