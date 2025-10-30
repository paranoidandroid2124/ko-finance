***

title: 보안
description: 토스페이먼츠 API의 보안 정책과 방화벽 설정하는 방법을 안내합니다.
keyword: HTTPS, TLS, 포트, IP, 프락시
--------------------------------

# 보안

## 방화벽 설정

방화벽은 외부의 신뢰할 수 없는 네트워크가 내부 네트워크에 접근하지 못하도록 하는 보안 시스템입니다. 특정 포트나 IP에서 들어오는 요청을 필터링하거나, 사용자 인증 요청, 프락시, 주소변환기능(NAT) 등의 방법이 있습니다.

### 포트 번호를 허용하세요

#### 1. API 요청을 위한 443 포트

상점 서버에서 토스페이먼츠 서버에 요청을 보내려면 HTTPS로 접근할 수 있는 443 포트가 허용되어 있어야 합니다.

#### 2. 웹훅 URL 포트

결제 상태 변경, 지급대행 실행, 브랜드페이 고객 결제수단 업데이트와 같은 변경 사항을 받아볼 수 있는 [웹훅 이벤트를 등록하면](/guides/v2/webhook#2-웹훅-이벤트를-등록하세요) 토스페이먼츠 서버에서 상점 서버로 결제 처리에 필요한 데이터를 전송합니다. 방화벽 설정에서 웹훅 URL에 지정된 포트 번호로 인바운드 트래픽(Inbound Traffic)을 허용해주세요. IP는 아래 목록을 참고해주세요.

### IP 접근 제어 목록에 추가해주세요

상점 서버에서 IP [접근 제어 목록(ACL, Access Control List)](https://ko.wikipedia.org/wiki/%EC%A0%91%EA%B7%BC_%EC%A0%9C%EC%96%B4_%EB%AA%A9%EB%A1%9D)으로 트래픽을 분류해 허용하거나 거부하면, 토스페이먼츠의 IP 주소를 허용해주세요.

다음 IP에 접근할 수 있도록 허용해주면 정상적으로 인바운드 요청이 전송됩니다.

*   13.124.18.147
*   13.124.108.35
*   3.36.173.151
*   3.38.81.32
*   115.92.221.121\*
*   115.92.221.122\*
*   115.92.221.123\*
*   115.92.221.125\*
*   115.92.221.126\*
*   115.92.221.127\*

\* 2024년 12월에 추가된 신규 IP입니다.

### 브랜드페이 방화벽 설정

[브랜드페이](/guides/brandpay/overview)를 연동할 때 아래 리소스 주소를 방화벽 허용 목록(whitelist)에 추가해주세요. 브랜드페이 리소스를 불러오는 데 사용됩니다.

*   `https://api.tosspayments.com`
*   `https://event.tosspayments.com`
*   `https://static.toss.im`
*   `https://pages.tosspayments.com`
*   `https://polyfill-fe.toss.im`
*   `https://assets-fe.toss.im`

`https://api.tosspayments.com`는 IP가 2개로 특정됩니다. 아웃바운드 방화벽을 사용하고 있다면 다음 IP의 접근을 허용해주세요.

\- 103.182.251.2

\- 103.182.250.2

\- 210.98.141.21\*

\- 210.98.141.22\*

\* 2024년 12월에 추가된 신규 IP입니다.

## HTTP 프로토콜

### HTTPS만 사용합니다

토스페이먼츠 API는 HTTPS로 호출해야 합니다.

[HTTPS](/resources/glossary/http-protocol#http와-https의-차이점)는 HTTP의 보안(Secured) 버전입니다. HTTP로 주고받는 데이터는 암호화되지 않은 평문(plaintext)이기 때문에 개인 정보가 유출될 수 있습니다. 따라서 구매자의 결제 정보와 개인 정보를 보호하는 보안을 강화한 프로토콜인 HTTPS를 사용해야 합니다.

### TLS 버전 1.2 이상을 지원합니다

[TLS(전송 계층 보안)](/resources/glossary/tls)은 안전한 통신 프로토콜입니다. 토스페이먼츠 API는 TLS 버전 1.2 이상만 지원합니다.

TLS 1.2 미만의 SSL/TLS 버전은 보안이 취약하여 지원하지 않습니다. 상점 서버의 HTTP 클라이언트 환경이 TLS 1.2 이상을 지원하는지 확인해주세요.

### 보안에 취약한 Cipher Suite 는 지원되지 않습니다.

아래의 Cipher suite 또는 이보다 보안이 강한 알고리즘만 지원됩니다.

\* Cipher Suite(사이퍼 스위트): TLS/SSL 통신에서 키 교환·암호화·무결성 검사에 어떤 알고리즘을 조합해 쓸지 정해 놓은 세트입니다.

*   TLS\_AES\_128\_GCM\_SHA256
*   TLS\_AES\_256\_GCM\_SHA384
*   TLS\_CHACHA20\_POLY1305\_SHA256
*   ECDHE-ECDSA-AES128-GCM-SHA256
*   ECDHE-RSA-AES128-GCM-SHA256
*   ECDHE-ECDSA-AES128-SHA256
*   ECDHE-RSA-AES128-SHA256
*   ECDHE-ECDSA-AES256-GCM-SHA384
*   ECDHE-RSA-AES256-GCM-SHA384
*   ECDHE-ECDSA-AES256-SHA384
*   ECDHE-RSA-AES256-SHA384
