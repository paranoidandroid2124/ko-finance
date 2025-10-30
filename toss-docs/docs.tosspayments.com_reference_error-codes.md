***

title: API 에러 코드
description: 토스페이먼츠 API 사용할 때 발생할 수 있는 에러를 살펴보세요.
keyword: 에러, API, 결제창, 오류, error, failure, 에러 객체
------------------------------------------------

# API 에러 코드

토스페이먼츠 API를 사용할 때 발생할 수 있는 에러를 살펴보세요.



title: 에러 확인하기


요청이 정상적으로 처리되지 않으면 응답으로 HTTP 상태 코드와 함께 아래와 같은 에러 객체가 돌아옵니다.

```json
{
  "code": "NOT_FOUND_PAYMENT",
  "message": "존재하지 않는 결제 입니다."
}
```

*   `code`: 에러 타입을 보여주는 에러 코드입니다.
*   `message`: 에러 메시지입니다. 에러 발생 이유를 알려줍니다.

이미 일어난 결제 기록을 조회했을 때는 Payment 객체의 `failure`필드에 에러 객체가 들어있습니다.

```json {10,18-21}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "lastTransactionKey": "B7103F204998813B889C77C043D09502",
  "paymentKey": "5EnNZRJGvaBX7zk2yd8ydw26XvwXkLrx9POLqKQjmAw4b0e1",
  "orderId": "a4CWyWY5m89PNh7xJwhk1",
  "orderName": "토스 티셔츠 외 2건",
  "currency": "KRW",
  "method": "카드",
  "status": "ABORTED",
  // ...
  "discount": null,
  "cancels": null,
  "secret": null,
  "type": "NORMAL",
  "easyPay": null,
  "country": "KR",
  "failure": {
    "code": "COMMON_ERROR",
    "message": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
  },
  "totalAmount": 15000,
  "balanceAmount": 15000,
  "suppliedAmount": 13636,
  "vat": 1364,
  "taxFreeAmount": 0,
  "taxExemptionAmount": 0
}
```

## 코어 API 별 에러

### 결제 승인

### 결제 조회

### 결제 취소

### 카드 번호 결제

### 가상계좌 발급 요청

### 카드 자동결제 빌링키 발급 요청

### 카드 자동결제 승인

### 거래 조회

### 정산 조회

*   에러 코드로 `INVALID_REQUEST`가 돌아왔다면 `dateType`이 제대로 들어갔는지 확인해보세요.

### 수동 정산

### 현금영수증 발급 요청

### 현금영수증 발급 취소 요청

### 현금영수증 조회

### 현금영수증 국세청 에러

