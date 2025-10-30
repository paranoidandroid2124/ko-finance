***

title: 자동결제(빌링) 결제창 연동하기
description: 자동결제는 다른 이름으로 빌링, 또는 정기결제로 불리는 결제 방식입니다. 카드 등록창에서 구매자의 카드를 한 번만 등록하고 나면, 별도의 구매자 인증 없이 간편하게 결제를 요청할 수 있습니다.
keyword: 정기 결제, 빌링, billing, 구독, billingKey, 빌링키, 구독 결제, 빌링키 발급, schedule, scheduling, cron, cron job, 스케줄링, 스케줄러, 빌링키 관리, 추가 계약, 카드 등록, 결제 주기 변경, 원하는 시점, 특정 시점
----------------------------------------------------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 자동결제(빌링) 결제창 연동하기

{description}

자동결제는 정기 구독형 서비스에만 사용할 수 있어요. 비정기 결제 서비스에는 정책적으로 사용이 제한되니 유의하세요.

\* 자동결제는 추가 리스크 검토 및 계약 후 사용할 수 있습니다. 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

![카드 자동결제 흐름도](https://static.tosspayments.com/docs/billing/billing-flow.png)

## API 키 준비하기

개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 **API 개별 연동 키**를 확인하세요.

토스페이먼츠와 전자결제 계약 전이어도 회원가입하면 나만의 테스트 상점 키를 확인하고 테스트 결제내역, 웹훅 등 기능을 사용할 수 있어요. 로그인한 상태라면 코드의 키값이 테스트 상점 키입니다. 로그인하지 않아도 문서 테스트 키로 테스트 연동할 수 있어요.

토스페이먼츠와 전자결제 계약을 완료했다면 개발자센터의 [API 키 메뉴](https://developers.tosspayments.com/my/api-keys)에서 자동결제(빌링)로 계약된 상점아이디(MID)를 선택한 다음에 클라이언트 키와 시크릿 키를 확인하세요. [테스트 키와 라이브 키의 차이점](/reference/using-api/api-keys#api-키-이해하기)도 확인하고 연동을 시작하세요.

\* 자동결제는 추가 리스크 검토 및 계약 후 사용할 수 있습니다. 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

```js title="API 개별 연동 키"
// API 개별 테스트 연동 키
// 토스페이먼츠에 회원가입하기 전이라면 아래 키는 문서 테스트 키입니다.
// 토스페이먼츠에 회원가입하고 로그인한 상태라면 아래 키는 내 테스트 키입니다.
const clientKey = "<ClientKey />";
const secretKey = "<SecretKey />";
```

***

## 1. 구매자 카드 등록하기

먼저 주문서 페이지에 자동결제(빌링) 결제창을 연동할게요. 아래 코드는 주문서 페이지의 예시에요.

클라이언트 쪽에 토스페이먼츠 SDK를 설치하고, 클라이언트 키로 SDK를 초기화하세요. 다음, [`payment()`](/sdk/v2/js#tosspaymentspayment) 메서드로 결제창 인스턴스를 생성하세요. 아래 코드에서는 `payment`라는 인스턴스를 생성했어요.

그럼 이제 결제창을 띄울 준비가 됐어요. 결제창 인스턴스로 [`requestBillingAuth()`](/sdk/v2/js#paymentrequestbillingauth) 메서드를 호출하면 결제 요청이 시작되고, 결제창이 열려요. 메서드의 파라미터로 주문번호, 결제금액, `successUrl`, `failUrl` 등 필요한 정보를 설정하세요. 그리고 주문서의 **'카드 등록하기'** 버튼에 자동결제 요청 메서드를 이벤트로 등록해주세요.

```html stack="frontend"
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <!-- SDK 추가 -->
    <script src="https://js.tosspayments.com/v2/standard"></script>
  </head>
  <body>
    <!-- 카드 등록하기 버튼 -->
    <button class="button" style="margin-top: 30px" onclick="requestBillingAuth()">카드 등록하기</button>
    <script>
      // ------  SDK 초기화 ------
      // @docs https://docs.tosspayments.com/sdk/v2/js#토스페이먼츠-초기화
      const clientKey = "<ClientKey />";
      const customerKey = "<UniqueId name='customerKey.cardBillingWindow' />";
      const tossPayments = TossPayments(clientKey);
      // 회원 결제
      // @docs https://docs.tosspayments.com/sdk/v2/js#tosspaymentspayment
      const payment = tossPayments.payment({ customerKey });
      // 비회원 결제
      // const payment = tossPayments.payment({customerKey: TossPayments.ANONYMOUS})
      // ------ '카드 등록하기' 버튼 누르면 결제창 띄우기 ------
      // @docs https://docs.tosspayments.com/sdk/v2/js#paymentrequestpayment
      async function requestBillingAuth() {
        await payment.requestBillingAuth({
          method: "CARD", // 자동결제(빌링)는 카드만 지원합니다
          successUrl: window.location.origin + "/success", // 요청이 성공하면 리다이렉트되는 URL
          failUrl: window.location.origin + "/fail", // 요청이 실패하면 리다이렉트되는 URL
          customerEmail: "customer123@gmail.com",
          customerName: "김토스",
        });
      }
    </script>
  </body>
</html>
```

```jsx stack="frontend"
import { loadTossPayments, ANONYMOUS } from "@tosspayments/tosspayments-sdk";
import { useEffect, useState } from "react";
// ------  SDK 초기화 ------
// @docs https://docs.tosspayments.com/sdk/v2/js#토스페이먼츠-초기화
const clientKey = "<ClientKey />";
const customerKey = "<UniqueId name='customerKey.cardBillingWindow' />";
export function PaymentCheckoutPage() {
  const [payment, setPayment] = useState(null);
  useEffect(() => {
    async function fetchPayment() {
      try {
        const tossPayments = await loadTossPayments(clientKey);
        // 회원 결제
        // @docs https://docs.tosspayments.com/sdk/v2/js#tosspaymentspayment
        const payment = tossPayments.payment({
          customerKey,
        });
        // 비회원 결제
        // const payment = tossPayments.payment({ customerKey: ANONYMOUS });
        setPayment(payment);
      } catch (error) {
        console.error("Error fetching payment:", error);
      }
    }
    fetchPayment();
  }, [clientKey, customerKey]);
  // ------ '카드 등록하기' 버튼 누르면 결제창 띄우기 ------
  // @docs https://docs.tosspayments.com/sdk/v2/js#paymentrequestpayment
  async function requestBillingAuth() {
    // 결제를 요청하기 전에 orderId, amount를 서버에 저장하세요.
    // 결제 과정에서 악의적으로 결제 금액이 바뀌는 것을 확인하는 용도입니다.
    await payment.requestBillingAuth({
      method: "CARD", // 자동결제(빌링)는 카드만 지원합니다
      successUrl: window.location.origin + "/success", // 요청이 성공하면 리다이렉트되는 URL
      failUrl: window.location.origin + "/fail", // 요청이 실패하면 리다이렉트되는 URL
      customerEmail: "customer123@gmail.com",
      customerName: "김토스",
    });
  }
  return (
    // 카드 등록하기 버튼
    <button className="button" onClick={() => requestBillingAuth()}>
      카드 등록하기
    </button>
  );
}

```

**'카드 등록하기'** 버튼을 누르면 아래와 같은 결제창이 열려요. 테스트하고 싶은 카드 정보를 입력해주세요. 테스트 클라이언트 키를 사용했다면 실제로 결제되지 않으니 안심하세요.

![카드 자동결제 결제수단 등록창 예시 이미지](https://static.tosspayments.com/docs/window/card-billing.png)

*   테스트 환경에서는 본인인증 문자가 발송되지 않습니다. 본인인증창이 뜨면 인증번호로 `000000`을 입력하세요.

*   테스트 환경에서는 카드 번호의 앞 여섯 자리(BIN 번호)만 유효해도 자동결제가 등록됩니다. 라이브 환경에서는 전체 카드 번호가 유효해야 등록됩니다.

*   현재 자동결제 결제수단은 국내에서 발급한 카드만 지원합니다. 해외카드, 해외결제는 지원하지 않습니다.

## 2. 리다이렉트 URL로 이동하기

결제창에서 구매자의 결제수단을 [인증](/resources/glossary/card-payment#1-인증)하는데요. 인증 결과는 리다이렉트 URL로 확인할 수 있어요.
결제 인증이 성공했다면 성공 리다이렉트 URL(`successUrl`)의 쿼리 파라미터로 결제 정보를 확인하고 검증해주세요. 인증이 실패했다면 이동한 실패 리다이렉트 URL(`failUrl`)의 쿼리 파라미터로 에러를 확인해주세요.

### 결제 인증이 성공했어요

카드 정보가 인증됐다면, `successUrl`로 이동해요. 해당 URL에 아래 두 가지 쿼리 파라미터가 추가돼요. 다음 단계에 필요한 값이니 서버나 임시 저장소에 보관해주세요. `customerKey`는 이전 단계에서 만든 구매자 ID입니다. `authKey`는 빌링키를 발급할 때 필요한 일회성 인증 키입니다. 최대 길이는 300자입니다.

```plain theme="grey" copyable="false"
/success?customerKey={CUSTOMER_KEY}&authKey={AUTH_KEY}
```

### 결제 인증이 실패했어요

만약에 결제 정보가 틀려서 결제 인증이 실패했다면, `failUrl`로 이동해요. 해당 URL에는 아래 쿼리 파라미터가 추가돼요. 에러 코드와 메시지를 확인해서 구매자에게 적절한 안내 메시지를 보여주세요.

```plain theme="grey" copyable="false"
/fail?code={ERROR_CODE}&message={ERROR_MESSAGE}
```



title: PAY\_PROCESS\_CANCELED


**오류원인**

구매자에 의해 결제가 취소되면 `PAY_PROCESS_CANCELED` 에러가 발생합니다. 결제 과정이 중단된 것이라서 `failUrl`로 `orderId`가 전달되지 않아요.



title: PAY\_PROCESS\_ABORTED


**오류원인**

결제가 실패하면 `PAY_PROCESS_ABORTED` 에러가 발생합니다.

**해결 방법**

*   오류 메시지를 확인하세요. 계약 관련 오류는 토스페이먼츠 고객센터(1544-7772, support@tosspayments.com)로 문의해주세요.

*   기타 오류는 토스페이먼츠 [실시간 기술지원 채널](https://discord.com/invite/A4fRFXQhRu)에서 문의해주세요.



title: REJECT\_CARD\_COMPANY


**오류원인**

구매자가 입력한 카드 정보에 문제가 있다면 `REJECT_CARD_COMPANY` 에러가 발생합니다.

**해결 방법**

*   오류 메시지를 확인하고 구매자에게 안내를 해주세요.

## 3. 빌링키 발급하기

이제 [빌링키](/guides/v2/billing#빌링키란)를 발급할 차례예요. 빌링키는 카드번호, 유효기간, CVC 등 결제 정보를 암호화한 값이에요. 구매자의 카드 정보 대신 빌링키를 사용해서 구독 결제 시점에 결제를 내는 원리입니다.

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

인코딩된 값을 [Basic 인증 헤더](/reference/using-api/authorization)에 넣고 요청 본문도 추가하세요. 앞 단계에서 리다이렉트 URL로 받은 [`authKey`](/reference#v1billingauthorizationsissuepost-authkey), [`customerKey`](/reference#v1billingauthorizationsissuepost-customerkey) 값을 [카드 자동결제 빌링키 발급 요청 API](/reference#authkey로-카드-자동결제-빌링키-발급-요청)의 요청 본문으로 보냅니다.

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

## 4. 빌링키로 자동결제 승인하기

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

## 5. 결제 완료 후 응답 확인하기

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
