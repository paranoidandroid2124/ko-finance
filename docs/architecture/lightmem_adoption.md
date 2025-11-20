# LightMem 도입 검토 메모

## 개요
- **목적**: Nuvien 서비스에서 LLM이 `사용자별 서비스 이용 맥락`(다이제스트 룰, 알림 이력 등)을 기억하도록 하는 외부 메모리 계층 도입을 검토한다.
- **참고 자료**: LightMem(https://github.com/zjunlp/LightMem) 구조 및 논문 `Lightweight and Efficient Memory-Augmented Generation (arXiv:2510.18866)`.
- **핵심 질문**: 토큰 비용을 절감하면서도 사용자 맞춤형 응답/다이제스트 품질을 높일 수 있는가? 개인정보·보안 리스크는 제어 가능한가?

## 진행 현황 (2025-11)
- PlanSettings & Admin Quick Adjust UI가 LightMem watchlist/digest/chat 토글을 저장하고 `/api/v1/user-settings/lightmem`이 사용자 opt-in을 관리한다.
- FastAPI 라우터와 Celery 경로가 공통 `services.lightmem_gate`로 플랜/사용자 권한을 판정한다.
- `services/daily_brief_service.build_digest_preview()`가 Celery `m4.send_filing_digest`에서도 그대로 사용되어 프리뷰·실발송 데이터가 일치한다.
- Digest 프리뷰 API 및 Celery 경로에 관측 로그가 추가되어 뉴스/워치리스트 건수, LLM 노트 유무, 메모리 허용 여부를 추적한다.
- Celery beat 스케줄이 `timeframe=daily/weekly` 파라미터를 사용해 주간 다이제스트까지 자동 발송한다.
- Phase 5 인증 개편(자체 이메일·비밀번호, FastAPI/Next.js Credential Provider, NHN Cloud Email REST, 인증 전용 Redis 레이트리밋) 문서와 코드가 반영돼 핵심 백엔드 기능을 확보했다.

---

## 기대 효과 (Strengths)
1. **토큰 비용 절감**
   - Sensory 단계에서 프롬프트 압축(`gpt-4o-mini` 등) → 5~10배 이상 토큰 절감 기대.
   - 다이제스트/대화에서 반복되는 문맥 제거로 API 호출 비용 감소.

2. **맥락 유지 & 개인화**
   - Short-Term Memory: 세션 요약을 Redis/PlanStore에 저장해 직전 대화 맥락 유지.
   - Long-Term Memory: 사용자 선호·히스토리를 Qdrant 등 벡터 스토어에 저장 → 개인화 응답 가능.

3. **보고서 품질 향상**
   - 다이제스트/Weekly Brief에 필요한 핵심 이벤트만 남겨 정제된 결과 제공.
   - RAG(정적 근거) + LightMem(서비스 맥락) 병행 시 “근거 + 개인화”가 동시에 가능.

4. **Plan Tier 차별화**
   - Pro/Enterprise 플랜에서 LightMem 기능을 활성화해 서비스 밸류 추가.

---

## 향후 우선 과제 (Backlog)
1. **Rate limit & 큐 분리**
   - Redis 기반 토큰 버킷으로 LLM 호출·LightMem compose 요청을 분당/초당 제한하고, hit 시 즉시 폴백을 반환한다.
   - 인증 트래픽은 AUTH_RATE_LIMIT_REDIS_URL 기반 Redis를 사용하도록 분리해 LightMem과 공유되지 않도록 했고, 향후 지표/알림을 분리해 운영한다.
   - Celery에서 watchlist/digest/chat 전용 큐를 분리하고 워커 수·prefetch 한도를 기능별로 조정한다.

2. **API 키 분할·로테이션**
   - 기능별(다이제스트, 워치리스트, 챗봇)로 별도의 API 키를 사용하고, 주/백업 키 자동 failover 로직을 추가한다.
   - Secret Manager/Helm values에 키 목록을 등록해 CI/CD에서 롤링 교체 가능하도록 표준화한다.

3. **캐시·폴백 계층**
   - Digest/Chat에 Redis TTL 캐시를 도입해 동일 사용자 요청 반복 시 LLM 재호출을 줄이고, rate limit hit 시 템플릿 기반 폴백을 제공한다.
   - Watchlist 개인화 노트를 세션 캐시에 저장해 Celery 재시도에서도 재사용한다.

4. **관측·모니터링**
   - Prometheus 또는 Langfuse에 LightMem 허용 여부, 토큰 사용량, rate limit hit, 폴백 비율을 적재하고 Admin Ops 대시보드에서 확인한다.
   - Plan/user opt-in 변경 시 Audit 로그를 남겨 추후 감사에 대비한다.

5. **테스트·시뮬레이션**
   - 플랜×사용자 opt-in 조합별 LightMem 동작을 자동 검증하는 단위/통합 테스트를 확장하고, Celery digest 파이프라인 E2E 시나리오를 추가한다.

6. **문서·환경 구성**
   - 새 환경 변수(기본 사용자 ID, rate limit 설정, API 키 목록 등)를 Helm/Secret Manager/README에 반영하고 운영자가 값을 관리할 절차를 정의한다.
   - 개인정보/데이터 보존 정책 문서를 최신 상태로 유지한다.

---

## 잠재 리스크 & 이슈 (Weaknesses / Risks)
1. **개인정보 & 규제 리스크**
   - 사용자 이용 기록을 저장하므로 목적 고지, 동의, 삭제권, 국외 이전 등 준수 필요.
   - 메모리 항목이 민감한 비공개 정보일 수 있음 → 암호화·접근 통제 필수.

2. **스토리지 인프라 복잡도**
   - Redis + Qdrant + Secret Manager 등 다양한 외부 스토어 필요.
   - nightly offline update(Celery) 등 배치 파이프라인 관리 부담.

3. **Fallback / 장애 처리**
   - 압축 모델 실패, 저장소 장애 시 기존 RAG만으로 동작하도록 degrade 전략 필요.

4. **운영 모니터링**
   - 토큰 절감 효과, 메모리 조회율 등 지표가 없으면 유지보수가 어려움.
   - Audit log, Langfuse 등의 추가 연동 필요.

---

## 필수 구성 요소 (Must-Haves)
1. **프롬프트 압축 모듈 (Sensory Layer)**
   - `services/lightmem/preprocessor.py` (LiteLLM `gpt-4o-mini` 기반 압축).
   - 토큰 절감 수치 로깅(Langfuse).

2. **세션 요약 저장소 (Short-Term Memory)**
   - Redis/PlanStore에 `SummaryEntry(topic, highlights, expires_at)` 저장, TTL 1~2시간.
   - 세션 종료 시 LTM 후보 큐에 push.

3. **장기 메모리 (Long-Term Memory)**
   - Qdrant `memory_store` 컬렉션 (embedding_dim=384 등).
   - Celery nightly job `memory_sleep_update` → 중복 제거, 재요약, 스코어링.
   - 삭제 요청/보관 기한 정책 반영(예: 180일 이상 미사용 데이터 삭제).

4. **MemoryService (Prompt Composer)**
   - `compress → load_session → retrieve_long_term → compose_prompt → generate` 흐름.
   - fallback 로직(실패 시 RAG-only) 포함.

5. **Feature Flag & Plan 통제**
   - `PlanContext.memory_enabled` 등 플래그로 Pro 이상에서만 활성화.
   - Admin Ops에 enable/disable UI 제공 (운영자 전용).

- 저장 데이터 AES/Fernet 암호화, 키는 현재 `.env`/환경 변수로 관리(향후 GCP 전환 시 Secret Manager로 이관 예정).
- 접근 권한은 서비스 계정 한정, Audit 로그 필수.
- Privacy Policy 업데이트: “개인화 목적, 학습 재사용 금지” 명시.

---

## 적용 시나리오 예시
1. **워치리스트 대화**
   - Sensory: 인사/불필요 정보 제거 → 토큰 감소.
   - STM: 최근 룰 상태 요약 유지 → “어제 중단된 룰” 설명 가능.
   - LTM: 사용자 선호(삼성SDI, 감성 API 이슈 기록) 바탕 개인화 응답.

2. **다이제스트 생성**
   - 하루 동안 이벤트를 topic별로 요약 → 마감 시 핵심만 템플릿 주입.
   - Weekly Digest 생성 전에 sleep-time offline update로 중복 제거.

3. **Admin Ops 분석**
   - 장기 메모리를 통해 사용자별 긴급 이슈/알림 패턴 파악.
   - `token_monitor` + Langfuse로 비용/성능 효과 추적.

---

## 체크 리스트 (도입/운영 전에 확인)
- [x] Plan Tier & Feature flag 설계 (Pro 이상만 사용).
- [ ] Redis/Qdrant 준비 상태 health check 및 모니터링.
- [ ] Rate limit / fallback 처리 로직 구현.
- [ ] 개인정보 동의/보관/삭제 정책 문서에 반영 및 자동화.
- [ ] AES 암호화 + 키 관리 체계 마련(환경 변수 → Secret Manager 연동).
- [ ] Audit log & Langfuse log 연동, 메트릭 대시보드 구축.
- [ ] nightly batch(Celery) 스케줄링 구성.
- [ ] 운영자 전용 Admin UI 분리(별도 도메인/Single Sign-On).
- [ ] 토큰 절감/응답 품질 A/B 테스트 계획 수립.

---

## 결론
LightMem는 **감각기억 → 단기기억 → 장기기억**의 3단 구조로 LLM에 외부 메모리를 제공하여 토큰 절감과 맞춤형 응답을 동시에 달성할 수 있는 프레임워크이다. 다이제스트, 워치리스트 대화 등 서비스 측면에 바로 적용 가능하지만, 개인정보 처리와 스토리지 인프라, fallback 전략 등 운영 측면의 준비가 필수적이다. 위 체크리스트를 충족하는 범위에서 Pro Tier를 시작점으로 단계적 도입을 검토한다.
