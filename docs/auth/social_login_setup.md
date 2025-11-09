# 소셜 로그인 구성 가이드

## 1. 의존성 설치

```bash
cd web/dashboard
pnpm add next-auth@beta @auth/pg-adapter pg
```

## 2. 환경 변수

`.env.local`(로컬) 및 배포 환경에 아래 항목을 채웁니다. 샘플은 `web/dashboard/.env.local.example` 참고.

- `AUTH_SECRET`: `npx auth secret`으로 생성.
- `AUTH_TRUST_HOST=true`
- 데이터베이스: `DATABASE_URL` 혹은 `DB_USER/DB_PASSWORD/DB_HOST/DB_NAME/DB_PORT`
- 각 Provider 키
  - `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`
  - `AUTH_KAKAO_ID`, `AUTH_KAKAO_SECRET`
  - `AUTH_NAVER_ID`, `AUTH_NAVER_SECRET`

## 3. OAuth 콘솔 설정

| Provider | 콘솔 위치 | Redirect URI 예시 |
| --- | --- | --- |
| Google | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) | `http://localhost:3000/api/auth/callback/google`, `https://<도메인>/api/auth/callback/google` |
| Kakao | [Kakao Developers](https://developers.kakao.com/) → 카카오 로그인 | `http://localhost:3000/api/auth/callback/kakao`, `https://<도메인>/api/auth/callback/kakao` |
| Naver | [NAVER Developers](https://developers.naver.com/) → 애플리케이션 | `http://localhost:3000/api/auth/callback/naver`, `https://<도메인>/api/auth/callback/naver` |

> **참고**: Kakao는 Redirect URI가 하나라도 다르면 `KOE006` 오류가 발생하므로, 로컬/운영 URI를 정확히 등록하고 이메일 제공 동의 항목을 켜야 합니다.

## 4. DB 스키마

`db/migrations/001_add_plan_and_role.sql` 실행으로 `users` 테이블에 아래 컬럼을 추가합니다.

- `plan_tier` (`free`/`pro`/`enterprise`) – 기본값 `free`
- `role` (`user`/`admin`) – 기본값 `user`
- `last_login_at` (`TIMESTAMPTZ`)

## 5. FastAPI 연동 (다음 단계 미리보기)

1. `pip install pyjwt`.
2. `web/auth.py`에서 `AUTH_SECRET`을 이용해 JWT 검증.
3. `get_current_user`, `require_min_plan` 의존성을 라우터에 주입.

이후 Toss 결제 웹훅에서 `users.plan_tier`를 갱신하면 Auth.js JWT 콜백이 자동으로 새로운 플랜을 반영하게 됩니다.
