***

title: 자동결제(빌링) API로 연동하기
description: API만 사용해서 구매자의 카드 정보를 등록하고 자동결제를 연동하는 서버 투 서버 방법을 알아보세요.
keyword: 정기 결제, 빌링, billing, 구독, billingKey, 빌링키, 구독 결제, 빌링키 발급, schedule, scheduling, cron, cron job, 스케줄링, 스케줄러, 빌링키 관리, 추가 계약, 카드 등록, 결제 주기 변경, 원하는 시점, 특정 시점
----------------------------------------------------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 자동결제(빌링) API로 연동하기

{description}

구매자의 카드를 처음 한 번 등록할 때 본인인증을 마치고 [빌링키](/guides/v2/billing#빌링키란)를 발급하면, 별도의 본인인증 없이 간편하게 빌링키로 계속 결제할 수 있습니다.
API로 자동결제를 연동하면 본인인증은 직접 구현해야 합니다. 결제창을 띄우는 [SDK 방식](/guides/v2/billing/integration)으로 연동하면 토스페이먼츠에서 휴대폰 본인인증을 제공합니다.

\* 빌링키 발급 API는 신규 계약을 받지 않는 서비스입니다. 자세한 내용은 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

![자동결제-흐름](https://static.tosspayments.com/docs/billing/billing-overview.png)

## API 키 준비하기

개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 **API 개별 연동 키 > 시크릿 키**를 확인하세요.

토스페이먼츠와 전자결제 계약 전이어도 회원가입하면 나만의 테스트 상점 키를 확인하고 테스트 결제내역, 웹훅 등 기능을 사용할 수 있어요. 로그인한 상태라면 코드의 키값이 테스트 상점 키입니다. 로그인하지 않아도 문서 테스트 키로 테스트 연동할 수 있어요.

토스페이먼츠와 전자결제 계약을 완료했다면 개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 자동결제(빌링)로 계약된 상점아이디(MID)를 선택한 다음에 시크릿 키를 확인하세요. [테스트 키와 라이브 키의 차이점](/reference/using-api/api-keys#api-키-이해하기)도 확인하고 연동을 시작하세요.

\* 자동결제는 추가 리스크 검토 및 계약 후 사용할 수 있습니다. 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

```js title="API 개별 연동 키"
// API 개별 테스트 연동 키
// 토스페이먼츠에 회원가입하기 전이라면 아래 키는 문서 테스트 키입니다.
// 토스페이먼츠에 회원가입하고 로그인한 상태라면 아래 키는 내 테스트 키입니다.
const secretKey = "<SecretKey />";
```

***

## 1. 빌링키 발급하기

자체 UI를 제작해서 구매자의 카드 번호, 카드 유효기간, 생년월일을 입력받고 본인인증을 받으세요.

입력받은 구매자의 카드 정보로 [빌링키](/guides/v2/billing#빌링키란)를 발급해보겠습니다. 빌링키는 카드번호, 유효기간, CVC 등 결제 정보를 암호화한 값이에요. 구매자의 카드 정보 대신 빌링키를 사용해서 구독 결제 시점에 결제를 내는 원리입니다.

시크릿 키와 `:`을 base64로 인코딩해서 [Basic 인증](/resources/glossary/basic-auth) 헤더를 아래와 같이 만들어주세요. **`:`을 빠트리지 않도록 주의하세요.** 비밀번호가 없다는 것을 알리기 위해 시크릿 키 뒤에 콜론을 추가합니다.
시크릿 키는 클라이언트, GitHub 등 외부에 노출되면 안 됩니다.

```plain theme="grey" copyable="false"
Basic base64("{API_SECRET_KEY}:")
```



title: 시크릿 키 인코딩 방법


시크릿 키 뒤에 `:`을 추가하고 base64로 인코딩합니다. **`:`을 빠트리지 않도록 주의하세요.**

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



title: UNAUTHORIZED\_KEY


**오류원인**

API 키를 잘못 입력하면 `UNAUTHORIZED_KEY` 에러가 발생합니다.

**해결 방법**

*   클라이언트 키와 매칭된 시크릿 키를 사용하고 있는지 확인하세요. API 키는 토스페이먼츠에 로그인한 뒤에 개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 확인할 수 있어요.

*   [시크릿 키 인코딩](/reference/using-api/authorization#시크릿-키로-인증하기)을 다시 확인하세요. 시크릿 키 뒤에 `:`을 추가하고 base64로 인코딩해서 사용해야 됩니다.



title: NOT\_SUPPORTED\_METHOD


자동결제 계약이 안 되어 있는 클라이언트 키로 연동하면 발생합니다. 자동결제 계약이 되어있는 클라이언트 키를 사용하거나 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

인코딩된 값을 [Basic 인증 헤더](/reference/using-api/authorization)에 넣고 요청 본문도 추가하세요.

구매자의 카드 정보를 빌링키 발급 API의 요청 본문에 포함하세요. 카드 번호와 카드 유효기간은 필수 파라미터입니다. 토스페이먼츠와 계약할 때 비밀번호, 카드 소유자의 생년월일 정보도 필수 파라미터로 추가할 수도 있습니다.
또 다른 필수 파라미터는 [`customerKey`](/reference#v1billingauthorizationscardpost-customerkey)인데요. [`customerKey`](/reference#v1billingauthorizationscardpost-customerkey)는 내 상점에서 구매자를 특정하는 값이에요. 각 구매자에게 고유한 무작위 값을 발급해주세요.

#### customerKey로 카드 빌링키 발급

POST

/v1/billing/authorizations/card

#### 파라미터



name: customerKey
required: true
type: string


구매자 ID입니다. 빌링키와 연결됩니다. 다른 사용자가 이 값을 알게 되면 악의적으로 사용될 수 있습니다. 자동 증가하는 숫자 또는 이메일・전화번호・사용자 아이디와 같이 유추가 가능한 값은 안전하지 않습니다. [UUID](/resources/glossary/uuid)와 같이 충분히 무작위적인 고유 값으로 생성해주세요. 영문 대소문자, 숫자, 특수문자 `-`, `_`, `=`, `.`, `@ `를 최소 1개 이상 포함한 최소 2자 이상 최대 300자 이하의 문자열이어야 합니다.



name: cardNumber
required: true
type: string


카드 번호입니다. 최대 길이는 20자입니다.

\* 테스트 환경에서는 카드 번호의 앞 여섯 자리(BIN 번호)만 유효해도 자동결제가 등록됩니다. 라이브 환경에서는 전체 카드 번호가 유효해야 등록됩니다.



name: cardExpirationYear
required: true
type: string


카드 유효 연도입니다.



name: cardExpirationMonth
required: true
type: string


카드 유효 월입니다.



name: customerIdentityNumber
required: true
type: string


카드 소유자 정보입니다. 생년월일 6자리(`YYMMDD`) 혹은 사업자등록번호 10자리가 들어갑니다.



name: cardPassword
type: string


카드 비밀번호 앞 두 자리입니다.



name: customerName
type: string


구매자명입니다. 최대 길이는 100자입니다.



name: customerEmail
type: string


구매자의 이메일 주소입니다. 결제 상태가 바뀌면 이메일 주소로 [결제내역](/guides/learn/payment-results#이메일)이 전송됩니다. 최대 길이는 100자입니다.



name: vbv
type: object


해외 카드 결제의 3DS 인증에 사용합니다. **3DS 인증 결과를 전송해야 되면 필수입니다.**



name: cavv
type: string


3D Secure 인증 세션의 인증 값입니다.



name: xid
type: string


트랜잭션 ID입니다.



name: eci
type: string


3DS 인증 결과의 코드 값입니다.

## 2. 빌링키 저장하기

API 호출 결과로 HTTP `200 OK`를 받으면 빌링키 발급 성공입니다.
빌링키를 구매자를 특정하는 [`customerKey`](/reference#v1billingauthorizationscardpost-customerkey)와 매핑해서 서버에 저장하세요. 한 번 발급된 빌링키는 다시 조회할 수 없습니다. 앞으로 해당 구매자의 [`billingKey`](/reference#v1billingbillingkeypost-billingkey), [`customerKey`](/reference#v1billingauthorizationscardpost-customerkey)가 있으면 언제든 결제를 낼 수 있어요. 빌링키가 노출되어도 빌링키와 매핑된 [`customerKey`](/reference#v1billingauthorizationscardpost-customerkey)를 모른다면 결제가 불가능합니다.

빌링키의 유효기간은 빌링키와 연결된 카드 유효기간과 같습니다. **발급된 빌링키를 삭제하는 기능은 제공하지 않습니다.** 발급된 빌링키가 더 이상 필요하지 않으면 데이터베이스에서 삭제하고 사용하지 않으면 됩니다.

```json {6} title="응답"
{
  "mId": "tosspayments",
  "customerKey": "<UniqueId name='customerKey.cardBillingWindow' />",
  "authenticatedAt": "2021-01-01T10:00:00+09:00",
  "method": "카드",
  "billingKey": "Z_t5vOvQxrj4499PeiJcjen28-V2RyqgYTwN44Rdzk0=",
  "card": {
    "issuerCode": "61",
    "acquirerCode": "31",
    "number": "43301234****123*",
    "cardType": "신용",
    "ownerType": "개인"
  },
  "cardCompany": "현대",
  "cardNumber": "43301234****123*"
}
```



title: 구매자가 등록한 카드가 결제할 수 있는 카드인지 유효성을 검사할 수 있는 방법은 없나요?


별도로 제공하지 않습니다. 자동결제에 등록할 카드의 유효성 여부는 빌링키 발급을 요청할 때 카드사를 통해 확인합니다. 만약 유효하지 않다면 [에러](/reference/error-codes#카드-자동결제-빌링키-발급-요청)를 응답합니다. 카드 잔고 부족이나 한도 초과는 [결제 승인을 요청](/reference#카드-자동결제-승인)할 때 카드사를 통해 확인합니다.



title: 구매자가 카드를 재발급 받거나 카드 유효기간이 만료되면 어떻게 해야 하나요?


새로운 카드 정보로 빌링키를 다시 발급하세요. 별도로 빌링키를 갱신하는 과정은 없습니다.

## 3. 빌링키로 자동결제 승인하기

이제 발급받은 빌링키로 원하는 결제 주기에 [카드 자동결제 승인 API](/reference#카드-자동결제-승인)를 호출하세요. **토스페이먼츠에서는 자체적으로 스케줄링 기능을 제공하지 않아요.** 따라서 직접 스케줄링 기능을 구현해서 원하는 주기, 시점에 자동결제 승인 API를 호출해야 합니다. 스케줄링 예시는 [구독 결제 서비스 구현하기 (2) 스케줄링](/blog/subscription-service-2) 아티클에서 확인하세요.

발급한 [`billingKey`](/reference#v1billingbillingkeypost-billingkey)를 [카드 자동결제 승인 API](/reference#카드-자동결제-승인)의 Path 파라미터로 추가해주세요. 요청 본문에는 주문 정보와 함께 [`customerKey`](/reference#v1billingauthorizationsissuepost-customerkey)를 넣어주세요.



title: NOT\_MATCHES\_CUSTOMER\_KEY


[`customerkey`](/reference#billingconfirmdto-customerkey)와 매핑되지 않은 [`billingKey`](/reference#billingconfirmdto-billingkey)를 사용하면 발생합니다.



title: 구매자가 구독을 취소하면 어떻게 해야 하나요?


다음 결제일에 구독을 취소한 구매자의 빌링키, `customerKey`로 [카드 자동결제 승인 API](/reference#카드-자동결제-승인)를 호출하지 않으면 됩니다.



title: 구독 결제 금액이 변경되면 어떻게 해야 하나요?


[카드 자동결제 승인 API](/reference#카드-자동결제-승인)를 호출할 때 `amount` 파라미터를 변경된 결제 금액으로 설정하면 됩니다.



title: 구독 결제 주기가 변경되면 어떻게 해야 하나요?


[카드 자동결제 승인 API](/reference#카드-자동결제-승인)를 호출하는 주기를 변경해주세요.

## 4. 결제 완료 후 응답 확인하기

API 호출 결과로 HTTP `200 OK`를 받으면 결제 승인 성공입니다. 상태 코드와 함께 [Payment 객체](/reference#payment-객체)가 응답으로 돌아옵니다. 자동결제는 [`card`](/reference#paymentdetaildto-card) 필드가 포함되어 있어야 합니다.

응답으로 받은 Payment 객체가 아래 예시와 다르다면 API 버전을 확인하세요. 개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 설정된 API 버전을 확인하고 변경할 수 있어요. API 버전 업데이트 사항은 [릴리즈 노트](/resources/release-note)에서 확인할 수 있습니다.

```json {13-26,54} title="응답"
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='paymentKey.billing' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='lastTransactionKey.billing' />",
  "orderId": "<UniqueId name='orderId.billing' />",
  "orderName": "토스 프라임 구독",
  "requestedAt": "2022-06-08T15:40:09+09:00",
  "approvedAt": "2022-06-08T15:40:49+09:00",
  "useEscrow": false,
  "cultureExpense": false,
  "card": {
    "issuerCode": "61",
    "acquirerCode": "31",
    "number": "43301234****123*",
    "installmentPlanMonths": 0,
    "isInterestFree": false,
    "interestPayer": null,
    "approveNo": "00000000",
    "useCardPoint": false,
    "cardType": "신용",
    "ownerType": "개인",
    "acquireStatus": "READY",
    "amount": 4900
  },
  "virtualAccount": null,
  "transfer": null,
  "mobilePhone": null,
  "giftCertificate": null,
  "cashReceipt": null,
  "cashReceipts": null,
  "discount": null,
  "cancels": null,
  "secret": null,
  "type": "BILLING",
  "easyPay": null,
  "country": "KR",
  "failure": null,
  "isPartialCancelable": true,
  "receipt": {
    "url": "https://dashboard.tosspayments.com/sales-slip?transactionId=KAgfjGxIqVVXDxOiSW1wUnRWBS1dszn3DKcuhpm7mQlKP0iOdgPCKmwEdYglIHX&ref=PX"
  },
  "checkout": {
    "url": "https://api.tosspayments.com/v1/payments/<UniqueId name='paymentKey.billing' />/checkout"
  },
  "currency": "KRW",
  "totalAmount": 4900,
  "balanceAmount": 4900,
  "suppliedAmount": 4455,
  "vat": 455,
  "taxFreeAmount": 0,
  "metadata": null,
  "taxExemptionAmount": 0,
  "method": "카드"
}
```
