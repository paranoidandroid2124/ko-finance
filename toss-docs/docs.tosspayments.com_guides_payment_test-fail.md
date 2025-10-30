***

title: 테스트용 실패 리다이렉트 페이지
description: 결제창 연동 가이드 테스트용 실패 리다이렉트 페이지입니다.
keyword: failUrl, 실패 리다이렉트, 리다이렉트, 테스트
searchIndex: false
------------------

# 테스트용 실패 리다이렉트 페이지

[결제창 연동하기](/guides/payment/integration) 예제 코드에서 `requestPayment()`에 실패 리다이렉트 URL(`failUrl`)로 설정한 주소입니다.

현재 브라우저 주소창에서 **에러 코드, 메시지, 주문번호**를 확인해보세요.

![실패 리다이렉트 페이지 예시](https://static.tosspayments.com/docs/window/failurl-example.png)

💡 이제 결제 요청 실패 리다이렉트 페이지를 만들고 실제 상점의 오리진을 포함한 `failUrl`을 설정하세요. 자세한 내용은 [결제 요청 실패 처리](/sdk/payment-js#실패했을-때)를 참고하세요.

💡 브라우저에서 [`failUrl`로 전달되는 에러 목록](/sdk/v2/error-codes#failurl로-전달되는-에러)을 확인하고 문제를 해결하세요.
