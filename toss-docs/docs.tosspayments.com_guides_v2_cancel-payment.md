***

title: 결제 취소하기
description: 토스페이먼츠 결제 취소 API로 금액 전액・부분 환불하는 방법, 가상계좌 결제 취소하는 방법, 결제위젯에서 가상계좌 정보 확인하는 방법을 소개합니다.
keyword: 결제 취소, 취소, 부분 취소, 환불, 취소 기한, 카드 취소, 계좌이체 취소, 휴대폰 취소, 가상계좌 취소, 페이팔 취소, PayPal 취소, 취소 정책, 환불 기한, 취소 기간, 환불 소요 기간
-----------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 결제 취소하기

{description}

API 실행해보기

## 결제 취소 기한

먼저 각 결제수단마다 취소 기한, 취소 소요 시간이 다른데요. 아래 표에서 정보를 확인하고 구매자에게 필요한 정보를 안내해주세요.

| 결제 수단                                        | 취소 기한                                                                                            | 취소 소요 기간                                                                                                  |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| [카드](/resources/glossary/card-payment)         | 취소 기한은 없지만, 카드사 별로 결제 데이터 보관 기간이 달라서 1년을 초과하면 취소가 안될 수 있어요. | 결제가 매입되기 전에는 취소 직후 환불됩니다. 매입 이후 또는 부분 취소는 요청 후 영업일 기준 3~4일이 소요됩니다. |
| [계좌이체](/resources/glossary/transfer-payment) | 180일 이내의 거래만 취소 가능합니다.                                                                 | 실시간으로 환불됩니다.                                                                                          |
| [가상계좌](/resources/glossary/virtual-account)  | 상점마다 설정이 다를 수 있으나 보통 365일 동안 취소가 가능합니다.                                    | 영입일 기준 총 2일이 소요됩니다. 의심거래로 탐지된 결제는 최대 영업일 기준 9일이 소요될 수 있습니다.            |
| [휴대폰](/resources/glossary/mobile-payment)     | 통신사 정책으로 결제가 발생한 당월에만 취소가 가능합니다.                                            | 당일 취소됩니다.                                                                                                |
| 해외 간편결제(PayPal)                            | 180일 이내의 거래만 취소 가능합니다.                                                                 | 영업일 기준 최대 5일이 소요됩니다. 일부 환불은 카드 회사에 따라 최대 30일이 소요될 수 있습니다.                 |



title: 이미 정산 받은 결제도 취소 가능한가요?


네 가능합니다. 다음 정산금에서 상계처리됩니다.



title: 부분 취소도 가능한가요?


