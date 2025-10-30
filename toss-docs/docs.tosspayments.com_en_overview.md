***

title: Online payment process
description: Explore the Korean online payment process, step by step.
keyword:  Toss Payments, payment, payment gateway, payment gateway integration, payment gateway integration flow
----------------------------------------------------------------------------------------------------------------

# Online payment process

Explore the Korean online payment process, step by step.

## Overview

In most global online payment integrations, the customer's card details are verified and authorized in a single step. However, in Korean online payment systems the customer's identity must be authenticated for the payment to be authorized. This means that they are treated as two separate steps during integration, or two-track.

### 1. Authentication

Online payments in Korean involve a unique authentication process, where ownership of the payment method must be verified.

For example, during a card payment, customers must prove ownership of the card through a third-party authentication app or on an AppCard. Authentication is a vital step to fight fraud and online identity theft.

#### What are AppCards?

All card companies in Korea release their own app, which we call AppCards. In AppCards, customers can register their cards and use them online and offline like a digital wallet.

![Card company app example image](https://static.tosspayments.com/docs/global/demo04-2.png)

To register your card, you must verify your identity through a standard authentication process. Once the card is registered, you can use biometric recognition or a simple password for verification. Because they are quick and easy to use, AppCards are standard when making an online card payment in Korea. See the [Card payment guide](/en/integration-types) for a more detailed walkthrough of AppCards.

While the AppCard makes it easier for the customer to pay, it makes it a little more difficult for the developers. In mobile environments, add the AppCard [app schemes](/guides/v2/webview#앱스킴-리스트) to your app and make sure your app can handle intent URLs.

### 2. Authorization

Once the payment method is authenticated, the payment must be authorized. During authorization, the payment method provider deducts the payment amount from the customer's account. For example, if the customer is using a credit card, credit is deducted from the card's limit.

#### Why is payment two-track?

In most global payment systems, authentication (or verification) and authorization occurs in a single step, and we call this the one-track payment. However due to strict online payment regulations in Korea, the card holder's identity must be verified before the payment can be authorized. Since there are two steps, authentication and authorization, we call this the two-track payment.

Although one-track seems more convenient, two-track payment is safer for both the customer and the merchant. It protects the customer's assets and protects the merchant from disputes. Furthermore, since the whole process is synchronous, webhooks are not mandatory for integration and the data that you receive from the authorization does not have to be validated in any way.

Two-track is standard in Korea. If you must make a one-track payment, contact your sales associate to assess the risks.

#### How is two-track implemented in integration?

Toss Payments will ask you to define a `successUrl` and `failUrl` during your payment request. When the authentication is successful, Toss Payments redirects your app to the `successUrl` and if it fails, to the `failUrl`. Query parameters are added to each URL during the redirect to help you move on to the next step or debug.

For example, the below query parameters are added to the `successUrl` during the redirect. You must use these values to request authorization.

![successurl](https://static.tosspayments.com/docs/learn/successurl-example.png)

### 3. Capture

Capture is the process by which Toss Payments receives cash for the goods or services the customer bought on credit. Toss Payments sends the card company payment data, such as card numbers and payment amounts, and the card company gives Toss Payments the requested funds.

When using Toss Payments systems, all your payments are automatically captured everyday at midnight. You may also use manual capture and request it yourself.

### 4. Settlement

Toss Payments settles the payment with the merchant. Toss Payments will send the payment amount accrued by the merchant during the settlement period, after deducting Toss Payments service fees. The settlement period depends on your contract.

***
