# Phase 1 — Skeleton UI & Data Exposure (완료)

**핵심 목표** 검색 허브·회사 스냅샷 개편, 뉴스 인사이트 노출, 디자인 토큰 정착

## 주요 산출물
- 검색 경험
  - `web/dashboard/src/components/search/GlobalSearchBar.tsx` — 커맨드 팔레트/자동완성
  - `web/dashboard/src/components/search/SearchResults.tsx` — 탭 구조 및 잠금 배지
- 회사 스냅샷 & 뉴스
  - `[ticker]/page.tsx` 히어로·메트릭 레이아웃 리프레시
  - `NewsSignalCards.tsx`로 감성/신뢰도 카드 노출
- 디자인 시스템/인프라
  - Tailwind 모션 토큰 (`motion.css`, `tailwind.config.ts`)
  - Storybook 토큰 미리보기 스토리
- 문서 & QA
  - 검색/스냅샷 관련 회귀 테스트 (`web/dashboard/tests/SearchPage.spec.tsx` 등)
  - API 필드 감사 기록을 요약해 Phase 1 범위 확정

## 비고
- 증거 패널, 경보 설정, 요금제 UX는 다음 단계에서 다루도록 범위를 제한했습니다.
