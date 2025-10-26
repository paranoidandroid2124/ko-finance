# K-Finance Dashboard UI Design System (Draft)

## 1. Typography
- **Primary font**: Pretendard (fallback: Inter, system sans-serif)
- **Numeric font**: Roboto Mono for KPI figures and tables
- **Weights**: 700 (heading), 600 (subheading), 500 (label), 400 (body), 300 (caption)
- **Line heights**: Heading 1.3, body 1.6

## 2. Color Palette

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `bg-page` | #F5F7FB | #0D1423 | 기본 배경 |
| `bg-card` | #FFFFFF | #171F2F | 카드, 패널 |
| `text-primary` | #111827 | #F9FAFB | 본문, 주요 텍스트 |
| `text-secondary` | #4B5563 | #9CA3AF | 보조 텍스트 |
| `border` | #E5E7EB | #1F2937 | 구분선, 카드 테두리 |
| `primary` | #4B6CFB | #5C7CFF | CTA, 강조 링크 |
| `primary-hover` | #3755E8 | #4A64F0 | hover 상태 |
| `accent-positive` | #2AC5A8 | #22D3C5 | 긍정 감성, 상승 지표 |
| `accent-negative` | #F45B69 | #FF6B81 | 부정 감성, 하락 지표 |
| `accent-warning` | #F2B636 | #FACC15 | guardrail 경고, 알림 |

차트 색상(순서): `#5C7CFF`, `#2AC5A8`, `#F45B69`, `#A855F7`, `#38BDF8`, `#F97316`.

## 3. Layout Grid
- 최대 폭 1440px, 12-column grid, gutter 24px
- 핵심 영역
  - 좌측 사이드바 (폭 256px, collapse 모드 80px)
  - 상단 헤더 (높이 72px, sticky)
  - 중앙 콘텐츠 (카드 레이아웃, 3열 대응)
  - 우측 사이드패널 (폭 320px, 알림·챗봇)
- 반응형 breakpoint: 1280 / 1024 / 768 / 480
- 모바일: 사이드바 Drawer, 카드 스택 정렬

## 4. Components (MVP 리스트)

### Navigation
- 글로벌 사이드바: 로고, 주요 섹션, 하위 링크
- 상단 헤더: 검색, 알림, 테마 토글, 사용자 메뉴

### 카드 & 지표
- KPI 카드: 제목, 메트릭 값, 증감 퍼센트, Sparkline
- 트렌드 카드: 기간 선택 탭 + Line/Area 차트
- 토픽/랭킹 카드: 리스트형, 아이콘/색상 배지

### 데이터 표시
- 테이블: Sticky header, 필터 칩, 정렬, 페이지네이션
- 뉴스 카드: 출처, 감성, 타임스탬프, CTA
- 알림 피드: 아이콘, 요약, 세부 버튼

### 상호작용 요소
- 탭/세그먼트 컨트롤
- 슬라이더(감성 임계값), 스위치(알림 채널)
- 모달/Drawer (PDF 뷰어, 설정)
- Toast, Skeleton, Empty state

### 챗봇 UI
- 메시지 버블: 사용자/시스템 구분 색
- Follow-up pill 버튼
- Guardrail 경고 배너
- 피드백 버튼 (👍 / 👎) + 텍스트 입력

## 5. Iconography
- Tabler Icons (line style) 기본 사용
- 커스텀 섹터 아이콘 8종 (예: 바이오, 엔터, 에너지, 금융 등)
- Guardrail, 알림 레벨 별 색상 배지 정의

## 6. Interaction & Motion
- Hover 상태: 배경 6~8% 명도 변화, 그림자 강화
- 카드 진입: 0.2s fade-in + translate Y(8px) → 0
- 차트: 초기 line-draw 0.4s ease-out
- Light/Dark 전환: 0.3s crossfade (prefers-reduced-motion 대응)
- Focus ring: 2px solid `#5C7CFF` + outline-offset 2px

## 7. Accessibility & Localization
- 텍스트 대비 4.5:1 이상 (primary), 3:1 이상 (secondary)
- 모든 아이콘 버튼에 `aria-label`
- 키보드 네비게이션: 탭 순서 정의, Skip to content 링크
- 다국어 대비: 문자열 별 토큰화, 한/영 전환 UI 고려

## 8. Implementation Stack (추천)
- Next.js 14 (App Router) + TypeScript
- Tailwind CSS + `next-themes`
- React Query (데이터 페칭/캐시)
- Zustand (글로벌 UI 상태)
- Storybook (컴포넌트 QA)
- ECharts/Apache ECharts (다크 테마 지원) or Recharts
- Framer Motion (모션)

## 9. 디자인 Deliverable 계획
1. Figma: 스타일 가이드 + 4개 핵심 화면 와이어프레임(홈, 공시, 뉴스, 챗)
2. Storybook: Navigation, 카드, 차트 래퍼, 챗버블 컴포넌트
3. Theme 토글, Layout 템플릿, 데모 데이터 기반 목업 페이지

## 10. 다음 단계
- Figma 와이어프레임 초안 → 이해관계자 확인
- Next.js 프로젝트 초기화 (`web/dashboard`) 및 스타일 시스템 반영
- Storybook 세팅 후 핵심 컴포넌트 개발 착수


## Phase 0 References
- Motion tokens: design/motion_tokens.md (timings, easings, lock interactions)
- Deliverables tracker: design/phase0_deliverables.md

