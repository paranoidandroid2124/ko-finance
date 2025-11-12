# RAG 딥링크/뷰어 배포 & 롤백 전략

기존 서비스가 사용 중인 플래그 기반 배포·모니터링 흐름을 그대로 재사용한다. 아래 일정/체크리스트는 모든 환경에서 동일한 순서를 권장한다.

## 1. 단계적 롤아웃 계획
| 단계 | 환경 | 플래그/설정 | 검증 항목 |
| --- | --- | --- | --- |
| 0 | 모든 환경 | `RAG_LINK_DEEPLINK=false` (기본) | 기존 RAG 흐름 정상 작동 |
| 1 | Stage | `RAG_LINK_DEEPLINK=true`, `DEEPLINK_VIEWER=false` | Chat 메시지에 딥링크가 노출되는지, 기존 Evidence 패널 UI 영향 없는지 |
| 2 | Stage | `DEEPLINK_VIEWER=true` | `/viewer/[token]` 진입, Prometheus 지표/telemetry 적재 확인 |
| 3 | Prod Canary (5% 사용자) | `DEEPLINK_VIEWER=true` + 접근성 확인 | KPI 모니터링 (딥링크 사용률 ≥ 30%, 실패율 < 3%) |
| 4 | Prod 100% | 모든 플래그 ON | QA/모니터링 리포트 정상화 |

플래그는 `.env` 혹은 Feature Store를 통해 기존과 동일하게 주입한다. Canary 대상은 `plan.feature_flags()` 혹은 Gateway 레벨에서 사용자 그룹을 제한하는 방식으로 구성할 수 있다.

## 2. 성공 기준 (KPI)
| KPI | 설명 | 수집 방법 |
| --- | --- | --- |
| 딥링크 사용률 | `rag.deeplink_opened / rag.deeplink_viewer_ready` | Prometheus 쿼리 |
| 실패율 | `(rag.deeplink_failed + rag.deeplink_viewer_error) / rag.deeplink_opened` | Prometheus |
| QA 정확도 | `scripts/qa/verify_sentence_offsets.py` 통과율 99% 이상 | CI 파이프라인 / 주간 리포트 |
| 사용자 피드백 | Admin 콘솔/지원 티켓 | 수동 모니터링 (주간 헬스 리뷰에서 공유) |

## 3. 모니터링 연동
- Prometheus: `rag_telemetry_events_total` 그래프/알람 (Runbook 참고).  
- Audit Log: `rag.telemetry.*` 액션 필터링으로 사용자 별 이슈 재현.  
- Langfuse: 기존 RAG trace 재사용(추가 구성 불필요).  
- QA 스크립트: 주간 Cron 혹은 CI nightly job으로 `scripts/qa/verify_sentence_offsets.py --fail-on-issues` 실행 → JSON/Markdown 리포트를 Artefact로 업로드.

## 4. 롤백 전략
1. **플래그 롤백**  
   - 즉시 `DEEPLINK_VIEWER=false`로 되돌려 `/viewer` 진입 자체를 막는다.  
   - 필요 시 `RAG_LINK_DEEPLINK=false`까지 내리면 기존 “출처 텍스트” UI만 남기고 모든 딥링크를 숨긴다.  
   - 롤백 후 Prometheus가 `rag.deeplink_opened` 증가하지 않는지 확인.
2. **코드 롤백**  
   - API: FastAPI 배포 파이프라인에서 직전 Stable 태그로 재배포.  
   - 프런트: Next.js 빌드 artefact 롤백(또는 Feature flag).  
3. **데이터/토큰**  
   - 이미 발급된 deeplink 토큰은 TTL(기본 15분) 경과 후 자동 폐기되므로 별도 조치 불필요.  
4. **체크리스트**  
   - [ ] Prometheus Alert 여전히 firing 여부 확인  
   - [ ] Audit 로그에서 실패 이벤트가 0으로 감소했는지 확인  
   - [ ] 고객 지원/Ticket 채널에 공지  
   - [ ] Runbook에 “롤백 수행/시간” 기록

## 5. 주간 헬스 리뷰 템플릿
1. **KPI 대시보드 스크린샷** (딥링크 사용률, 실패율)  
2. **QA 리포트 요약**  
   - 실행 일시 / 샘플 수 / 미스매치 건수  
   - 조치 항목 여부  
3. **사용자 피드백**  
   - 긍정/부정 사례 정리  
4. **향후 액션 아이템**  
   - 접근성 개선, 모니터링 튜닝 등

이 문서는 기존 `docs/ops/ingest_reliability.md`와 동일한 톤으로 관리한다. 변경 시 PR 리뷰어가 Runbook/롤백 문서도 같이 확인하도록 체크리스트에 포함한다.
