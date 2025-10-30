***

title: 웹훅(Webhook) 연결하기
description: 토스페이먼츠 결제, 브랜드페이, 지급대행 상태에 변경사항이 있을 때 웹훅으로 실시간 업데이트를 받아보세요.
keyword: 가상계좌 입금 알림, 웹훅, 콜백, 웹훅 이벤트, 알림, Webhook, PAYMENT\_STATUS\_CHANGED, DEPOSIT\_CALLBACK, PAYOUT\_STATUS\_CHANGED, METHOD\_UPDATED, CUSTOMER\_STATUS\_CHANGED, 입금 알림, 상태 변경, 입금 확인, 가상계좌 테스트, 입금 테스트, 입금 확인, 입금 기한 만료, 결제 만료, 결제 취소, 결제수단 변경, 회원 탈퇴
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

**Version 2**

새로 나온

# 웹훅(Webhook) 연결하기

토스페이먼츠 결제, 브랜드페이, 지급대행 상태에 변경사항이 있을 때 웹훅으로 실시간 업데이트를 받아보세요. [웹훅](/resources/glossary/webhook)이란 데이터가 변경되었을 때 실시간으로 알림을 받을 수 있는 기능이에요.

## 1. 웹훅 이벤트 타입을 알아보세요

웹훅으로 등록할 수 있는 이벤트 타입은 아래와 같습니다. 웹훅 본문과 자세한 설명은 각 이벤트 타입을 선택해서 살펴보세요.

