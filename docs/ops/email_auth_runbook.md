# 이메일·비밀번호 인증 운영 가이드

## 1. 구성 개요
- **FastAPI**: `/api/v1/auth/*` 라우터 (`services/auth_service.py`)가 Argon2 해시, `auth_tokens`, `session_tokens`, 감사 로그, rate limit를 처리합니다.
- **Next.js Auth.js**: Credential Provider가 FastAPI `/auth/login`을 호출하고, JWT 콜백에서 `/auth/session/refresh` 결과를 반영합니다. 로그아웃 이벤트는 FastAPI `/auth/logout`으로 전파됩니다.
- **메시지 발송**: `services/email_service.py` → `notification_service.py`가 NHN Cloud Email REST API(`NHN_APP_KEY`, `NHN_SECRET_KEY`)를 사용합니다.
- **Rate limit**: 인증 전용 Redis (`AUTH_RATE_LIMIT_REDIS_URL`, `AUTH_RATE_LIMIT_PREFIX`)에서 버킷을 관리합니다.

## 2. 환경 변수
| 구분 | 키 | 설명 |
| --- | --- | --- |
| NHN Email | `NHN_APP_KEY`, `NHN_SECRET_KEY`, `NHN_EMAIL_BASE_URL`, `NHN_SENDER_ADDRESS`, `NHN_SENDER_NAME` | 콘솔에서 발급된 app key / secret / 발신자 정보. `NHN_EMAIL_BASE_URL`는 기본값 `https://email.api.nhncloudservice.com`. |
| SMTP 폴백 | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` | NHN SMTP를 사용할 경우에만 설정. 기본 제공자는 `ALERT_EMAIL_PROVIDER=nhn_rest`. |
| 인증 Rate Limit | `AUTH_RATE_LIMIT_REDIS_URL`, `AUTH_RATE_LIMIT_PREFIX` | 인증 전용 Redis/네임스페이스. 미설정 시 LightMem 값으로 폴백하지만 운영에서는 반드시 분리. |
| NextAuth ↔ FastAPI | `API_BASE_URL` (또는 `NEXT_PUBLIC_API_BASE_URL`) | Next.js 서버에서 FastAPI REST를 호출할 때 사용하는 베이스 URL. |
| 브랜드/연락처 | `APP_BRAND_NAME`, `SUPPORT_EMAIL`, `ALERT_EMAIL_FROM` | 이메일 템플릿 및 지원 연락처에 사용. |

## 3. 배포/변경 시 체크
1. **NHN 콘솔**에서 새 appKey/secret을 발급할 경우 `.env` → Secret Manager → Kubernetes/Compose 환경변수까지 갱신.
2. 발신 도메인을 변경하면 NHN Console에서 SPF/DKIM/DMARC 인증을 완료해야 함.
3. 인증 rate limit Redis를 교체할 경우 `AUTH_RATE_LIMIT_PREFIX`로 네임스페이스를 바꾸고, 구 Redis 키는 수동 삭제.
4. Next.js `API_BASE_URL`을 변경하면 미들웨어/Route Handler에서 같은 값을 사용하도록 동기화.

## 4. 테스트 절차
### 4.1 이메일 발송
1. `.env`에 NHN 자격 정보를 입력하고 `python -m services.email_service` 같은 단발 테스트 스크립트로 health check (`send_verification_email(...)`).
2. FastAPI `/api/v1/auth/register` 호출 → 가입 성공/이메일 발송 202 로그 확인 → 실제 메일 수신 확인.
3. `/api/v1/auth/password-reset/request` → 메일 링크 클릭 후 `/auth/reset/[token]` 페이지에서 비밀번호 변경.
4. SMTP 대신 REST를 사용했는지 NHN 콘솔 로그 및 `notification_service` 로그로 검증.

### 4.2 Refresh / Logout
1. Next.js 로그인 후 브라우저 devtools에서 Access 토큰 만료 시각(15분)을 확인하고, 15분 이상 기다린 뒤에도 페이지 이동이 정상인지 확인 (자동 refresh 성공).
2. `session.error === "RefreshAccessTokenError"`가 발생하면 토스트/배너가 “세션이 만료되어 다시 로그인해 주세요” 메시지를 표시하는지 QA.
3. FastAPI `/api/v1/auth/logout` API를 Postman으로 호출해 특정 `session_id`를 revoke → Next.js에서 새 API 호출 시 401 → 자동 signOut되거나 토스트가 뜨는지 확인.

### 4.3 Rate limit
1. 동일 이메일/아이피로 로그인 실패를 5회 이상 반복 → `/api/v1/auth/login`이 423 `account_locked`를 반환하는지 확인.
2. `AUTH_RATE_LIMIT_REDIS_URL`의 Redis에서 `auth:*` 키가 생성되는지 검사 (`redis-cli --scan | grep auth:`).

## 5. 장애 대응
| 증상 | 조치 |
| --- | --- |
| NHN REST 4xx/5xx | NHN 콘솔에서 발신 제한/잔여 포인트 확인 → `NHN_SECRET_KEY` 만료 여부 확인 → 필요 시 SMTP 폴백 사용 (`ALERT_EMAIL_PROVIDER=nhn_smtp`). |
| 이메일 바운스 증가 | NHN 웹훅(`/nhn/email-webhook`) 로깅 후 서프레션 리스트 업데이트 → 문제 계정의 메일 주소 수정/정지. |
| Access 토큰 반복 401 | Next.js `session.error` 확인 → FastAPI `/auth/session/refresh` 로그 확인 → `session_tokens` 레코드가 revoke 되었는지 검사. |
| Rate limit 오탐 | Redis 키 삭제(`DEL auth:auth.login.ip:...`) 후 제한값 조정 → `.env`의 `AUTH_LOGIN_FAILURE_LIMIT`, `_WINDOW_SECONDS` 값 재검토. |

## 6. 문서/참고
- `docs/auth/email_password_design.md` – 데이터 모델, API, UX, 이메일 정책, rate limit 등 전체 설계.
- `services/email_service.py` – NHN 템플릿 렌더링 코드.
- `services/auth_service.py` – 비밀번호 해시, 토큰, Refresh, Logout 로직.
- `docs/guidance_prompt.txt` – Phase 5 진행 상황과 남은 TODO.
