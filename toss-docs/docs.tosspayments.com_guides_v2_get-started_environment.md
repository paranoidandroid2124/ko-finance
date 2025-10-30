***

title: 환경 설정하기
description: 테스트 환경 주의점, 방화벽 설정, 지원 플랫폼 및 브라우저를 알아보세요.
keyword: API 키, api key, client key, secret key, 키 발급, 테스트 카드, 테스트 환경, 방화벽, 지원 브라우저, Chrome, Edge, Firefox, Safari, Whale, 삼성 인터넷
---------------------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 환경 설정하기

{description}

## 테스트 환경

토스페이먼츠는 개발자의 연동 편의를 위해 라이브 환경과 비슷한 테스트 환경을 제공하고 있어요.

하지만 테스트 환경에서는 카드 번호와 같은 실제 결제 정보를 입력해도, 결제는 가상으로 승인돼요. 따라서 테스트 환경에서는 **결제가 승인되어도 실제 결제수단에서 돈이 출금되지 않아요.**

테스트 환경과 라이브 환경이 다른 점은 아래 표에서 자세히 확인하세요.

카드

*   유효한 카드 번호로 테스트해도 실제로 결제가 되지 않습니다.

간편결제

*   토스페이, 네이버페이, 애플페이, 삼성페이, SSG페이, 엘페이, 핀페이는 개발 연동 체험 상점 및 MID 테스트 키로 연동할 수 있습니다.
*   카카오페이는 계약 이후에 MID로 발급받는 상점용 테스트 키로만 연동할 수 있습니다.
*   애플페이는 iPhone 및 Mac Safari 에서만 노출돼요.
*   페이코는 테스트 키로 연동할 수 없어요. 라이브 키로 테스트하세요.

가상계좌

