# K-Finance Dashboard (Frontend)

Next.js 기반 “K-Finance AI Copilot” 대시보드입니다. 실시간 공시·뉴스·RAG 분석 데이터를 백엔드 FastAPI (`/api/v1/...`)에서 직접 받아 렌더링하며, mock 데이터는 더 이상 사용하지 않습니다.

## 핵심 스택
- Next.js 14 (App Router, TypeScript)
- Tailwind CSS + next-themes
- React Query, Zustand
- Storybook

## 빠른 시작
1. **백엔드 기동**  
   Redis·Qdrant·PostgreSQL이 포함된 백엔드를 먼저 실행합니다. 예시:
   ```bash
   docker-compose up -d        # 또는 Makefile: make services
   ```

2. **의존성 설치**
   ```bash
   pnpm install   # 또는 npm install / yarn
   ```

3. **환경변수 설정 (`web/dashboard/.env.local`)**
   ```bash
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   ```
   - 값은 *슬래시 없이* 루트만 적습니다. 예: `https://api.kofilot.com`
   - 이 값은 런타임에 클라이언트로 노출되므로 공개 가능한 도메인만 입력합니다.

4. **개발 서버 실행**
   ```bash
   pnpm dev       # http://localhost:3000
   ```

Storybook:
```bash
pnpm storybook
```

## 실제 API 연동 요약
React Query 훅이 모두 실서비스 엔드포인트를 조회합니다. 주요 매핑은 다음과 같습니다.

| 화면/훅 | 요청 | 설명 |
| --- | --- | --- |
| `useFilings` (`src/hooks/useFilings.ts`) | `GET /api/v1/filings/?limit=50`<br/>`GET /api/v1/filings/{filing_id}` | 공시 리스트/상세를 최신 순으로 조회 |
| `useDashboardOverview` | `GET /api/v1/dashboard/overview` | 핵심 지표·알림·뉴스 요약 |
| `useNewsHeatmap` | `GET /api/v1/news/sentiment/heatmap` | 섹터·시간대별 뉴스 감성 히트맵 |
| `useNewsInsights` | `GET /api/v1/news/insights` | 상위 뉴스 인사이트 |
| `chatStore` + `chatApi` | `GET /api/v1/chat/sessions` 등 | 챗봇 세션/메시지 동기화 |

> 백엔드와의 스키마 계약은 `web/routers/*.py`, `schemas/api/*.py`에 정의되어 있습니다. 필요 시 그 라우터 문서를 우선 확인하세요.

## 실데이터 회귀 체크
Mock 제거 이후에도 실제 API가 응답하지 않을 경우 UI가 빈 상태가 되므로, 최소한 아래 스크립트 중 하나를 실행해 연결을 검증하는 것을 권장합니다.

1. **간단 헬스체크 스크립트 (추가됨)**  
   ```bash
   pnpm dlx ts-node scripts/check-api-health.ts
   ```
   - `/api/v1/filings`, `/api/v1/dashboard/overview` 엔드포인트를 호출해 성공 여부를 출력합니다.

2. **Playwright 스모크 (선택)**  
   ```bash
   pnpm dlx playwright test --config playwright.config.ts --grep "@smoke"
   ```
   - 추후 실데이터 UI 회귀용 시나리오는 `tests/e2e`에 추가 예정입니다.

## 소스 구조
```
src/
  app/           Next.js App Router 엔트리
  components/    레이아웃 & UI 컴포넌트
  hooks/         React Query / Zustand 연동 훅
  lib/           API 클라이언트, 유틸
  store/         Zustand 상태 스토어
design/          디자인 시스템 문서 (루트 기준)
scripts/         개발 편의 스크립트 (예: API 헬스체크)
```

## 진행 상황
- [x] 실서비스 API 연동
- [x] 챗봇 세션 동기화
- [ ] Tailwind theme token 변수화
- [ ] ECharts 기반 인사이트 차트
- [ ] Playwright 실데이터 회귀 시나리오 강화
- [ ] 온보딩/운영 문서 세부화

