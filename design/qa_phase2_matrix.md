# Phase 2 QA 시나리오 매트릭스 (초안)

> 업데이트: 2025-11-21 · 담당: TBD  
> 범위: EvidencePanel v2, TimelineSparkline, RAG v2 백엔드 연계

## 1. 핵심 UI 상태

| 시나리오 | 상태 값 | 기대 결과 | 확인 방법 |
| --- | --- | --- | --- |
| EvidencePanel 로딩 | `status=loading` | 스켈레톤 4개 출력, PDF 영역 로딩 메시지 | Storybook `Evidence/EvidencePanel/Loading` |
| 근거 정상 노출 | `status=ready` | self_check, reliability 뱃지 노출, 선택 카드 강조 | Storybook `Evidence/EvidencePanel/Ready` |
| 앵커 미스매치 | `status=anchor-mismatch` | 상단 경고 배너, PDF fallback 버튼 | Storybook `Evidence/EvidencePanel/AnchorMismatch` |
| Free 플랜 잠금 | `planTier=free`, `inlinePdfEnabled=false` | 잠금 메시지 + 업그레이드 CTA + PDF 새 창 링크 | Storybook `Evidence/EvidencePanel/FreePlanLocked` |
| TimelineSparkline 기본 | `planTier=pro` | 감성/가격 듀얼축, 이벤트 툴팁 | Storybook `Company/TimelineSparkline/Default` |
| Free 플랜 | `planTier=free` | 가격축 비활성, 감성만 노출 | Storybook `Company/TimelineSparkline/FreePlan` |
| 잠금 상태 | `locked=true` | 잠금 카드, 업그레이드 CTA | Storybook `Company/TimelineSparkline/Locked` |
| Chat 연동 | 채팅 화면 EvidenceWorkspace | 근거 선택 시 대화창 하이라이트, PDF 미리보기 동기화 | `/app/chat` 로컬 실행, Session 생성 후 확인 |
| Timeline 데이터 없음 | `timeline.points=[]` | “표시할 타임라인 데이터가 없습니다” 안내 | `/app/labs/evidence` 또는 Storybook |

## 2. 로그·관측 항목

- `rag.evidence_view` 이벤트: EvidencePanel 마운트, 카드 선택, 타임라인 Hover 연동 시 `urn_id`, `anchor.paragraph_id`, `self_check.verdict`, `plan_tier` 포함 (백로그).
- TimelineSparkline 상호작용: hover/select 시 `timeline.hover`/`timeline.select` 콘솔 이벤트 임시 확인 → 추후 Langfuse/Analytics 스키마 정의.
- 채팅 EvidenceWorkspace 연동 시: `rag.evidence_view`, `timeline.interact` 이벤트가 `telemetry:event` 커스텀 이벤트로 브라우저에 전달되는지 확인 (DevTools → Event Listeners).

## 3. 통합 테스트 계획

1. 백엔드: `tests/test_rag_api.py` v2 페이로드 유지, 향후 EvidencePanel snapshot fixture 연동.
2. 프런트 유닛: EvidencePanel + Timeline 상호작용 테스트 (`tests/evidenceWorkspaceStore.spec.ts`) → telemetry 이벤트 확인.
3. E2E 후보: 질문 생성 → 근거 선택 → PDF 띄우기 → 타임라인 클릭 플로우 (Playwright 초안 작성 예정). Reduce Motion 환경(브라우저 설정) 포함.

## 4. 오픈 이슈

- PDF.js 래퍼 연동 시 로딩/에러 상태를 Storybook에 반영 필요.
- IntersectionObserver 사용 시 SSR 안전성을 테스트 환경에서 검증해야 함 (JSDOM mock 필요).
- TimelineSparkline `visualMap` 강조 색상 다크 모드 대비 확인.
- EvidenceWorkspace의 planTier UI 문구/스타일 확정 필요(Pro/Enterprise 전환 문구 검토).
