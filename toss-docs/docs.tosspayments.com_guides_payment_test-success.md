***

title: 테스트용 성공 리다이렉트 페이지
description: 결제창 연동 가이드 테스트용 실패 리다이렉트 페이지입니다.
keyword: failUrl, 실패 리다이렉트, 리다이렉트, 테스트
searchIndex: false
------------------

# 테스트용 성공 리다이렉트 페이지

[결제창 연동하기](/guides/payment/integration)에서 `requestPayment()`에 성공 리다이렉트 URL(`successUrl`)로 설정한 주소입니다.

현재 브라우저 주소창에서 **결제 키, 주문번호, 결제 금액**을 확인해보세요.

![성공 리다이렉트 페이지 예시](https://static.tosspayments.com/docs/window/successurl-example.png)

💡 이제 결제 요청 성공 리다이렉트 페이지를 만들고 실제 상점의 오리진을 포함한 `successUrl`을 설정하세요. 자세한 내용은 [결제 요청 결과 확인하기](/guides/payment/integration#2-결제-요청-결과-확인하기)를 참고하세요.

💡 이어서 [결제 승인을 진행](/guides/payment/integration/#3-결제-승인하기)하세요.
