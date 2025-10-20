# M1 Performance & Readiness Notes

## 1. 현재 지표 현황
- **SLO**: 공시 감지 → 알림 P95 < 60s (미측정)
- **추출 품질**: Self-check faithfulness > 0.8 일괄 저장 (로그 기반)
- **인덱싱**: RAG 인덱싱 완료 상태 → `analysis_status='INDEXED'`

## 2. 수집 권장 메트릭
| 구간 | 메트릭 | 수집 방법 |
|------|--------|-----------|
| Ingest | DART API 호출 지연, 다운로드 크기 | `logging.info` + Prometheus counter |
| Parse | PDF → chunk 처리 시간 | `time.perf_counter()` 측정, 로그로 출력 |
| LLM | classify/extract/self-check 응답 시간, fallback 여부 | `llm.llm_service._safe_completion`에 라벨 추가 |
| Alarms | 텔레그램 전송 성공/실패 카운터 | `services/notification_service` 로그 |
| RAG | 임베딩 요청 시간, Qdrant upsert/search 지연 | `services/vector_service` 로그 |

## 3. 단기 최적화 아이디어
- **LLM 호출 병렬화**: classify → extract 순차 호출 대신 비동기화 검토 (추후)
- **Chunk 필터링**: 텍스트 길이 하한 조정 (`MIN_PARAGRAPH_LENGTH`)으로 임베딩 비용 절감
- **Qdrant 세션 재사용**: 현재 Lazy client 재사용으로 연결 비용 감소 (완료)

## 4. 권장 점검 루틴
1. 마이그레이션 직후: `scripts/migrate_schema.py` 로그, DB 상태 확인
2. 일일 배치: `scripts/seed_data.py` 실행 후 처리 시간 기록
3. 주간: Langfuse/Preset 대시보드로 self-check 실패율, 알림 지연 검토

## 5. 운영 체크리스트 업데이트 포인트
- 비상 연락망, 장애 티켓 템플릿
- Celery 워커 스케일링 기준 (큐 길이, 처리 시간)
- 실시간 DART 스케줄링 도입 시 beat 설정 문서화 필요
