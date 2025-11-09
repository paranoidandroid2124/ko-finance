# GCP 배포 시 Auth/OAuth 비밀 관리

## 1. Secret Manager 사용
- `AUTH_SECRET`, `AUTH_GOOGLE_*`, `AUTH_KAKAO_*`, `AUTH_NAVER_*`, `DATABASE_URL` 등 민감 값은 Secret Manager에 보관합니다.
- Cloud Run 서비스에 연결할 때 **환경 변수 → Secret 참조** 기능을 사용하면 파일 없이 주입할 수 있습니다.
- 권한은 최소화(`roles/secretmanager.secretAccessor`)하고, 비밀 값 변경 시 최신 버전만 참조하도록 Cloud Run 재배포가 필요합니다.

## 2. Cloud Run/Build 설정
- **Cloud Run**: `AUTH_SECRET`, `AUTH_TRUST_HOST=true`, `AUTH_URL=https://<서비스도메인>`을 환경 변수로 주입. FastAPI 컨테이너에도 동일한 `AUTH_SECRET`을 넣어 JWT 검증이 일치하도록 합니다.
- **Cloud Build / GitHub Actions**: 빌드 단계에서만 Secret을 가져와 `pnpm build` 또는 `uvicorn` 실행 전에 환경 변수로 노출하고, 로그에 출력되지 않도록 `set +x` 등으로 보호합니다.

## 3. DB 연결
- Cloud SQL을 쓸 경우 `INSTANCE_CONNECTION_NAME`을 비밀이 아닌 구성 변수로 두고, DB 사용자/비밀번호는 Secret Manager를 통해 주입합니다.
- Next.js(Auth.js)에서는 unix socket(`/cloudsql/INSTANCE`) 또는 Cloud SQL 커넥터를 사용하도록 `src/auth.ts`에서 환경 변수 기반으로 분기합니다.

## 4. 로컬 개발 대비 차이
- 로컬에서는 `.env.local` 파일로 테스트 키를 사용해도 되지만, Git에 반영되지 않도록 유지합니다.
- 운영 키는 오직 Secret Manager/CI 변수로만 관리하고, 문서나 채팅에 평문으로 남기지 않습니다.

## 5. 체크리스트
1. Secret Manager에 `auth-secret`, `google-oauth`, `kakao-oauth`, `naver-oauth`, `db-credentials` 등으로 저장.
2. Cloud Run(Next.js/FastAPI) 서비스 설정에서 각 비밀을 환경 변수로 매핑.
3. OAuth 콘솔에 Cloud Run 도메인 기반 redirect URI 등록.
4. 배포 후 `/api/auth/signin` 및 `/api/v1/me` 호출로 JWT가 정상 검증되는지 확인.