네 가능합니다. [부분 취소](#부분-취소하기)를 참고해주세요. 결제 취소 API의 [`cancelAmount`](/reference#v1paymentspaymentkeycancelpost-cancelamount)를 부분 취소할 금액으로 설정해주세요. 카드 결제의 부분 취소는 요청 후 영업일 기준 3~4일이 소요됩니다.

하지만 특정 결제수단은 부분 취소가 불가능합니다. 구매자가 가상계좌에 입금을 아직 안 했다면 부분 취소를 할 수 없어요. 발급된 가상계좌의 입금 금액을 바꿀 수 없기 때문이에요. 가상계좌 입금 이후에는 부분 취소가 가능합니다.



title: 에스크로 결제는 어떻게 취소하나요?


배송 정보가 등록되지 않은 [에스크로](/resources/glossary/escrow) 결제는 다른 결제와 똑같이 취소할 수 있습니다.

하지만 배송 정보가 등록된 에스크로 결제는 구매자가 배송을 받은 뒤에만 결제를 취소할 수 있어요. 구매자가 받는 구매확정 메일에서 '**구매취소 요청하기**'를 선택하면 됩니다.

만약에 구매자가 배송을 받은 뒤에 부분 취소를 원한다면, 구매확정 메일에서 일단 '**구매확정하기**'를 선택하고 내 상점에서 결제 취소 API로 [부분 취소](\(#부분-취소하기\))를 요청하면 됩니다.

## 전액 취소하기

[결제 취소 API](/reference#결제-취소) 엔드포인트에 [결제 승인 API](/reference#결제-승인) 요청 결과로 받은 [`paymentKey`](/reference#v1paymentspaymentkeycancelpost-paymentkey)를 Path 파라미터로 추가하세요.
API 요청 본문에 취소 이유를 [`cancelReason`](/reference#v1paymentspaymentkeycancelpost-cancelreason) 파라미터로 추가하세요. [멱등키 헤더](/reference/using-api/authorization#멱등키-헤더)를 추가하면 중복 취소 없이 안전하게 처리됩니다.

API 응답의 [`cancels`](/reference#paymentdetaildto-cancels) 필드를 확인하세요. 결제 취소 정보 객체가 배열 안에 돌아옵니다. 각 취소 거래마다 거래를 구분하는 [`transactionKey`](/reference#paymenttransactiondto-transactionkey)를 가지고 있습니다.

```json title="응답 - Payment 객체" {39-50}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "lastTransactionKey": "<UniqueId name='paymentKey.lastTransactionKey' />",
  "paymentKey": "<UniqueId name='paymentKey.cancelPayment' />",
  "orderId": "<UniqueId name='orderId.cancelPayment' />",
  "orderName": "토스 티셔츠 외 2건",
  "currency": "KRW",
  "method": "카드",
  "status": "CANCELED",
  //...
  "cancels": [
    {
      "cancelReason": "구매자가 취소를 원함",
      "canceledAt": "2022-01-01T11:32:04+09:00",
      "cancelAmount": 10000,
      "taxFreeAmount": 0,
      "taxExemptionAmount": 0,
      "refundableAmount": 0,
      "transferDiscountAmount": 0,
      "easyPayDiscountAmount": 0,
      "transactionKey": "8B4F646A829571D870A3011A4E13D640",
      "receiptKey": "V4AJ6AhSWsGN0RocizZQlagPLN8s2IahJLXpfSHzQBTKoDG7",
      "cancelStatus": "DONE",
      "cancelRequestId": null
    }
  ],
  "secret": null,
  "type": "NORMAL",
  "easyPay": "토스페이",
  "country": "KR",
  "failure": null,
  "totalAmount": 10000,
  "balanceAmount": 0,
  "suppliedAmount": 0,
  "vat": 0,
  "metadata": null,
  "taxFreeAmount": 0,
  "taxExemptionAmount": 0
}
```

## 부분 취소하기

결제 금액 중 일부만 취소하려면 [결제 취소 API](/reference#결제-취소)의 엔드포인트에 [`paymentKey`](/reference#v1paymentspaymentkeycancelpost-paymentkey)를 추가하고 [`cancelAmount`](/reference#v1paymentspaymentkeycancelpost-cancelamount) 파라미터에 취소할 금액을 추가해주세요. [`cancelAmount`](/reference#v1paymentspaymentkeycancelpost-cancelamount)에 값을 넣지 않으면 전액 취소됩니다.

부분 취소를 여러 번 하면 아래와 같이 [`cancels`](/reference#paymentdetaildto-cancels) 필드에 취소 객체가 여러 개 돌아옵니다.

```json title="응답 - Payment 객체"
{
  // ...
  "cancels": [
    {
      "cancelAmount": 1000,
      "cancelReason": "구매자가 취소를 원함",
      "taxFreeAmount": 0,
      "taxExemptionAmount": 0,
      "refundableAmount": 9000,
      "transferDiscountAmount": 0,
      "easyPayDiscountAmount": 0,
      "canceledAt": "2022-01-01T23:23:52+09:00",
      "transactionKey": "8B4F646A829571D870A3011A4E13D640",
      "receiptKey": "CuskOnzZEf0Xbwo8eMZ56slTAXbJ8jUjTX3n6SNuvY5d7Fpf",
      "cancelStatus": "DONE",
      "cancelRequestId": null
    },
    {
      "cancelAmount": 1000,
      "cancelReason": "구매자가 다른 품목도 취소를 원함",
      "taxFreeAmount": 0,
      "taxExemptionAmount": 0,
      "refundableAmount": 8000,
      "transferDiscountAmount": 0,
      "easyPayDiscountAmount": 0,
      "canceledAt": "2022-01-02T20:00:00+09:00",
      "transactionKey": "6673C15BF350C3F9BF45CEFC48C7A24E",
      "receiptKey": "PLDm1CZSQxTBvYrHytz3yt3MU09Nx57IoCxIEJ8HPzOyIRos",
      "cancelStatus": "DONE",
      "cancelRequestId": null
    }
  ]
  // ...
}
```

## Case 1. 가상계좌 결제 환불하기

[가상계좌](/resources/glossary/virtual-account) 결제를 취소하면 **취소일+2일**에 은행에서 구매자의 계좌로 입금 처리를 해줍니다. 따라서 가상계좌 결제를 취소할 때는 환불받을 계좌 정보를 [결제 취소 API](/reference#결제-취소) 요청에 포함해야 합니다.

*   **구매자가 입금을 완료했으면**: [`refundReceiveAccount`](/reference#v1paymentspaymentkeycancelpost-refundreceiveaccount)에 환불받을 계좌 정보를 포함해서 결제 취소를 요청하세요. 환불 계좌의 번호와 예금주의 유효성이 확인되면 해당 계좌로 취소 금액이 환불됩니다.
*   **구매자가 입금하기 전이라면**: 일반 결제와 똑같이 취소하세요. `refundReceiveAccount` 파라미터를 추가할 필요 없습니다. 발급된 가상계좌의 입금 금액을 바꿀 수 없기 때문에 부분 취소가 불가능합니다.

응답은 다른 취소 요청과 동일하게 [Payment 객체](/reference#payment-객체)의 [`cancels`](/reference#paymentdetaildto-cancels)로 돌아옵니다.

```json title="응답" {36-49}
{
  "mId": "tvivarepublica",
  "version": "2022-11-16",
  "lastTransactionKey": "<UniqueId name='lastTransactionKey.cancelVirtualAccountPayment' />",
  "paymentKey": "<UniqueId name='paymentKey.cancelVirtualAccountPayment' />",
  "orderId": "<UniqueId name='orderId.cancelVirtualAccountPayment' />",
  "orderName": "토스 티셔츠 외 2건",
  "currency": "KRW",
  "method": "가상계좌",
  "status": "PARTIAL_CANCELED",
  "requestedAt": "2022-01-01T11:48:53+09:00",
  "approvedAt": "2022-01-01T11:49:35+09:00",
  "useEscrow": false,
  "cultureExpense": false,
  "checkout": {
    "url": "https://api.tosspayments.com/v1/payments/<UniqueId name='paymentKey.cancelVirtualAccountPayment' />/checkout"
  },
  "card": null,
  "virtualAccount": {
    "accountNumber": "X6505831718354",
    "accountType": "일반",
    "bankCode": "20",
    "customerName": "김토스",
    "dueDate": "2022-01-03T11:48:53+09:00",
    "expired": true,
    "settlementStatus": "INCOMPLETED",
    "refundStatus": "NONE",
    "refundReceiveAccount": null
  },
  "transfer": null,
  "mobilePhone": null,
  "giftCertificate": null,
  "cashReceipt": null,
  "cashReceipts": null,
  "discount": null,
  "cancels": [
    {
      "cancelReason": "구매자 변심",
      "canceledAt": "2022-01-01T11:51:04+09:00",
      "cancelAmount": 10000,
      "taxFreeAmount": 0,
      "taxExemptionAmount": 0,
      "refundableAmount": 0,
      "transferDiscountAmount": 0,
      "easyPayDiscountAmount": 0,
      "transactionKey": "ND38Q0IGWUG7UC02G6G1GL1XJRG2BO5N",
      "receiptKey": "aIHE2heVz6hwRIWsu0msyxjF6xhPtn9T44fij4BF9bNUN64G",
      "cancelStatus": "DONE",
      "cancelRequestId": null
    }
  ],
  "secret": null,
  "type": "NORMAL",
  "easyPay": null,
  "country": "KR",
  "failure": null,
  "totalAmount": 10000,
  "balanceAmount": 0,
  "suppliedAmount": 0,
  "vat": 0,
  "taxFreeAmount": 0,
  "metadata": null,
  "taxExemptionAmount": 0
}
```

## Case 2. 결제위젯 환불 계좌 확인하기

결제위젯 어드민 > 기능 > 가상계좌 메뉴에서 **가상계좌 환불 정보 입력 > 사용함**을 선택했다면 구매자가 환불 계좌 정보를 입력하는 UI를 사용할 수 있어요.

![결제위젯 가상계좌 설정](https://static.tosspayments.com/docs/guides/learn/결제%20취소하기.png)

환불 계좌 정보는 [결제 승인](/guides/v2/payment-widget/integration#3-결제-승인하기)으로 받은 Payment 객체의 [`virtualAccount.refundReceiveAccount`](/reference#paymentdetaildto-virtualaccount) 필드에서 확인할 수 있어요.
다만 **해당 정보는 결제창을 띄운 시점부터 30분 동안만 조회**할 수 있기 때문에 결제 승인 직후 응답을 저장해주세요. 30분이 지나면 `refundReceiveAccount` 필드의 값은 `null`로 내려옵니다.

저장한 정보를 [결제 취소 API](#case-1-가상계좌-환불하기)의 파라미터로 사용하세요. 결제위젯에서 구매자의 환불 정보를 받는 UI만 제공하기 때문에 환불 계좌 정보를 입력받아도 해당 계좌로 자동 환불되지 않습니다.

```json title="응답" {13-17}
{
  // Payment 객체
  // ...
  "virtualAccount": {
    "accountNumber": "X6505636518308",
    "accountType": "일반",
    "bankCode": "20",
    "customerName": "박토스",
    "dueDate": "2022-01-10T21:05:09+09:00",
    "expired": false,
    "settlementStatus": "INCOMPLETED",
    "refundStatus": "NONE",
    "refundReceiveAccount": {
      "bankCode": "20",
      "accountNumber": "001012341342",
      "holderName": "박토스"
    }
  }
  // ...
}
```
