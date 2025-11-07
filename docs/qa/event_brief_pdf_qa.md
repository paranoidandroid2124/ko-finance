# 이벤트 브리프 PDF QA 체크리스트

## 목적
RAG 재색인 작업 이후 생성되는 Typst 기반 이벤트 브리프 PDF가
- 시각적으로 깨지지 않고
- 필수 링크/첨부가 정상 동작하며
- 저장된 메타데이터와 일치하는지

를 반복적으로 검증하기 위한 운영·QA 가이드입니다.

## 준비물
- 최근 재색인 작업 ID 3~5건
- 각 작업의 `event_brief.pdf`, `event_brief.json`, `evidence_package.zip`
- Langfuse trace URL (있을 경우)
- 감사 로그 (`rag_event_brief_generated`) 항목

## 1. 레이아웃 및 스타일
- [ ] 모든 페이지에서 폰트가 기본 테마(한글 Noto Sans 대체)로 표시된다.
- [ ] 표·요약 박스가 페이지 경계에서 잘리지 않고, 머리글/셀 테두리가 유지된다.
- [ ] 강조 색상은 `#1F6FEB`(primary), `#22C55E`(accent)로 렌더링된다.
- [ ] 문단 사이 간격, 불릿 리스트 등 Typst 스타일이 깨지지 않는다.

## 2. 링크 및 첨부 기능
- [ ] `Langfuse trace` 버튼/링크가 존재할 경우 올바른 URL로 이동한다.
- [ ] `증거 패키지 ZIP` / `PDF 다운로드` 버튼이 200 응답을 반환하고 만료되지 않았다.
- [ ] 본문 내 내부 목차/하이퍼링크가 해당 섹션으로 정확히 이동한다.

## 3. 데이터 정확성
- [ ] 헤더의 `Task ID`, `Scope`, `Actor`, `완료 시각`이 `rag_reindex.jsonl` 기록과 동일하다.
- [ ] `event_brief.json`의 `diff_summary`와 PDF 표기 값이 일치한다.
- [ ] Langfuse trace ID·URL이 감사 로그(`rag_event_brief_generated`)의 payload와 매칭된다.
- [ ] 주요 수치(총 변경 건수, queue wait, duration 등)가 Admin 패널 히스토리 API 응답과 동일하다.

## 4. 회귀 테스트
- [ ] 최소 월 1회 QA 리포트를 기록한다 (`docs/qa/qa-log.md` 등).
- [ ] PDF 생성 파이프라인에 수정이 있을 때는 위 항목을 즉시 전체 수행한다.

## 5. 자동화 제안
- `scripts/render_daily_brief.py`에 최근 N건 PDF를 재생성하고, 링크 유효성(HTTP status)과 JSON 대비 필드 차이를 검사하는 옵션을 추가한다.
- MinIO/GCS presigned URL 만료를 대비해 QA 시 새 URL 발급 스크립트를 준비한다.

## 기록
QA 결과/이슈는 `docs/qa/qa-log.md` 또는 Notion QA 보드에
`{날짜, Task ID, 담당자, 이상 여부, 후속 조치}` 형식으로 남긴다.
