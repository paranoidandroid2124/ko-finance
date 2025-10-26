# UX Modernization Wireframes (Phase 0)

> Reference: ops/long_term_must_do.md · Updated 2025-10-25

## 1. Global Research Hub (Search Results)

### Layout
- **Sticky header (72px)**: logo · command palette button (⌘K) · notification bell (locked in Free) · profile avatar.
- **Search rail (left, 280px)**: query history, saved filters (Pro+), quick filters (공시, 뉴스, 섹터, 키워드).
- **Results canvas (flex 1)**: tab strip (공시 · 뉴스 · 표 · 차트) with result count badge → responsive grid (2 columns ≥1280px, single column <1024px).
- **Evidence preview rail (right, 320px)**: collapsible drawer showing last selected card’s key facts + link to full evidence panel.

### Result Card Anatomy
1. Title (report/news headline) + badge for category (정기보고, M&A, etc.).
2. Meta row: iledAt/publishedAt, ingest timestamp, source reliability chip.
3. KPI row: 이벤트 후 1D/5D/20D 수익률, 섹터 대비 Δ, 감성 z-score (news only).
4. Evidence summary pills: count of supporting paragraphs, PDF link indicator, RAG self-check state.
5. Actions: Open Evidence (Free), Add to Compare (Pro lock), Set Alert (Pro lock), Export (Enterprise lock).

### Empty / Loading States
- Skeleton grid (8 cards) with shimmer motion token motion.medium.
- Empty message with tips (필터를 완화해 보세요, 최근 조회: ...).

## 2. Company Command Center (/company/[ticker])

### Above the Fold
- **Hero panel**: Company name, ticker, sector chips, latest filing callout (title, filed date, receipt no., OpenDART link).
- **Metric strip** (4 KPIs): EBITDA margin, YoY revenue, debt ratio, sentiment trend; each has sparkline overlay with event markers.
- **Disclosure summary**: who/what/why/how blocks (from summary), with inline doc anchor icons.

### Mid Section
- **Event Timeline** (left, 60% width): vertical timeline with grouped events (issuance, litigation, governance) and derived metrics badges; selecting a node syncs the chart and evidence panel.
- **Market Response Panel** (right, 40% width): dual-axis chart combining price vs. sentiment z-score, with brush for range selection (Pro unlock for custom ranges).

### Lower Section
- **Peer Comparison Table**: columns for ticker, market cap, latest sentiment, 5D return, major recent filing (title). CSV export, alert, API buttons locked behind Pro/Enterprise.
- **News Insight Cards**: windows (24h, 72h, 7d) showing article count, avg sentiment, top topics (chip group), domain diversity gauge.

### Drawer Interactions
- View Evidence: slides in from right (70% width) showing paragraph highlights, PDF inline viewer (Pro), update tracker (diff vs previous run).

## 3. Filing Deep Dive (/filings/[id])

### Layout
- Two-column (main 720px, sidebar 320px) within responsive container.
- **Main**: filing title, sentiment banner, metadata row, summary paragraphs.
- **Evidence section**: accordion grouped by “핵심 사실”, each entry showing paragraph snippet, anchor (p.12, 3-1절), support confidence.
- **Market impact**: mini chart with 1D/5D/20D returns vs sector, highlight window.
- **RAG Q&A quick-start**: prompt suggestions, self-check status chips.

### Sidebar
- PDF 열기, 다운로드, 비교에 추가, 알림 설정, 챗으로 보내기. Buttons show lock badge depending on plan.
- Processing health: pipeline run time, anomalies detected, last refresh timestamp.

## 4. Sector Pulse Dashboard (/sectors & /news)

### Top Section
- Heatmap of sector sentiment vs volume (Free) with hover tooltip showing top events/news; Pro unlock toggles for window size, data export.
- Hotspot scatter (volume surprise vs sentiment shift) with drill-down to article drawer.

### Mid Section
- Explainer Panel: top-moving sectors, aggregated topics, recommended watchlist (Pro).
- News Drawer: sorted by novelty score with cluster tags (duplication collapse indicated by stacked icon).

### Bottom Section
- Alert builder (Pro+): configure sector, trigger condition, channel. Disabled in Free with upgrade CTA.
- API usage summary (Enterprise): request volume, rate limits.

## 5. Research Assistant Console (/chat)

### Layout
- Left rail: session list, pinned conversations (Pro), filters (context type).
- Main pane: message stream with role coloring, guardrail banner, evidence citations with inline preview buttons.
- Right rail: context summary, related filings/news, upgrade panel (for locked features).

### Message Blocks
- Assistant message includes: answer, evidence chips (공시, 뉴스, 표, 차트 icons), self-check verdict, follow-up suggestions.
- User message metadata: timestamp, source (manual vs auto follow-up).

### Locked Enhancements
- Export conversation, Schedule refresh, Team share (Enterprise) displayed with lock shimmer animation.

## 6. Responsive Considerations
- Tablets (≤1024px): search rail collapses into top filter pills; evidence preview toggles via bottom sheet.
- Mobile (≤768px): command palette becomes floating button; evidence panel becomes full-screen modal; charts switch to mini sparkline cards.

## 7. Wireframe Deliverables
- Low-fidelity sketches attached (Link TBD) with layer naming aligned to component list.
- Each wireframe includes annotation for data bindings and plan lock states (Free, Pro, Enterprise).

## 8. Next Steps
1. Validate wireframes against existing data availability (useCompanySnapshot, useFilings, RAG responses).
2. Confirm additional API fields required (market returns, sector mapping, pipeline metadata).
3. Update design tokens and Storybook scaffolding (see motion_tokens.md).
