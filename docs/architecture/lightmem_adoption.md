# LightMem 도입 검토 메모

## 개요
- **목적**: K-Finance 서비스에서 LLM이 `사용자별 서비스 이용 맥락`(다이제스트 룰, 알림 이력 등)을 기억하도록 하는 외부 메모리 계층 도입을 검토한다.
- **참고 자료**: LightMem(https://github.com/zjunlp/LightMem) 구조 및 논문 `Lightweight and Efficient Memory-Augmented Generation (arXiv:2510.18866)`.
- **핵심 질문**: 토큰 비용을 절감하면서도 사용자 맞춤형 응답/다이제스트 품질을 높일 수 있는가? 개인정보·보안 리스크는 제어 가능한가?

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
- [ ] Plan Tier & Feature flag 설계 (Pro 이상만 사용).
- [ ] Redis/Qdrant가 준비되었는지 health check.
- [ ] 압축 실패/fallback 처리 로직 구현.
- [ ] 개인정보 동의/보관/삭제 정책 문서에 반영.
- [ ] AES 암호화 + 키 관리 체계 마련(현재는 환경 변수, GCP 전환 시 Secret Manager 연동).
- [ ] Audit log & Langfuse log 연동.
- [ ] nightly batch(Celery) 스케줄링 구성.
- [ ] 운영자 전용 Admin UI 분리(별도 도메인/Single Sign-On).
- [ ] 토큰 절감/응답 품질 A/B 테스트 계획 수립.

---

## 결론
LightMem는 **감각기억 → 단기기억 → 장기기억**의 3단 구조로 LLM에 외부 메모리를 제공하여 토큰 절감과 맞춤형 응답을 동시에 달성할 수 있는 프레임워크이다. 다이제스트, 워치리스트 대화 등 서비스 측면에 바로 적용 가능하지만, 개인정보 처리와 스토리지 인프라, fallback 전략 등 운영 측면의 준비가 필수적이다. 위 체크리스트를 충족하는 범위에서 Pro Tier를 시작점으로 단계적 도입을 검토한다.
