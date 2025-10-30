***

title: 인증 및 기타 헤더 설정
description: 토스페이먼츠 API를 사용하기 위해 필요한 인증과 헤더 설정 방법입니다.
keyword: Authorization, Basic, base64, 인코딩, 인증, 헤더, 시크릿 키, 멱등성, 멱등키, Idempotency, Idempotent, 중복 요청, 영문 헤더, 테스트 헤더, 선택 요청 헤더, 에러 재현
-----------------------------------------------------------------------------------------------------------------------------------

# 인증 및 기타 헤더 설정

토스페이먼츠 API를 사용하기 위해 필요한 인증과 헤더 설정 방법입니다.

## 인증 헤더

토스페이먼츠 API는 일반적으로 Basic 인증에 시크릿 키를 사용합니다. 시크릿 키는 [개발자센터](https://developers.tosspayments.com/my/api-keys)에서 확인할 수 있습니다.

### 시크릿 키로 인증하기

**1.** [개발자센터](https://developers.tosspayments.com/my/api-keys)에서 내 시크릿 키를 확인하세요.

*   로그인했다면, 아래 키값도 **내 테스트 시크릿 키로 바뀌어요**.
*   로그인하지 않고 문서에 있는 테스트 시크릿 키도 결제 연동에 사용할 수 있지만, 결제 내역을 확인할 수 없어요.

```
<SecretKey />
```

`test_sk`로 시작하는 시크릿 키는 테스트 키입니다. `live_sk`로 시작하는 시크릿 키는 라이브 키입니다. 시크릿 키는 외부에 절대 노출되면 안 됩니다.

**2.** 시크릿 키 뒤에 `:`을 추가하고 [base64](/resources/glossary/base64)로 인코딩하세요. **콜론을 빠트리지 않도록 주의하세요.**

시크릿 키를 복사해 사용할 때는 주의가 필요합니다. 시크릿 키를 base64로 인코딩할 때 UTF-8 BOM 문자가 포함되면 결과가 77u/로 시작할 수 있습니다. 이 경우 BOM이 없는 UTF-8 형식으로 다시 인코딩해주세요.

```bash theme="grey" copyable="false" feedbackable="false"
base64('<SecretKey />:')
        ─────────────────┬───────────────── ┬
                     secretKey              :
                   발급받은 시크릿 키           콜론
```

아래 명령어를 터미널에서 실행하면 인코딩된 값을 얻을 수 있습니다.

```bash
echo -n '<SecretKey />:' | base64
```

**3.** 인코딩된 값을 API의 Basic 인증헤더에 사용하세요.

```bash
Authorization: Basic {ENCODED_SECRET_KEY}
```

### Basic 인증 방식이란

```plain theme="grey" copyable="false" feedbackable="false"
Authorization: Basic base64({USERNAME}:{PASSWORD})
```

[HTTP Basic 인증 방식](/resources/glossary/basic-auth)은 클라이언트에서 base64로 인코딩된 사용자 ID, 비밀번호 쌍을 인증 정보(credentials) 값으로 사용합니다. 사용자 ID와 비밀번호는 위와 같이 콜론으로 구분합니다. Base64로 인코딩한 정보는 쉽게 디코딩이 가능해서 Basic 인증은 반드시 [HTTPS](/resources/glossary/http-protocol) 및 [TLS](/resources/glossary/tls)와 함께 사용해야 합니다.

토스페이먼츠 API는 시크릿 키를 사용자 ID로 사용하고, 비밀번호는 사용하지 않습니다. 비밀번호가 없다는 것을 알리기 위해 시크릿 키 뒤에 콜론을 추가합니다.

## 멱등키 헤더

[멱등성](https://ko.wikipedia.org/wiki/%EB%A9%B1%EB%93%B1%EB%B2%95%EC%B9%99)은 연산을 여러 번 하더라도 결과가 달라지지 않는 성질을 뜻합니다. API 요청에서 멱등성을 보장하면 같은 요청이 여러 번 일어나도 항상 첫 번째 요청과 같은 결과가 돌아옵니다.

멱등키를 사용하면 민감한 API 요청이 반복적으로 일어나는 문제를 막을 수 있고, 네트워크 이슈나 타임아웃 문제로 응답을 받지 못했을 때도 안전하게 같은 요청을 다시 보낼 수 있습니다. 멱등성의 개념과 구현 방법은 [토스페이먼츠 블로그 포스트](/blog/what-is-idempotency)에서 더 자세히 살펴보세요.

### 멱등키 사용하기

요청 헤더에 `Idempotency-Key`를 추가하면 멱등한 요청을 보낼 수 있습니다.

```plain theme="grey" copyable="false" feedbackable="false"
Idempotency-Key: {IDEMPOTENCY_KEY}
```

*   멱등키는 [UUID](/resources/glossary/uuid)와 같이 충분히 무작위적인 고유 값으로 생성해주세요. 최대 길이는 300자입니다.

*   멱등키는 처음 요청에 사용한 날부터 15일간 유효합니다. 처음 요청한 날부터 15일이 지났다면 새로운 멱등키로 요청하세요.

아래와 같이 API 요청에 멱등키 헤더를 사용하면 같은 요청이 두 번 일어나도 실제로 요청이 이루어지지 않고 첫 번째 요청 응답과 같은 응답을 보내줍니다.

```bash {5}
curl --request POST \
  --url https://api.tosspayments.com/v1/payments/confirm \
  --header 'Authorization: Basic dGVzdF9nc2tfZG9jc19PYVB6OEw1S2RtUVhrelJ6M3k0N0JNdzY6' \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: SAAABPQbcqjEXiDL' \
  --data '{"paymentKey":"5zJ4xY7m0kODnyRpQWGrN2xqGlNvLrKwv1M9ENjbeoPaZdL6","orderId":"a4CWyWY5m89PNh7xJwhk1","amount":15000}'
```

*   토스페이먼츠 서버는 상점에서 API 요청 헤더로 보낸 멱등키와 API 키, API 주소, HTTP 메서드 조합이 같은 요청이 있는지 확인해서 멱등성을 보장합니다. 따라서 API 키, API 주소, HTTP 메서드가 다르다면 같은 멱등키를 사용해도 괜찮습니다.
*   멱등키 관리를 위한 별도의 데이터베이스나 테이블을 사용하면 서버 성능 및 보안 및 유지보수 측면에서 장점이 있습니다. 단순한 데이터 구조라면 Redis와 같은 [키-값(K-V) 저장소](https://en.wikipedia.org/wiki/Key%E2%80%93value_database)를 사용해도 괜찮습니다. 멱등키와 관련된 데이터의 복잡도, 유효 기간 관리, 확장성, 성능 등을 고려해서 적절한 데이터베이스 유형을 선택하세요.
*   멱등한 요청에서 에러가 반환되었을 때 멱등키를 변경해서 동일한 요청을 재시도하는 것은 위험이 있습니다. 정확한 오류 원인을 토스페이먼츠로부터 확인한 다음에 다시 요청을 보내주세요.

토스페이먼츠에서 제공하는 모든 POST 메서드 API는 요청에 멱등키 헤더를 추가해서 사용할 수 있습니다. 그 외 메서드는 [자체적으로 멱등성을 보장](https://developer.mozilla.org/ko/docs/Glossary/Idempotent)합니다. GET 요청에 추가하는 멱등키 헤더는 무시됩니다.

### 에러 처리하기

멱등키 헤더를 사용할 때 발생할 수 있는 에러는 두 가지가 있습니다. 멱등키 길이가 300자보다 길면 HTTP `400 - INVALID_IDEMPOTENCY_KEY`가 돌아옵니다. 300자 이하로 멱등키를 다시 만들어주세요. 첫 번째 요청이 처리 중일 때 같은 요청을 다시 보내면 HTTP `409 - IDEMPOTENT_REQUEST_PROCESSING` 에러가 돌아옵니다. 이 에러가 돌아오면 다시 한번 요청해서 응답을 확인하세요.

| HTTP Status Code | 에러 코드                       | 메시지                          |
| ---------------- | ------------------------------- | ------------------------------- |
| `400`            | `INVALID_IDEMPOTENCY_KEY`       | 멱등키는 300자 이하여야 합니다. |
| `409`            | `IDEMPOTENT_REQUEST_PROCESSING` | 이전 멱등 요청이 처리중입니다.  |

## 선택 요청 헤더

API 요청에 추가할 수 있는 선택 헤더 목록입니다.

### 영문으로 응답받기

모든 필드와 오류 메시지는 기본적으로 한글로 제공됩니다. 영문으로 에러 메시지 및 응답 본문을 받고 싶다면 API 요청 헤더에 `Accept-Language`를 포함하세요. 사용자가 입력한 값을 제외한 모든 필드가 영어로 변환됩니다.

```plain theme="grey" copyable="false" feedbackable="false"
Accept-Language: en-US
```

### 팝업 차단 에러 방지하기

결제 과정에서 팝업 차단 에러가 나는 것을 방지하기 위해 아래와 같이 HTTP 헤더를 설정해주세요. [COOP(Cross-Origin-Opener-Policy)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy)은 웹 사이트에서 팝업 창이나 새 탭을 열 수 있는지 정하는 보안 정책입니다.

```plain theme="grey" copyable="false" feedbackable="false"
Cross-Origin-Opener-Policy: same-origin-allow-popups
```

### 테스트 환경에서 에러 재현하기

테스트 환경에서 에러를 재현하고 싶다면 토스페이먼츠 API 테스트 헤더를 사용하세요.

```plain theme="grey" copyable="false" feedbackable="false"
TossPayments-Test-Code: {TEST_CODE}
```

*   `{TEST_CODE}` 자리에 재현하고 싶은 [에러 코드](/reference/error-codes)를 넣고 API를 실행하세요.
*   `test_` 로 시작하는 테스트 API 키를 사용해주세요. 라이브 환경에서는 테스트 코드 헤더가 무시됩니다.

예를 들어, 카드 번호 결제 API에 잘못된 유효기간을 넣었을 때 돌아오는 응답을 보고 싶다면 아래와 같이 `INVALID_CARD_EXPIRATION`를 테스트 헤더에 추가하세요.

```bash
curl --request POST \
  --url https://api.tosspayments.com/v1/payments/key-in \
  --header 'Authorization: <AuthHeader />' \
  --header 'Content-Type: application/json' \
  --header 'TossPayments-Test-Code: INVALID_CARD_EXPIRATION' \
```
