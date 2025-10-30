***

title: 간편결제 응답 확인하기
description: 간편결제에서는 구매자가 카드, 계좌, 포인트를 함께 사용할 수도 있는데요. 구매자가 선택한 결제수단에 따라 결제 승인의 응답이 어떻게 바뀌는지 설명해드려요.
keyword: 애플페이, 네이버페이, 카카오페이, 토스페이, 페이코, 삼성페이, 간편결제, 간편결제 응답, easyPay.amount, easyPay.discountAmount, 결제 응답 객체, 포인트 결제, 카카오페이 머니, 네이버페이 머니, 페이코 포인트, 쿠폰, 즉시할인, 토스포인트, 카카오페이 포인트, 페이코 쿠폰,
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 간편결제 응답 확인하기

{description}

간편결제에서 카드, 계좌, 포인트 수단을 2개 이상 사용하는 것을 [복합결제](/resources/glossary/multi-pay)라고 하는데요. 사용할 수 있는 조합은 각 간편결제사의 정책을 확인하세요. 적립식 결제를 지원하는 토스페이, 카카오페이, 네이버페이, 페이코는 적립식 결제수단과 카드 또는 계좌를 조합해서 사용할 수 있습니다. 카드와 계좌를 동시에 사용하는 복합결제는 모든 간편결제사에서 제공하지 않아요.

## 간편결제 결제수단 타입