*   테스트 환경에서는 가상계좌번호 앞에 'X'가 붙습니다.
*   테스트 환경에서 발급된 계좌로 직접 입금할 수 없지만 [테스트 결제내역 메뉴](https://developers.tosspayments.com/my/payment-logs)에서
    입금처리를 할 수 있습니다.
*   개발 연동 체험 상점의 테스트 키로 연동하면 가상계좌 입금 안내 문자가 발송되지 않습니다. 토스페이먼츠 전자결제 계약 이후에 확인할 수 있는 테스트 키로는 가상계좌 안내 문자가 발송됩니다.

영수증

*   [Payment 객체](/reference#payment-객체)에 영수증 URL은 생성되지만 실제 데이터는 제공되지 않습니다.
*   영수증 샘플은 [결제 결과 안내](/guides/v2/learn/payment-results) 가이드에서 확인하세요.

자동결제(빌링)

*   카드 번호의 앞 여섯 자리([BIN 번호](/resources/glossary/bin))만 유효해도 자동 결제가 등록됩니다. 라이브 환경에서는 전체 카드 번호가 유효해야 등록됩니다.
*   휴대폰 본인 인증번호로 `000000`을 입력하세요. 휴대폰 인증은 라이브 환경에서만 사용할 수 있습니다.

계좌이체

*   계좌번호, 비밀번호, 계좌 소유주 이름, 보안카드와 OTP 정보를 가상의 값으로 넣어 테스트할 수 있습니다. 다만 사용자의 공동 인증서는 실제로 인증이 되어야 합니다.

게임 문화 상품권

*   가상의 게임 문화 상품권 PIN 번호를 입력할 수 있습니다. 사용 가능한 금액은 항상 10,000원으로 표시됩니다.

정산

*   [정산 조회 API](/reference#정산-조회)의 응답으로 돌아오는 정산 기록은 라이브 환경에서만 조회할 수 있습니다.
*   테스트 환경에서는 정산 기록이 없는 것으로 조회됩니다.

지급대행

*   테스트 환경에서 [잔액조회 API](/reference#잔액-조회)를 호출하면 응답으로 `availableAmount`만 돌아옵니다.
*   테스트 환경에서는 유효한 사업자번호로 법인사업자(`CORPORATE`) [셀러만 등록](/reference#셀러-등록)할 수 있어요. 셀러의 상태가 `KYC_REQUIRED`로 바뀔 수는 있지만 테스트 KYC 수행이 불가능하기 때문에 `APPROVED` 상태로 바뀔 수는 없습니다.
*   [지급대행 요청 API](/reference#지급대행-요청)를 라이브 환경에서 테스트하면 수수료가 부과됩니다.

API 요청 제한

*   테스트 환경에서 각 API는 분당 100 건의 요청 제한이 있습니다.

### 테스트 환경에서 에러 재현하기

에러 대응을 위해 테스트 환경에서 API 에러를 재현하고 싶을 수도 있는데요. 아래 `TossPayments-Test-Code` API 헤더를 사용하면 토스페이먼츠에서 일어나는 모든 에러를 테스트 환경에서도 라이브 환경과 똑같이 재현할 수 있어요.

```plain theme="grey" copyable="false" feedbackable="false"
TossPayments-Test-Code: {TEST_CODE}
```

아래 예시는 결제 승인 API에서 잔액 부족 또는 한도초과 에러 `REJECT_CARD_PAYMENT`를 제현하고 있어요. 예시로 사용 방법을 자세히 알아볼게요.

*   [`Authorization` 인증 헤더](/reference/using-api/authorization)에 반드시 테스트 시크릿 키를 사용해주세요. 라이브 키를 사용하면 테스트 코드 헤더가 무시돼요.
*   `TossPayments-Test-Code` 헤더에 재현하고 싶은 [에러 코드](/reference/error-codes)를 넣고 API를 호출하세요.

```bash title="요청"
curl --request POST \
  --url https://api.tosspayments.com/v1/payments/confirm \
  --header 'Authorization: Basic dGVzdF9nc2tfZG9jc19PYVB6OEw1S2RtUVhrelJ6M3k0N0JNdzY6' \
  --header 'Content-Type: application/json' \
  --header 'TossPayments-Test-Code: REJECT_CARD_PAYMENT' \
  --data '{"paymentKey":"5zJ4xY7m0kODnyRpQWGrN2xqGlNvLrKwv1M9ENjbeoPaZdL6","orderId":"a4CWyWY5m89PNh7xJwhk1","amount":15000}'
```

그럼 아래와 같이 테스트한 에러 코드의 [에러 객체](/reference/using-api/req-res#에러-객체)가 응답으로 돌아옵니다.

```json title="응답"
{
  "code": "REJECT_CARD_PAYMENT",
  "message": "한도초과 혹은 잔액부족으로 결제에 실패했습니다."
}
```

### 테스트 결제내역 확인하기

테스트 환경에서 일어난 결제 내역은 개발자센터에서 자세히 확인할 수 있어요. 라이브 환경의 결제내역은 상점관리자에서 확인해주세요.

1.  개발자센터에 로그인하고 내 [테스트 결제내역](https://developers.tosspayments.com/my/payment-logs) 메뉴로 이동하세요.

2.  날짜 별, 결제수단 별로 결제내역을 조회할 수 있어요.

3.  [가상계좌 결제](/resources/glossary/virtual-account)는 가장 오른쪽 칼럼에서 결제를 취소하거나 가상계좌 입금을 처리할 수 있어요.
    *   **'취소'** 를 선택하면 결제 취소 API를 호출하지 않고 테스트 결제를 취소할 수 있어요.
    *   **'입금처리'** 를 선택하면 가상계좌에 입금되는 액션을 테스트할 수 있어요.

![토스페이먼츠 테스트 결제내역](https://static.tosspayments.com/docs/guides/env-setting.png)

## 방화벽 설정하기

토스페이먼츠는 구매자의 결제 정보와 개인 정보를 보호하기 위해 [**HTTPS 통신과 TLS 버전 1.2 이상만 지원해요**](/reference/using-api/security). 서버에서 아래 토스페이먼츠 [IP 주소](/resources/glossary/ip)를 허용해주세요. 더 자세한 내용은 [방화벽 가이드](/reference/using-api/security)에서 확인하세요.

| IP 주소          | 방향    |
| ---------------- | ------- |
| 13.124.18.147    | INBOUND |
| 13.124.108.35    | INBOUND |
| 3.36.173.151     | INBOUND |
| 3.38.81.32       | INBOUND |
| 115.92.221.121\* | INBOUND |
| 115.92.221.122\* | INBOUND |
| 115.92.221.123\* | INBOUND |
| 115.92.221.125\* | INBOUND |
| 115.92.221.126\* | INBOUND |
| 115.92.221.127\* | INBOUND |

\* 2024년 12월에 추가된 신규 IP입니다.

## 지원 플랫폼·브라우저 환경

토스페이먼츠 SDK가 지원하는 플랫폼·브라우저 환경이에요. 토스페이먼츠 결제 서비스를 원활하게 이용하려면 **최신 버전의 브라우저를 사용하는 것을 권장해요**. 최신 브라우저는 더 안전하고 안정적이기 때문에 결제 오류를 최소화할 수 있습니다.

| 플랫폼 환경       | 브라우저 환경                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------- |
| 데스크톱 브라우저 | - Chrome 72 이상- Edge 79 이상- Firefox 64 이상- Safari 13 이상- Whale 1.6.81.8 이상 |
| 모바일 웹         | Chrome, Safari, 삼성 인터넷                                                                              |
| 모바일 앱         | Android, iOS                                                                                             |
