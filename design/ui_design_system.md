# K-Finance Dashboard UI Design System (Draft)

## 1. 타이포그래피
- **기본 본문**: Pretendard (fallback: Inter, system sans-serif)
- **숫자 데이터**: Roboto Mono – KPI, 테이블, 스파크라인 축에 사용
- **굵기 체계**: 700(헤딩) · 600(섹션 타이틀) · 500(레이블) · 400(본문) · 300(캡션)
- **행간**: 헤딩 1.3, 본문 1.6 – 카드와 패널에서 정보 밀도를 유지하면서 가독성 확보

## 2. 컬러 팔레트

| Token | Light | Dark | 용도 |
| --- | --- | --- | --- |
| `bg-page` | #F5F7FB | #0D1423 | 기본 배경 |
| `bg-card` | #FFFFFF | #171F2F | 카드/패널 |
| `text-primary` | #111827 | #F9FAFB | 본문, 주요 텍스트 |
| `text-secondary` | #4B5563 | #9CA3AF | 보조 텍스트 |
| `border` | #E5E7EB | #1F2937 | 구분선, 카드 테두리 |
| `primary` | #4B6CFB | #5C7CFF | CTA, 강조 링크 |
| `primary-hover` | #3755E8 | #4A64F0 | Hover 상태 |
| `accent-positive` | #2AC5A8 | #22D3C5 | 긍정 지표, 상승 카드 |
| `accent-negative` | #F45B69 | #FF6B81 | 부정 지표, 하락 경고 |
| `accent-warning` | #F2B636 | #FACC15 | Guardrail 경고, 알림 |

차트 팔레트(순서 사용): `#5C7CFF`, `#2AC5A8`, `#F45B69`, `#A855F7`, `#38BDF8`, `#F97316`.

## 3. 레이아웃 그리드
- 최대 폭 1440px, 12-column grid, gutter 24px
- 주요 영역
  - 좌측 사이드바: 폭 256px, collapse 모드 80px
  - 상단 헤더: 높이 72px, sticky
  - 중앙 콘텐츠: 카드형 구성, 최대 3열
  - 우측 사이드패널: 폭 320px, 알림·챗봇
- 반응형 breakpoint: 1280 / 1024 / 768 / 480
- 모바일: 사이드바 Drawer, 카드 스택 정렬, 헤더 아이콘 우선

## 4. 핵심 컴포넌트
### 네비게이션
- 글로벌 사이드바: 로고, 주요 섹션, 하위 링크 그룹
- 상단 헤더: 검색, 알림(벨 HoverCard), 테마 전환, 사용자 메뉴

### 카드 & 지표
- KPI 카드: 제목, 메트릭 값, 증감 퍼센트, 스파크라인
- 트렌드 카드: 기간 선택 탭 + Line/Area Chart
- 토픽/랭킹 카드: 리스트형, 아이콘·컬러 배지

### 데이터 표시
- 테이블: Sticky header, 필터 칩, 페이지네이션
- 뉴스 카드: 출처, 감성, 타임스탬프, CTA
- 알림 피드: 톤 배지, HoverCard 링크, 빈 상태 메시지

### 상호작용 요소
- 탭/세그먼트 컨트롤: 모션 토큰 기반 transition, 키보드 포커스 지원
- 모달/드로어: Evidence PDF Viewer, 설정 패널
- Toast, Skeleton, Empty state: 일관된 복구/가이드 텍스트 포함

### 플랜 잠금 UI
- 잠금 버튼: 점선 테두리 + 회색 텍스트 + 자물쇠 아이콘
- 업그레이드 CTA: primary 색상, hover 시 scale 1.02
- 락 툴팁: `group-hover` + `transition-motion-medium`, 포커스 노출

## 5. 아이코노그래피
- 기본: Tabler Icons(line). 24px 기준, 필요 시 16px/20px 스케일링
- 커스텀 섹터/산업 아이콘 8종: 바이오, 에너지, 금융, 반도체 등
- Guardrail/알림: 톤 색상에 맞춘 배지(`accent-positive/negative/warning`)

