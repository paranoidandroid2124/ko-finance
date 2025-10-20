# K-Finance Dashboard (Frontend)

React 기반 데이터 대시보드 UI 프로젝트입니다. 백엔드 API(`/api/v1/...`)와 연동하여 공시, 뉴스, RAG 분석을 시각화합니다.

## 기술 스택
- Next.js 14 (App Router, TypeScript)
- Tailwind CSS + next-themes
- React Query, Zustand
- Storybook

## 개발 시작
```bash
pnpm install   # 또는 npm install / yarn
pnpm dev       # http://localhost:3000
```

Storybook 실행:
```bash
pnpm storybook
```

## 구조
```
src/
  app/           Next.js App Router
  components/    레이아웃 & UI 컴포넌트
  lib/           Theme 등 유틸
design/          디자인 시스템 문서 (루트)
```

## TODO
- Tailwind theme token 개선 (CSS 변수화)
- 실제 API 연동 및 실시간 업데이트 적용
- ECharts 기반 차트 컴포넌트 구현
- 챗봇 세션/히스토리 기능 확장