| 에러 코드   | 한글 에러 메시지                                                                                | 영문 에러 메시지                                                                                                                                                |
| ----------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NTS_ERROR` | \[TS1] 신분확인정보 자릿수 오류                                                                  | \[TS1] Incorrect customer identity number length                                                                                                                 |
| `NTS_ERROR` | \[TS2] 카드정보 자릿수 오류                                                                      | \[TS2] Incorrect card number length                                                                                                                              |
| `NTS_ERROR` | \[TS3] 제외업종사업자와 거래한 현금결제내역                                                      | \[TS3] Cash transaction with a business not eligible for tax reduction                                                                                           |
| `NTS_ERROR` | \[TS4] 매출금액 입력오류 또는 거래금액 총합계 입력오류.                                          | \[TS4] Amount error                                                                                                                                              |
| `NTS_ERROR` | \[TS5] 승인번호, 거래일자 중복 오류                                                              | \[TS5] Duplicated approval key and transaction date                                                                                                              |
| `NTS_ERROR` | \[TS6] 거래일자 오류                                                                             | \[TS6] Transaction date error                                                                                                                                    |
| `NTS_ERROR` | \[TS7] 가맹점 사업자등록번호 미등록 오류 또는 현금영수증사업자의 승인코드가 불일치한 경우        | \[TS7] The business number does not exist or does not match the business number on the cash receipt.                                                             |
| `NTS_ERROR` | \[TS8] Layout 오류(Record 항목별 입력 값 오류)                                                   | \[TS8] Layout error: Incorrect values for record fields                                                                                                          |
| `NTS_ERROR` | \[TSC] 취소거래인 경우 원 승인거래 승인번호, 거래일자가 국세청에 미존재                          | \[TSC] The cancel transaction’s approval key and transaction date are not registered in the National Tax Service.                                                |
| `NTS_ERROR` | \[TSD] 승인거래이면서 당초승인번호, 당초거래일자, 취소사유 입력                                  | \[TSD] The cancel reason, original approval key, and original transaction date fields are given in an approval transaction.                                      |
| `NTS_ERROR` | \[TSE] 취소거래와 승인거래의 가맹점 사업자등록번호 불일치                                        | \[TSE] The business number of the cancel and approval transactions do not match.                                                                                 |
| `NTS_ERROR` | \[TSF] 취소거래와 승인거래의 거래자구분 불일치                                                   | \[TSF] The customer type of the cancel and approval transactions do not match.                                                                                   |
| `NTS_ERROR` | \[TSG] 취소거래와 승인거래의 거래금액 총합계 불일치                                              | \[TSG] The amounts of the cancel and approval transactions do not add up to the total amount.                                                                    |
| `NTS_ERROR` | \[TSH] 취소거래와 승인거래의 신분확인 불일치                                                     | \[TSH] The customer identity of the cancel and approval transactions do not match.                                                                               |
| `NTS_ERROR` | \[TSN] 대중교통 및 도서·공연비 여부가 ‘C’이나, 해당 가맹점이 도서·공연비 사업자 명단에 없는 경우 | \[TSN] The public transportation, book, performance ticket field value is ‘C’, but the business is not eligible for books and performance ticket tax deductions. |
| `NTS_ERROR` | \[TSO] 대중교통 및 도서·공연비 여부가 ‘Y’이나, 해당 가맹점이 도서·공연비 사업자 명단에 있는 경우 | \[TSO] The public transportation, book, performance ticket field value is ‘Y’, but the business is eligible for books and performance ticket tax deductions.     |
| `NTS_ERROR` | \[XXX] 정의 안된 오류                                                                            | \[XXX] Undefined error                                                                                                                                           |

### 셀러 등록

### 셀러 수정

### 셀러 삭제

### 셀러 단건 조회

### 셀러 목록 조회

### 지급대행 요청

### 지급대행 요청 취소

### 지급 요청 단건 조회

### 지급대행 v1 에러 목록



title: 지급대행 v1 에러 목록


**서브몰 등록**

**서브몰 조회**

**서브몰 단건 조회**

**서브몰 수정**

**서브몰 삭제**

**지급 가능한 잔액 조회**

**지급대행 요청**

**지급대행 요청 취소**

**지급대행 단건 조회**

### 전체 에러 목록

코어 API에서 발생할 수 있는 전체 에러 목록입니다.

| 상태 코드 | 에러 코드                                            | 한글 에러 메시지                                                                                                                      | 영문 에러 메시지                                                                                                                                         |
| :-------- | :--------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 400       | `ACCOUNT_OWNER_CHECK_FAILED`                         | 계좌 소유주를 가져오는데 실패했습니다. 은행코드, 계좌번호를 확인해주세요.                                                             | Failed to get account holder. Please check your bank code and account number.                                                                            |
| 400       | `ALREADY_CANCELED_PAYMENT`                           | 이미 취소된 결제 입니다.                                                                                                              | The payment has already been canceled.                                                                                                                   |
| 400       | `ALREADY_CLOSE_ACCOUNT`                              | 이미 해지된 계좌입니다.                                                                                                               | This account has already been closed.                                                                                                                    |
| 400       | `ALREADY_COMPLETED_PAYMENT`                          | 이미 완료된 결제 입니다.                                                                                                              | This is a payment that has already been completed.                                                                                                       |
| 400       | `ALREADY_EXIST_SUBMALL`                              | 이미 존재하는 서브몰입니다.                                                                                                           | This sub-mall is already exists.                                                                                                                         |
| 400       | `ALREADY_PROCESSED_PAYMENT`                          | 이미 처리된 결제 입니다.                                                                                                              | This is a payment that has already been processed.                                                                                                       |
| 400       | `ALREADY_REFUND_PAYMENT`                             | 이미 환불된 결제입니다.                                                                                                               | The payment has already been refunded.                                                                                                                   |
| 400       | `ALREADY_REFUNDING_PAYMENT`                          | 이미 환불 중인 결제입니다.                                                                                                            | The payment is already being refunded.                                                                                                                   |
| 400       | `API_VERSION_UPDATE_NEEDED`                          | 이 API를 사용하려면 \[VERSION] 이상의 버전을 사용해야 합니다. 개발자센터(https://developers.tosspayments.com)에서 버전을 변경해주세요. | To use the api need to upgrade version to \[VERSION]. You can update api version at Tosspayment Developer Center(https://developers.tosspayments.com)     |
| 400       | `BELOW_MINIMUM_AMOUNT`                               | 신용카드는 결제금액이 100원 이상, 계좌는 200원이상부터 결제가 가능합니다.                                                             | Payment can be made from 100 won or more by credit card, and 200 won or more for account.                                                                |
| 400       | `BELOW_ZERO_AMOUNT`                                  | 금액은 0보다 커야 합니다.                                                                                                             | The amount must be greater than 0.                                                                                                                       |
| 400       | `DUPLICATED_CASH_RECEIPT`                            | 이미 현금영수증이 발급된 주문입니다.                                                                                                  | This is a duplicate request that has already been issued.                                                                                                |
| 400       | `DUPLICATED_ORDER_ID`                                | 이미 승인 및 취소가 진행된 중복된 주문번호 입니다. 다른 주문번호로 진행해주세요.                                                      | This is a duplicate order id that has already been approved or canceled. Please proceed with a different order id.                                       |
| 400       | `DUPLICATED_REQUEST`                                 | 중복된 요청입니다.                                                                                                                    | This is a duplicate request.                                                                                                                             |
| 400       | `EXCEED_MAX_AMOUNT`                                  | 거래금액 한도를 초과했습니다.                                                                                                         | The transaction amount limit has been exceeded.                                                                                                          |
| 400       | `EXCEED_MAX_CARD_INSTALLMENT_PLAN`                   | 설정 가능한 최대 할부 개월 수를 초과했습니다.                                                                                         | You have exceeded the maximum number of installment months that can be set.                                                                              |
| 400       | `EXCEED_MAX_DAILY_PAYMENT_COUNT`                     | 하루 결제 가능 횟수를 초과했습니다.                                                                                                   | You have exceeded the number of daily payments.                                                                                                          |
| 400       | `EXCEED_MAX_DUE_DATE`                                | 가상 계좌의 최대 유효만료 기간을 초과했습니다.                                                                                        | You have exceeded the maximum expiry period for your virtual account.                                                                                    |
| 400       | `EXCEED_MAX_ONE_DAY_WITHDRAW_AMOUNT`                 | 1일 출금 한도를 초과했습니다.                                                                                                         | You have exceeded the one-day withdrawal limit.                                                                                                          |
| 400       | `EXCEED_MAX_ONE_TIME_WITHDRAW_AMOUNT`                | 1회 출금 한도를 초과했습니다.                                                                                                         | You have exceeded the one-time withdrawal limit.                                                                                                         |
| 400       | `EXCEED_MAX_PAYMENT_AMOUNT`                          | 하루 결제 가능 금액을 초과했습니다.                                                                                                   | You have exceeded the amount you can pay per day.                                                                                                        |
| 400       | `EXCEED_MAX_QUERY_LIMIT`                             | 최대 조회 개수를 초과했습니다.                                                                                                        | You have exceeded the maximum number of query limit.                                                                                                     |
| 400       | `EXCEED_MAX_VALID_HOURS`                             | 가상 계좌의 최대 유효시간을 초과했습니다.                                                                                             | The maximum validity time of the virtual account has been exceeded.                                                                                      |
| 400       | `EXCEED_MIN_CARD_INSTALLMENT_PLAN`                   | 설정 가능한 최소 할부 개월 수를 1개월 이상으로 설정해주세요.                                                                          | The minimum installment month must be set to at least 1 month.                                                                                           |
| 400       | `EXCEED_UNKNOWN_CASE`                                | 한도 초과 되었습니다.                                                                                                                 | A threashold exceeds                                                                                                                                     |
| 400       | `INCORRECT_FAIL_URL_FORMAT`                          | 잘못된 failUrl 입니다.                                                                                                                | Invalid format: `failUrl`                                                                                                                                |
| 400       | `INCORRECT_SUCCESS_URL_FORMAT`                       | 잘못된 successUrl 입니다.                                                                                                             | Invalid format: `successUrl`                                                                                                                             |
| 400       | `INVALID_ACCOUNT_NOT_CORRECT_BANK`                   | 입력하신 계좌는 해당 은행의 계좌가 아닙니다.                                                                                          | The account you entered is not a bank account.                                                                                                           |
| 400       | `INVALID_ACCOUNT_NUMBER`                             | 계좌번호가 올바르지 않습니다.                                                                                                         | Account number is incorrect.                                                                                                                             |
| 400       | `INVALID_ACCOUNT_NUMBER_OR_UNAVAILABLE`              | 잘못된 계좌번호이거나 서비스 불가한 계좌입니다.                                                                                       | Wrong account number or account unavailable.                                                                                                             |
| 400       | `INVALID_API_KEY`                                    | 잘못된 시크릿키 연동 정보 입니다.                                                                                                     | Incorrect secret key.                                                                                                                                    |
| 400       | `INVALID_AUTHORIZE_AUTH`                             | 잘못된 인증 방식입니다.                                                                                                               | Incorrect authentication.                                                                                                                                |
| 400       | `INVALID_AUTHORIZE_AUTH_TYPE_GIFT_CERTIFICATE`       | 유효하지 않은 상품권 결제 인증 타입입니다.                                                                                            | This is an invalid gift certificate payment authentication type.                                                                                         |
| 400       | `INVALID_BANK`                                       | 유효하지 않은 은행입니다.                                                                                                             | It is an Invalid bank.                                                                                                                                   |
| 400       | `INVALID_BILL_KEY_REQUEST`                           | 빌링키 인증이 완료되지 않았거나 유효하지 않은 빌링 거래 건입니다.                                                                     | Billing key authentication has not been completed or is an invalid billing transaction.                                                                  |
| 400       | `INVALID_BILLING_AUTH`                               | 유효하지 않은 빌링 인증입니다.                                                                                                        | Invalid billing authentication.                                                                                                                          |
| 400       | `INVALID_BIRTH_DAY_FORMAT`                           | 생년월일 정보는 6자리의 yyMMdd 형식이어야 합니다. 사업자등록번호는 10자리의 숫자여야 합니다.                                          | The birth date format must be in 6 length of yyMMdd format.                                                                                              |
| 400       | `INVALID_BUSINESS_NUMBER`                            | 사업자 등록번호가 잘못되었습니다.                                                                                                     | The business registration number is incorrect.                                                                                                           |
| 400       | `INVALID_CARD`                                       | 카드 입력정보가 올바르지 않습니다.                                                                                                    | Card input information is incorrect.                                                                                                                     |
| 400       | `INVALID_CARD_COMPANY`                               | 유효하지 않은 카드사입니다.                                                                                                           | It is an invalid card company.                                                                                                                           |
| 400       | `INVALID_CARD_EXPIRATION`                            | 카드 정보를 다시 확인해주세요.(유효기간) Please check the card expiration date information again.                                     |
| 400       | `INVALID_CARD_IDENTITY`                              | 입력하신 주민번호/사업자번호가 카드 소유주 정보와 일치하지 않습니다.                                                                  | The entered resident registration number/business number does not match the cardholder information.                                                      |
| 400       | `INVALID_CARD_INSTALLMENT_AMOUNT`                    | 할부금액 잘못 되었습니다.                                                                                                             | The installment amount is incorrect.                                                                                                                     |
| 400       | `INVALID_CARD_INSTALLMENT_PLANS_WITH_MAX_AND_SINGLE` | cardInstallmentPlan과 maxCardInstallmentPlan은 같이 사용할 수 없습니다.                                                               | cardInstallmentPlan and maxCardInstallmentPlan cannot be used together.                                                                                  |
| 400       | `INVALID_CARD_NUMBER`                                | 카드번호를 다시 확인해주세요.                                                                                                         | Please check your card number again.                                                                                                                     |
| 400       | `INVALID_CARD_PASSWORD`                              | 카드 정보를 다시 확인해주세요.(비밀번호) Please check the card information again.                                                     |
| 400       | `INVALID_CASH_RECEIPT_INFO`                          | 현금 영수증 정보가 잘못되었습니다.                                                                                                    | Cash receipt information is incorrect.                                                                                                                   |
| 400       | `INVALID_CLIENT_KEY`                                 | 잘못된 클라이언트 연동 정보 입니다.                                                                                                   | Incorrect client key.                                                                                                                                    |
| 400       | `INVALID_CURRENCY`                                   | 잘못된 통화 값입니다.                                                                                                                 | Invalid currency value.                                                                                                                                  |
| 400       | `INVALID_CUSTOMER_KEY`                               | `customerKey`는 영문 대소문자, 숫자, 특수문자 -, \*, =, ., @로 2자 이상 255자 이하여야 합니다.                                        | `customerKey` must be at least 2 and maximum 20 upper and lower case alphabets, numbers, special characters (-, \_, =, ., @).                            |
| 400       | `INVALID_DATE`                                       | 날짜 데이터가 잘못 되었습니다.                                                                                                        | The date data is invalid.                                                                                                                                |
| 400       | `INVALID_EASY_PAY`                                   | 간편결제 입력정보가 올바르지 않습니다.                                                                                                | The easy payment input information is incorrect.                                                                                                         |
| 400       | `INVALID_EMAIL`                                      | 이메일 주소 형식에 맞지 않습니다.                                                                                                     | It doesn't match the email address format.                                                                                                               |
| 400       | `INVALID_FLOW_MODE_PARAMETERS`                       | 인증 창을 먼저 띄우려면 카드사 코드 또는 은행 코드 또는 간편결제수단이 같이 전달되어야 합니다.                                        | If you want to open the payment authentication window first, the credit card company code, bank code, or easy payment method must be delivered together. |
| 400       | `INVALID_IDENTIFICATION_TYPE`                        | 유효하지 않은 본인 인증 타입입니다.                                                                                                   | This is an invalid authentication type                                                                                                                   |
| 400       | `INVALID_ISO_DATE_FORMAT`                            | 시간 일시 형식이 잘못되었습니다. 시간 형식은 ISO 8601 형식을 준수해야 합니다.                                                         | The format is incorrect. The time format must conform to ISO 8601 format.                                                                                |
| 400       | `INVALID_ORDER_ID`                                   | `orderId`는 영문 대소문자, 숫자, 특수문자(-, \_) 만 허용합니다. 6자 이상 64자 이하여야 합니다.                                        | The order id must be at least 6 and maximum 64 upper and lower case alphabets, numbers, special characters (-, \_, =).                                   |
| 400       | `INVALID_ORDER_NAME`                                 | 주문 이름은 100자 이하여야 합니다.                                                                                                    | The order name must be 100 characters or less.                                                                                                           |
| 400       | `INVALID_PAGING_KEY`                                 | 잘못된 페이징 키 입니다.                                                                                                              | Bad paging key.                                                                                                                                          |
| 403       | `INVALID_PASSWORD`                                   | 결제 비밀번호가 일치하지 않습니다.                                                                                                    | Payment password does not match.                                                                                                                         |
| 400       | `INVALID_PAYABLE_DATE`                               | 지급일자가 올바르지 않습니다.                                                                                                         | The payment date is incorrect.                                                                                                                           |
| 400       | `INVALID_PAYMENT_KEY`                                | 잘못된 결제 키 입니다.                                                                                                                | Invalid payment key.                                                                                                                                     |
| 400       | `INVALID_REFUND_ACCOUNT_INFO`                        | 환불 계좌번호와 예금주명이 일치하지 않습니다.                                                                                         | Refund account number and account holder name do not match.                                                                                              |
| 400       | `INVALID_REFUND_ACCOUNT_NUMBER`                      | 잘못된 환불 계좌번호입니다.                                                                                                           | Incorrect refund account number.                                                                                                                         |
| 400       | `INVALID_REFUND_AMOUNT`                              | 잘못된 환불 금액입니다.                                                                                                               | Incorrect refund amount.                                                                                                                                 |
| 400       | `INVALID_REJECT_CARD`                                | 카드 사용이 거절되었습니다. 카드사 문의가 필요합니다.                                                                                 | Refer to card issuer/decline.                                                                                                                            |
| 400       | `INVALID_REQUEST`                                    | 잘못된 요청입니다.                                                                                                                    | The bad request.                                                                                                                                         |
| 400       | `INVALID_REQUIRED_PARAM`                             | 필수 파라미터가 누락되었습니다.                                                                                                       | The installment amount is incorrect.                                                                                                                     |
| 400       | `INVALID_STOPPED_CARD`                               | 정지된 카드 입니다.                                                                                                                   | This is a suspended card.                                                                                                                                |
| 400       | `INVALID_SUBMALL_ID`                                 | 유효하지 않은 서브몰 ID 입니다. 영문, 숫자 20글자 이하로 입력해주세요.                                                                | This submall ID is not valid. Please enter 20 letters or less in alphabets or numbers.                                                                   |
| 400       | `INVALID_SUCCESS_URL`                                | successUrl 값은 필수 값입니다.                                                                                                        | The successUrl value is a required value.                                                                                                                |
| 400       | `INVALID_TEST_CODE`                                  | 유효하지 않은 테스트 코드입니다.                                                                                                      | Invalid test code                                                                                                                                        |
| 400       | `INVALID_UNREGISTERED_SUBMALL`                       | 미등록된 PG 하위몰 이거나 단독가맹점은 안심클릭/ISP 결제가 필요합니다.                                                                | The PG sub-merchant is not registered yet OR payment authentication method of the card issuer is required for the PG                                     |
| 400       | `INVALID_URL`                                        | url 은 http, https 를 포함한 주소 형식이어야 합니다.                                                                                  | url must be in address format including http and https.                                                                                                  |
| 400       | `INVALID_URL_FORMAT`                                 | 잘못된 URL 형식입니다.                                                                                                                | Invalid URL format.                                                                                                                                      |
| 400       | `INVALID_VALID_HOURS_WITH_DUE_DATE_AND_SINGLE`       | validHours와 dueDate는 같이 사용할 수 없습니다.                                                                                       | validHours and dueDate cannot be used together.                                                                                                          |
| 400       | `INVALID_VIRTUAL_ACCOUNT_TYPE`                       | 유효하지 않은 가상계좌 타입입니다.                                                                                                    | Invalid virtual account type.                                                                                                                            |
| 400       | `MAINTAINED_METHOD`                                  | 현재 점검 중 입니다.                                                                                                                  | The method is being maintained now                                                                                                                       |
| 400       | `NOT_ALLOWED_HOLIDAY`                                | 공휴일은 지급일로 선택할 수 없습니다.                                                                                                 | Public holidays cannot be selected as payment dates.                                                                                                     |
| 400       | `NOT_ALLOWED_INSTALLMENT_BELOW_AMOUNT`               | 해당 카드는 10000원 미만 할부 거래가 불가한 카드입니다.                                                                               | This card cannot be used for installment transactions less than KRW 10000.                                                                               |
| 400       | `NOT_ALLOWED_POINT_USE`                              | 포인트 사용이 불가한 카드로 카드 포인트 결제에 실패했습니다.                                                                          | Card point payment failed because the card cannot be used points.                                                                                        |
| 400       | `NOT_ENOUGH_AMOUNT`                                  | 지급가능한 금액을 초과했습니다.                                                                                                       | The payable amount has been exceeded.                                                                                                                    |
| 400       | `NOT_FOUND_TERMINAL_ID`                              | 단말기번호(Terminal Id)가 없습니다. 토스페이먼츠로 문의 바랍니다.                                                                     | There is no Terminal Id. Please contact Toss Payments.                                                                                                   |
| 400       | `NOT_MATCH_PAYEE_NAME`                               | 수취인 성명이 불일치 합니다.                                                                                                          | The payee's name is inconsistent.                                                                                                                        |
| 400       | `NOT_MATCHES_CUSTOMER_KEY`                           | 빌링 인증 고객키와 결제 요청 고객키가 일치하지 않습니다.                                                                              | The billing authentication customer key and the payment request customer key do not match.                                                               |
| 400       | `NOT_MATCHES_REFUNDABLE_AMOUNT`                      | 잔액 결과가 일치하지 않습니다.                                                                                                        | Balance results do not match.                                                                                                                            |
| 400       | `NOT_REGISTERED_BUSINESS`                            | 등록되지 않은 사업자 번호입니다.                                                                                                      | Unregsitered business registration number                                                                                                                |
| 400       | `NOT_REGISTERED_SUBMALL`                             | PG 하위몰 사업자번호가 등록되어 있지 않습니다.                                                                                        | PG sub-mall business number is not registered.                                                                                                           |
| 400       | `NOT_SUPPORTED_CARD_TYPE`                            | 지원되지 않는 카드 종류입니다.                                                                                                        | This card type is not supported.                                                                                                                         |
| 400       | `NOT_SUPPORTED_CARRIER`                              | 지원되지 않는 이동 통신사입니다.                                                                                                      | Unsupported carrier.                                                                                                                                     |
| 400       | `NOT_SUPPORTED_METHOD`                               | 지원되지 않는 결제수단입니다.                                                                                                         | This payment method is not supported.                                                                                                                    |
| 400       | `NOT_SUPPORTED_METHOD`                               | 지원되지 않는 결제수단입니다.                                                                                                         | This payment method is not supported.                                                                                                                    |
| 400       | `NOT_SUPPORTED_MONTHLY_INSTALLMENT_PLAN`             | 할부 또는 무이자 할부가 지원되지 않는 카드입니다.                                                                                     | This card does not support installment or interest-free installment.                                                                                     |
| 400       | `NOT_SUPPORTED_PROCESS`                              | 지원되지 않는 작업입니다.                                                                                                             | This operation is not supported.                                                                                                                         |
| 400       | `NOT_SUPPORTED_USD`                                  | 선택하신 카드 또는 결제수단은 달러 결제가 불가합니다.                                                                                 | The selected card or payment method cannot be paid in dollars.                                                                                           |
| 400       | `PAY_PROCESS_ABORTED`                                | 결제가 취소되었거나 진행되지 않았습니다.                                                                                              | Payment has been canceled or has not been processed.                                                                                                     |
| 400       | `PAY_PROCESS_CANCELED`                               | 결제가 사용자에 의해 취소되었습니다.                                                                                                  | Payment has been canceled by the customer.                                                                                                               |
| 400       | `REFUND_REJECTED`                                    | 환불이 거절됐습니다. 결제사에 문의 부탁드립니다.                                                                                      | The refund has been rejected. Please contact the respective payment provider.                                                                            |
| 400       | `REQUIRED_ACCOUNT_KEY`                               | 고정계좌는 발급용 고객키값이 필수입니다.                                                                                              | For fixed accounts, a customer key value is required.                                                                                                    |
| 400       | `REQUIRED_AMOUNT`                                    | 금액 값이 필수입니다.                                                                                                                 | Amount value is required.                                                                                                                                |
| 400       | `USER_ACCOUNT_ON_HOLD`                               | 계정이 사용 불가능한 상태입니다.                                                                                                      | Account is on hold.                                                                                                                                      |
| 400       | `EXCEEDS_TRANSFER_AMOUNT_MAXIMUM`                    | 계좌이체는 한 번에 1,000만 원 이하로만 결제하실 수 있어요. 금액을 낮춰 다시 시도해 주세요.                                            | Account transfers are limited to 10,000,000 KRW per transaction. Please lower the amount and try again.                                                  |
| 401       | `UNAUTHORIZED_KEY`                                   | 인증되지 않은 시크릿 키 혹은 클라이언트 키 입니다.                                                                                    | This is an unauthenticated secret key or client key.                                                                                                     |
| 403       | `EXCEED_MAX_AUTH_COUNT`                              | 최대 인증 횟수를 초과했습니다. 카드사로 문의해주세요.                                                                                 | The maximum number of authentications has been exceeded. Please contact your credit card company.                                                        |
| 403       | `EXCEED_MAX_REFUND_AMOUNT`                           | 하루 또는 한달 환불 가능한 금액을 초과했습니다.                                                                                       | This merchant have exceeded your daily or monthly refundable amount.                                                                                     |
| 403       | `EXCEED_MAX_REFUND_DUE`                              | 환불 가능한 기간이 초과했습니다.                                                                                                      | The refundable period has been exceeded.                                                                                                                 |
| 403       | `FORBIDDEN_CONSECUTIVE_REQUEST`                      | 반복적인 요청은 허용되지 않습니다. 잠시 후 다시 시도해주세요.                                                                         | Repetitive requests are not allowed. Please try again in a few minutes.                                                                                  |
| 403       | `FORBIDDEN_REQUEST`                                  | 허용되지 않은 요청입니다.                                                                                                             | This request is not allowed.                                                                                                                             |
| 403       | `NOT_ALLOWED_CHANGING_ACCOUNT`                       | 이미 입금, 반납된 계좌의 정보 변경은 불가합니다.                                                                                      | It is not possible to change the information of the account that has already been deposited or returned.                                                 |
| 403       | `NOT_ALLOWED_PARTIAL_REFUND`                         | 에스크로 주문, 현금 카드 결제 등의 사유로 부분 환불이 불가합니다.                                                                     | Partial refunds are not available for reasons such as escrow or cash payment.                                                                            |
| 403       | `NOT_ALLOWED_PARTIAL_REFUND_WAITING_DEPOSIT`         | 입금 대기중인 결제는 부분 환불이 불가합니다.                                                                                          | Partial refunds are not available while pending deposit.                                                                                                 |
| 403       | `NOT_ALLOWED_REFUND_BANK`                            | 환불 가능한 은행이 아닙니다.                                                                                                          | Not a refundable bank.                                                                                                                                   |
| 403       | `NOT_AVAILABLE_BANK`                                 | 은행 서비스 시간이 아닙니다.                                                                                                          | Not bank service time.                                                                                                                                   |
| 403       | `NOT_CANCELABLE_AMOUNT`                              | 취소 할 수 없는 금액 입니다.                                                                                                          | This is a non-cancelable amount.                                                                                                                         |
| 403       | `NOT_CANCELABLE_PAYMENT`                             | 취소 할 수 없는 결제 입니다.                                                                                                          | This is a non-cancelable payment.                                                                                                                        |
| 403       | `NOT_SUPPORTED_REFUND`                               | 환불 가능한 상점이 아닙니다.                                                                                                          | Not a refundable merchant.                                                                                                                               |
| 403       | `REJECT_ACCOUNT_PAYMENT`                             | 잔액부족으로 결제에 실패했습니다.                                                                                                     | Payment failed due to insufficient balance                                                                                                               |
| 403       | `REJECT_CARD_COMPANY`                                | 결제 승인이 거절되었습니다.                                                                                                           | Payment confirm is rejected                                                                                                                              |
| 404       | `NOT_FOUND`                                          | 존재하지 않는 정보 입니다.                                                                                                            | This information does not exist.                                                                                                                         |
| 404       | `NOT_FOUND_BILLING`                                  | 존재하지 않는 빌링 결제 인증 정보 입니다.                                                                                             | Billing payment authentication information that does not exist.                                                                                          |
| 404       | `NOT_FOUND_HTTP_METHOD`                              | 존재하지 않는 HTTP 메소드 접근입니다.                                                                                                 | This HTTP method does not allowed.                                                                                                                       |
| 404       | `NOT_FOUND_MERCHANT`                                 | 존재하지 않는 상점 정보 입니다.                                                                                                       | The merchant does not exist.                                                                                                                             |
| 404       | `NOT_FOUND_MERCHANT_INTEGRATION`                     | 존재하지 않는 상점 연동 정보 입니다.                                                                                                  | The integration information does not exist.                                                                                                              |
| 404       | `NOT_FOUND_METHOD`                                   | 존재하지 않는 결제수단 입니다.                                                                                                        | This payment method does not exist.                                                                                                                      |
| 404       | `NOT_FOUND_METHOD_IN_GROUP`                          | 같은 그룹내에 존재하지 않는 결제수단 입니다.                                                                                          | This payment method does not exist in the same group                                                                                                     |
| 404       | `NOT_FOUND_METHOD_OWNERSHIP`                         | 결제수단의 소유자가 아닙니다.                                                                                                         | This method ownership is not correct.                                                                                                                    |
| 404       | `NOT_FOUND_PAYMENT`                                  | 존재하지 않는 결제 정보 입니다.                                                                                                       | The payment does not exist.                                                                                                                              |
| 404       | `NOT_FOUND_PAYMENT_SESSION`                          | 결제 시간이 만료되어 결제 진행 데이터가 존재하지 않습니다.                                                                            | Payment session does not exist because the session time has expired.                                                                                     |
| 404       | `NOT_FOUND_SUBMALL`                                  | 존재하지 않는 서브몰입니다.                                                                                                           | This sub-mall does not exist.                                                                                                                            |
| 404       | `PAYOUT_NOT_FOUND`                                   | 존재하지 않는 지급대행 입니다.                                                                                                        | The payout does not exist.                                                                                                                               |
| 500       | `FAILED_BILL_KEY_AUTH_CREATION`                      | 빌링 결제 인증 중 키 생성에 실패했습니다. 잠시 후 다시 시도해주세요.                                                                  | Key generation failed during billing payment verification. Please try again in a few minutes.                                                            |
| 500       | `FAILED_BILLING_AUTO_CANCEL`                         | 빌링 자동결제 취소에 일시적인 오류가 발생했습니다.                                                                                    | A temporary error occurred while billing auth cancellation.                                                                                              |
| 500       | `FAILED_DB_PROCESSING`                               | 잘못된 요청 값으로 처리 중 DB 에러가 발생했습니다.                                                                                    | A DB error occurred while processing with an invalid request value.                                                                                      |
| 500       | `FAILED_HASH_DATA_CREATION`                          | 해시 데이터 생성 중 오류가 발생했습니다.                                                                                              | An error occurred while generating hash data.                                                                                                            |
| 500       | `FAILED_INTERNAL_SYSTEM_PROCESSING`                  | 내부 시스템 처리 작업이 실패했습니다. 잠시 후 다시 시도해주세요.                                                                      | Internal system processing operation has failed. Please try again in a few minutes.                                                                      |
| 500       | `FAILED_METHOD_HANDLING`                             | 결제 중 선택한 결제수단 처리에 일시적인 오류가 발생했습니다.                                                                          | There was a temporary error in processing the payment method you selected during checkout.                                                               |
| 500       | `FAILED_METHOD_HANDLING_CANCEL`                      | 취소 중 결제 시 사용한 결제수단 처리과정에서 일시적인 오류가 발생했습니다.                                                            | A temporary error occurred while processing cancellation.                                                                                                |
| 500       | `FAILED_PAYMENT_INTERNAL_SYSTEM_PROCESSING`          | 결제 기관(카드사, 은행, 국세청 등) 오류입니다. 결제 기관에서 보내 준 에러 메시지가 표시됩니다.                                        | Provider error. The error message received from provider will be displayed.                                                                              |
| 500       | `FAILED_REFUND_PROCESS`                              | 은행 응답시간 지연이나 일시적인 오류로 환불요청에 실패했습니다.                                                                       | The refund request failed due to a delay in the bank response time or a temporary error.                                                                 |
| 500       | `COMMON_ERROR`                                       | 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.                                                                              | A temporary error has occurred. Please try again in a few minutes.                                                                                       |
| 500       | `UNKNOWN_ERROR`                                      | 확인되지 않은 오류입니다. 잠시 후 다시 시도해주세요.                                                                                  | An unknown error occurred. Please try again in a few minutes.                                                                                            |

## 브랜드페이 API 별 에러

### 미동의 약관 조회

### 약관 동의

### Access Token 발급

### SecretKey로 결제수단 조회

### 카드 결제수단 삭제

### 계좌 결제수단 삭제

### 결제 승인

### 자동결제 실행

### 회원 탈퇴 처리

### 카드 프로모션 조회

### 계좌 프로모션 조회

## 구 모듈 에러

기존 전자결제 연동 모듈의 에러는 아래 링크에서 확인할 수 있습니다.

[구 모듈 에러](/legacy/errors)