| 이벤트 타입                                                                              | 설명                                                                            |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [`PAYMENT_STATUS_CHANGED`](/reference/using-api/webhook-events#payment_status_changed)   | 결제 상태 변경 이벤트입니다. 모든 결제수단에 사용 가능합니다.                   |
| [`DEPOSIT_CALLBACK`](/reference/using-api/webhook-events#deposit_callback)               | [가상계좌](/resources/glossary/virtual-account) 입금 및 입금 취소 이벤트입니다. |
| [`CANCEL_STATUS_CHANGED`](/reference/using-api/webhook-events#cancel_status_changed)     | 결제 취소 상태입니다.                                                           |
| [`METHOD_UPDATED`](/reference/using-api/webhook-events#method_updated)                   | 브랜드페이 고객 결제수단 변경 이벤트입니다.                                     |
| [`CUSTOMER_STATUS_CHANGED`](/reference/using-api/webhook-events#customer_status_changed) | 브랜드페이 고객 상태 변경 이벤트입니다.                                         |
| [`payout.changed`](/reference/using-api/webhook-events#payoutchanged)                    | 지급대행 상태 변경 이벤트입니다.                                                |
| [`seller.changed`](/reference/using-api/webhook-events#sellerchanged)                    | 셀러 상태 변경 이벤트입니다.                                                    |
| [`BILLING_DELETED`](/reference/using-api/webhook-events#billing_deleted)                 | 빌링키 삭제 이벤트입니다.                                                       |

## 2. 웹훅 이벤트를 등록하세요

[개발자센터의 웹훅 메뉴](https://developers.tosspayments.com/my/webhooks)에서 **웹훅 등록하기**를 누르면 아래와 같이 웹훅 이벤트 등록 팝업창이 열립니다. 웹훅 이름, 웹훅 URL을 입력하고 등록할 이벤트를 선택하세요. 마지막으로 **'등록하기'** 를 누르면 웹훅이 등록됩니다.

웹훅 목록에서 잘 등록되었는지 확인하세요. 결제 상태가 변경되어 등록한 이벤트가 발생하면 웹훅 URL로 웹훅 이벤트가 전송됩니다. 웹훅은 상세 페이지에서 삭제할 수 있습니다.

웹훅은 상점아이디(MID)별로 설정할 수 있고, 각 상점아이디에 따로 전송됩니다.

![개발자센터 웹훅 설정 페이지](https://static.tosspayments.com/docs/guides/learn/웹훅%20연결하기-1.png)



title: 로컬 환경에서 웹훅을 받을 수 있나요?


웹훅 URL은 온라인에서 접근할 수 있는 주소를 등록해야 합니다. 로컬 개발 환경은 외부에서 접근할 수 없기 때문에 로컬 서버 포트가 포함된 URL은 웹훅으로 등록할 수 없습니다.

혹은 로컬 개발 환경에 접근할 수 있도록 도와주는 도구를 사용해서 테스트할 수 있습니다.

[ngrok](https://ngrok.com)을 사용하면 로컬에서 실행된 서버를 외부에서 안전하게 접근할 수 있습니다. 내 로컬 서버 포트에 접근할 수 있는 URL을 만들고 아래와 같이 웹훅을 테스트해보세요.

![ngrok 예제 이미지](https://static.tosspayments.com/docs/webhook/ngrok예제.png)

1.  [ngrok을 다운로드](https://ngrok.com/download)하세요.
2.  터미널에서 `ngrok http 8080`와 같이 내가 사용할 로컬 서버 포트 번호를 커맨드에 추가해 실행하세요.
3.  서버 코드에 웹훅 엔드포인트를 추가하고 원하는 로직을 작성하세요.
4.  ngrok 콘솔을 실행했다면 `localhost:8080`로 포워딩할 수 있도록 생성된 URL(Forwarding)를 [개발자센터 웹훅 페이지](https://developers.tosspayments.com/my/webhooks)에 등록하세요. 3단계에서 만든 웹훅 엔드포인트를 ngrok으로 생성한 URL 뒤에 추가해서 등록해야 합니다.
5.  테스트 결제를 해보세요. 등록한 URL로 웹훅이 발송됩니다. [ngrok 인스펙터](https://ngrok.com/docs/secure-tunnels/ngrok-agent/web-inspection-interface)(Web Interface)에서 아래와 같이 이벤트 데이터가 들어온 것을 확인할 수 있습니다.

![ngrok 인스펙터 예제 이미지](https://static.tosspayments.com/docs/webhook/ngrok_web_inspector.png)



title: 이벤트는 어떤 형식인가요?


이벤트는 HTTP POST 메서드로 전달되는 JSON 파일입니다. 서버에서 JSON을 처리할 수 있는지 확인해주세요. HTTP도 지원하지만 보안이 강화된 HTTPS 통신을 권장합니다.

## 3. 웹훅 전송 기록을 확인하세요

[개발자센터 웹훅 목록](https://developers.tosspayments.com/my/webhooks)에서 등록한 웹훅을 선택하면 웹훅 상세 정보와 전송 기록을 확인할 수 있습니다.

웹훅 전송 기록은 등록한 이벤트의 가장 최근 전송 상태를 보여줍니다. 즉, 하나의 전송 기록은 이벤트가 발생한 뒤의 상태 변화를 표현합니다. 이벤트 발생 시간을 선택하면 해당 이벤트의 본문을 볼 수 있습니다.

전송 상태는 '전송 중', '성공', '실패' 중 하나입니다.

![웹훅 전송 기록 예제 이미지](https://static.tosspayments.com/docs/guides/learn/웹훅%20연결하기-2.png)

## 4. 웹훅 재전송 정책을 확인하세요

웹훅을 잘 받았다면 10 초 이내로 200 응답을 보내주세요. 200 응답을 보내면 웹훅 상태가 '성공'입니다. 200 응답을 보내지 않고 최초의 웹훅 전송이 실패하면 최대 7회(최초 전송으로부터 3일 19시간 후)까지 웹훅을 재전송합니다. 웹훅 전송이 실패하면 이메일로 실패 내역이 전송됩니다.

1회부터 6회까지 웹훅 전송이 실패해도 웹훅 상태는 '전송 중'입니다. 7회 웹훅 전송이 실패하면 웹훅 상태가 '실패'로 변경됩니다.

![웹훅 재전송](https://static.tosspayments.com/docs/webhook/webhook-status.png)

| 재전송 횟수 | 재전송 간격(분) |
| ----------- | --------------- |
| 1           | 1               |
| 2           | 4               |
| 3           | 16              |
| 4           | 64              |
| 5           | 256             |
| 6           | 1024            |
| 7           | 4096            |

'전송 중'일 때 \*\*'다시 시도'\*\*를 누르면 진행 중이던 재전송 시도는 무효화되고 새로운 1회 요청이 시도됩니다. 웹훅 전송이 계속 실패한다면 등록한 웹훅 URL의 포트 번호에 [방화벽 설정](https://docs.tosspayments.com/reference/using-api/security)이 허용되어 있는지 확인해보세요. 7회 전송까지 실패하면 이메일로 이벤트 정보를 알려드립니다.