| 결제수단        | 설명                                                                                                                                      | 응답 객체 금액 필드                                                           | 예시                                                                    |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 신용·체크 카드  | 구매자가 간편결제 서비스에 등록한 카드                                                                                                    | [`card.amount`](/reference#paymentdetaildto-cardamount)                       | 토스페이, 네이버페이 등 간편결제에 등록된 카드                          |
| 충전식 결제수단 | 구매자가 금액을 충전해서 사용하는 결제수단으로 간편결제 서비스에 등록한 **계좌 혹은 현금성 포인트**                                       | [`easyPay.amount`](/reference#paymentdetaildto-easypayamount)                 | 토스페이에 연결된 계좌, 카카오페이 머니, 네이버페이 머니, 페이코 포인트 |
| 적립식 결제수단 | 구매자가 간편결제사에서 제공하는 결제 서비스를 이용해서 **적립된 포인트, 쿠폰, 즉시할인** 금액으로 카드나 충전식 결제수단과 조합해서 사용 | [`easyPay.discountAmount`](/reference#paymentdetaildto-easypaydiscountamount) | 토스포인트, 카카오페이 포인트, 페이코 쿠폰                              |

## Case 1. 간편결제에 등록된 카드로 결제했을 때

토스페이에 등록된 카드로 15,000원을 결제하면 전체 결제 금액 [`totalAmount`](/reference#paymentdetaildto-totalamount)는 카드로 결제한 금액인 [`card.amount`](/reference#paymentdetaildto-cardamount)와 동일합니다.

```json {23}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='paymentKey.easyPayCard' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='lastTransactionKey.easyPayCard' />",
  "method": "간편결제",
  "orderId": "<UniqueId name='orderId.easyPayCard' />",
  "orderName": "토스 티셔츠 외 2건",
  //...
  "card": {
    "issuerCode": "61",
    "acquirerCode": "31",
    "number": "123456******7890",
    "installmentPlanMonths": 0,
    "isInterestFree": false,
    "interestPayer": null,
    "approveNo": "21974757",
    "useCardPoint": false,
    "cardType": "신용",
    "ownerType": "개인",
    "acquireStatus": "READY",
    "amount": 15000
  },
  "easyPay": {
    "provider": "토스페이",
    "amount": 0,
    "discountAmount": 0
  },
  //...
  "totalAmount": 15000
}
```

## Case 2. 간편결제에 등록된 카드 + 적립식 결제수단으로 결제했을 때

토스페이에 등록된 카드로 10,000원을 결제하고 토스포인트에서 5,000원을 사용해 총 15,000원을 결제합니다.

전체 결제 금액 [`totalAmount`](/reference#paymentdetaildto-totalamount)은 [`card.amount`](/reference#paymentdetaildto-cardamount)와 [`easyPay.discountAmount`](/reference#paymentdetaildto-easypaydiscountamount)의 합계입니다.

```json {23,27}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='easyPayCardPoint.paymentKey' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='easyPayCardPoint.lastTransactionKey' />",
  "method": "간편결제",
  "orderId": "<UniqueId name='payment.orderId' />",
  "orderName": "토스 티셔츠 외 2건",
  //...
  "card": {
    "issuerCode": "61",
    "acquirerCode": "31",
    "number": "123456******7890",
    "installmentPlanMonths": 0,
    "isInterestFree": false,
    "interestPayer": null,
    "approveNo": "21706400",
    "useCardPoint": false,
    "cardType": "체크",
    "ownerType": "개인",
    "acquireStatus": "READY",
    "amount": 10000
  },
  "easyPay": {
    "provider": "토스페이",
    "amount": 0,
    "discountAmount": 5000
  },
  //...
  "totalAmount": 15000
}
```

## Case 3. 충전식 결제수단으로 결제했을 때

토스페이에 연결된 계좌로 결제하면 전체 결제 금액 [`totalAmount`](/reference#paymentdetaildto-totalamount)는 계좌로 결제한 금액인 [`easyPay.amount`](/reference#paymentdetaildto-easypayamount)와 동일합니다. 즉 [`easyPay`](/reference#paymentdetaildto-easypay) 객체만 확인하면 됩니다.

```json {14}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='easyPayBank.paymentKey' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='easyPayBank.lastTransactionKey' />",
  "method": "간편결제",
  "orderId": "<UniqueId name='payment.orderId' />",
  "orderName": "토스 티셔츠 외 2건",
  //...
  "card": null,
  "easyPay": {
    "provider": "토스페이",
    "amount": 15000,
    "discountAmount": 0
  },
  //...
  "totalAmount": 15000
}
```

## Case 4. 충전식 결제수단 + 적립식 결제수단으로 결제했을 때

토스페이에 연결된 계좌로 15,000원을 결제하고 토스포인트에서 5,000원을 사용해 총 15,000원을 결제합니다.

전체 결제 금액 [`totalAmount`](/reference#paymentdetaildto-totalamount)는 [`easyPay.amount`](/reference#paymentdetaildto-easypayamount)와 [`easyPay.discountAmount`](/reference#paymentdetaildto-easypaydiscountamount)의 합계입니다.

```json {14-15}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='easyPayBankPoint.paymentKey' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='easyPayBankPoint.lastTransactionKey' />",
  "method": "간편결제",
  "orderId": "<UniqueId name='payment.orderId' />",
  "orderName": "토스 티셔츠 외 2건",
  //...
  "card": null,
  "easyPay": {
    "provider": "토스페이",
    "amount": 10000,
    "discountAmount": 5000
  },
  //...
  "totalAmount": 15000
}
```

## Case 5. 적립식 결제수단으로 결제했을 때

토스포인트로 15,000원을 결제하면 전체 결제 금액 [`totalAmount`](/reference#paymentdetaildto-totalamount)는 [`easyPay.discountAmount`](/reference#paymentdetaildto-easypaydiscountamount)와 동일합니다. 즉 [`easyPay`](/reference#paymentdetaildto-easypay) 객체만 확인하면 됩니다.

```json {15}
{
  "mId": "tosspayments",
  "version": "2022-11-16",
  "paymentKey": "<UniqueId name='easyPayBankPoint.paymentKey' />",
  "status": "DONE",
  "lastTransactionKey": "<UniqueId name='easyPayBankPoint.lastTransactionKey' />",
  "method": "간편결제",
  "orderId": "<UniqueId name='payment.orderId' />",
  "orderName": "토스 티셔츠 외 2건",
  //...
  "card": null,
  "easyPay": {
    "provider": "토스페이",
    "amount": 0,
    "discountAmount": 15000
  },
  //...
  "totalAmount": 15000
}
```
