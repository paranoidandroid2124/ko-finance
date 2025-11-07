# News Metadata Storage Policy

목표는 기사 “전문”을 보관하지 않고, 분석과 UI, 알림에 필요한 최소한의 메타데이터만 저장하는 것입니다.

## 저장하는 필드
- `source`, `url`, `headline`, `summary` (최대 480자)
- `published_at`, `ticker`(선택), `sentiment`, `topics`, `source_reliability`
- LLM 분석 근거는 문장 단위(rationale)만 JSON으로 보관합니다.
- 원문 텍스트(`original_text`)는 분석 직후 폐기되며 DB에 적재되지 않습니다.

## 데이터 보존
- `NEWS_RETENTION_DAYS`(기본 45일) 이후에는 `NewsSignal`, `NewsObservation`, `NewsWindowAggregate` 데이터를 정기적으로 삭제합니다.
- Celery 태스크 `m2.cleanup_news_signals`가 보존 기간을 초과한 레코드를 제거합니다.

## KOGL / 저작권 준수
- 기사 전문을 저장하지 않고, 원문 URL과 출처만 노출합니다.
- KOGL 기반 데이터(향후 도입 시)는 source 메타데이터에 라이선스 유형을 함께 기록하고 UI에서 배지로 표시합니다.

## 환경 변수 요약
| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `NEWS_SUMMARY_MAX_CHARS` | 480 | 요약 길이 제한(문장 트렁케이션) |
| `NEWS_RETENTION_DAYS` | 45 | 메타데이터 보존 기간(일) |
| `NEWS_SUMMARY_CACHE_TTL_MINUTES` | 1440 | 온디맨드 요약 캐시 지속 시간(분) |

## 운영 팁
- 스케줄러에서 하루 1회 `m2.cleanup_news_signals.delay()`를 실행해 보존 정책을 유지합니다.
- 요약 길이를 더 줄이고 싶거나 별도 규칙이 필요하면 `NEWS_SUMMARY_MAX_CHARS` 값을 Secret Manager에서 조정하세요.

## 온디맨드 요약 캐시
- `services.news_summary_service`는 요청 시 요약을 생성해 `uploads/news/summary_cache.json`에 저장합니다.
- 캐시는 `NEWS_SUMMARY_CACHE_TTL_MINUTES` 설정 동안만 유지하며, 만료되면 다시 생성합니다.
- 입력으로는 헤드라인·피드 요약·LLM 분석 결과(rationale)만 사용하고, 원문 전체 텍스트는 저장하지 않습니다.
- 캐시 실패 시에는 친근한 톤의 기본 문구(헤드라인 기반)로 응답해 UI 지연을 방지합니다.