## 6. 인터랙션 & 모션 토큰
- **CSS 커스텀 프로퍼티** (정의: `web/dashboard/src/styles/motion.css`)
  | 토큰 | 변수 | 값 | 권장 사용처 |
  | --- | --- | --- | --- |
  | motion-fast | `--motion-fast-duration` | 120ms · cubic-bezier(0.2,0,0.38,0.9) | 버튼 hover, 포커스 링 |
  | motion-medium | `--motion-medium-duration` | 220ms · cubic-bezier(0.2,0,0,1) | 카드 등장, 탭 전환 |
  | motion-slow | `--motion-slow-duration` | 320ms · cubic-bezier(0.33,1,0.68,1) | 패널 슬라이드/드로어 |
  | motion-delayed | `--motion-delayed-duration` | 500ms · cubic-bezier(0.25,0.1,0.25,1) | 업그레이드 CTA 펄스 |
  | motion-tactile | `--motion-tactile-duration` | 80ms · cubic-bezier(0.4,0,1,1) | 락 버튼 클릭, 미세 흔들림 |
- **Tailwind 유틸리티 매핑**
  - `transition-motion-fast`, `transition-motion-medium`, `animate-lock-shake`, `motion-shimmer`
  - Skeleton shimmer는 prefers-reduced-motion 조건 시 정적 그라디언트로 전환
- **Framer Motion 권장값**
  - `spring`(stiffness 320, damping 26) + opacity: 패널/드로어 진입
  - HoverCard(AlertBell): `initial { opacity:0, y:-8 } → animate { opacity:1, y:0 }`
  - Reduced motion: translate 제거, opacity-only transition

## 7. 플랜 락 & 업그레이드 패턴
- **상태 표기**
  | 요소 | Free | Pro | Enterprise |
  | --- | --- | --- | --- |
  | 잠금 버튼 | 점선 테두리 + 회색 텍스트 + 자물쇠 아이콘 | 실선 테두리 + primary 텍스트 | 실선 + 아이콘/배지 허용 |
  | 툴팁 메시지 | “Pro 플랜에서 이용 가능” | “Enterprise 업그레이드 안내” | 계정/플랜 관리 링크 |
  | 배경/오버레이 | 60% 화이트 오버레이 + blur | 40% primary 오버레이 | 투명, 기능 활성 |
- **적용 레퍼런스**
  - 검색 결과 카드: `LockedButton` 컴포넌트 (compare/alert/export)
  - EvidencePanel: `locked` 플래그 시 카드 오버레이 + 업그레이드 텍스트
  - TimelineSparkline: Free 플랜 → 거래량/가격 축 숨김, 락 메시지 노출
- **상호작용 가이드**
  - 클릭 시 `animate-lock-shake` 80ms 적용 → 즉각적 피드백
  - 업그레이드 CTA는 `motion-delayed`와 `transition-motion-medium` 조합으로 부드러운 스케일
  - 접근성: `aria-disabled`, `aria-describedby`(툴팁) 지정, 키보드 포커스 허용

## 8. 접근성 & 현지화
- 텍스트 대비: 주요 텍스트 4.5:1 이상, 보조 텍스트 3:1 이상
- 포커스 링: 2px solid `#5C7CFF`, outline-offset 2px
- 네비게이션: 탭 순서 정의, “Skip to content” 링크 지원
- 다국어: 한/영 토글 고려, 날짜·숫자 포맷 다국어 라이브러리 사용
- 모션 축소: `prefers-reduced-motion` 감지 → opacity-only, shimmer 비활성

## 9. 구현 스택 (추천)
- Next.js 14(App Router) + TypeScript
- Tailwind CSS + `next-themes`
- React Query(데이터 패칭/캐싱), Zustand(글로벌 UI 상태)
- Storybook 8 – 모션 토글, 접근성 애드온 포함
- Framer Motion, ECharts 또는 Recharts

## 10. 디자인 산출물 계획
1. Figma: 검색/회사/뉴스/챗 메인 화면 와이어프레임 → Phase 2 하이파이 연계
2. Storybook: Navigation, 카드, 차트 래퍼, 락 UI 컴포넌트 스토리
3. Theme 토큰, Layout 템플릿, 데이터 데모 페이지 샘플

## 11. Phase 0 레퍼런스
- 모션 토큰: `design/motion_tokens.md`
- 딜리버러블 트래커: `design/phase0_deliverables.md`
