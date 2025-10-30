***

title: 요청·응답 본문
description: 토스페이먼츠 API 요청과 응답 본문을 알아봅니다.
keyword: 응답, 상태 코드, response, error, json, content-type, 인코딩, URL 인코딩, 요청 본문, payload, deleted-entity, list, -list, 리스트 객체, 목록 객체, 삭제 객체
----------------------------------------------------------------------------------------------------------------------------------------

# 요청·응답 본문

## 요청 본문

요청 본문은 클라이언트가 API를 요청할 때 보내는 데이터입니다. 토스페이먼츠 API에 요청할 때는 JSON 형식을 사용하세요.

### URL 인코딩

전체 요청 본문을 인코딩할 필요는 없습니다. 특수 문자가 요청 본문이나 [쿼리 파라미터](/resources/glossary/query-param) 값에 포함되어 있다면 URL 인코딩을 해야 합니다. 데이터를 안전하게 전송하고, 서버에서 정확하게 해석되도록 하는 중요한 단계입니다.

[URL 인코딩](https://developer.mozilla.org/ko/docs/Glossary/Percent-encoding)은 웹에서 안전하게 데이터를 전송하기 위해 특정 문자를 `%` 기호와 두 개의 16진수 숫자로 변환하는 과정입니다. 인코딩은 데이터가 전달되는 과정에서 오류나 변조 없이 완전하고 믿을 수 있는 상태로 유지해서 웹 서버가 요청을 정확하게 해석하도록 도와줍니다.

```plain theme="grey" copyable="false"
// 원본 데이터
name=John Doe&age=30

// 인코딩 후
name=John%20Doe&age=30
```

API 요청을 할 때 데이터 전송의 정확성과 안전성을 보장하려면 URL 인코딩을 하세요. 대부분의 프로그래밍 언어 및 플랫폼에서는 URL 인코딩을 위한 내장 함수나 라이브러리를 제공합니다. 사용하는 언어에 맞는 인코딩 방법을 참조하여 API 요청을 준비하세요.

## 응답 본문

응답 본문은 서버가 클라이언트에 보내는 데이터입니다. 토스페이먼츠 API의 성공 여부는 HTTP 상태 코드로 전달합니다. 돌아온 HTTP 상태 코드에 따라 요청이나 에러를 처리하는 로직을 구축하세요.

모든 API 응답, 요청 본문은 JSON 형식입니다. 따라서 응답 헤더에는 다음과 같이 [Content-Type](https://developer.mozilla.org/ko/docs/Web/HTTP/Headers/Content-Type)이 포함됩니다.

```plain theme="grey" copyable="false" feedbackable="false"
Content-Type: application/json
```

### 응답 HTTP 상태 코드

| HTTP 상태 코드            | 설명                                                                                                                                                                                                                                        |
| :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `200 - OK`                | 요청이 성공적으로 처리되었습니다.                                                                                                                                                                                                           |
| `400 - Bad Request`       | 요청을 처리할 수 없습니다. 필수 파라미터를 보내지 않았거나, 파라미터 포맷이 잘못되었을 때 돌아오는 응답입니다. 요청 파라미터를 확인해주세요.                                                                                                |
| `403 - Forbidden`         | 시크릿 키 없이 요청했거나 사용한 시크릿 키가 잘못되었습니다. [개발자센터](https://developers.tosspayments.com/my/api-keys)에서 내 상점의 키값을 다시 한번 확인하고, [시크릿 키](/reference/using-api/api-keys#시크릿-키) 문서를 참고하세요. |
| `404 - Not Found`         | 요청한 리소스가 존재하지 않습니다. 요청한 API 주소를 다시 한번 확인해보세요.                                                                                                                                                                |
| `429 - Too Many Requests` | 비정상적으로 많은 요청을 보냈습니다. 잠시 후 다시 시도해주세요.                                                                                                                                                                             |
| `500 - Server Error`      | 토스페이먼츠 서버에서 에러가 발생했습니다.                                                                                                                                                                                                  |

### 리소스 객체

토스페이먼츠 API v2는 리소스 중심으로 설계됐습니다. 어떤 API를 호출해도 일정하게 리소스 객체가 응답됩니다.

```plain theme="grey" copyable="false"
{
  "version": "2022-11-16",
  "traceId": "{traceId}",
  "entityType": "{entityType}",
  "entityBody": {
    // ...
  }
}
```



name: version
type: string


API 버전입니다. 토스페이먼츠의 [API 버전 정책](/reference/versioning) 및 [API 변경사항](/resources/release-note)을 확인해보세요.



name: traceId
type: string


토스페이먼츠에서 발급하는 API 요청의 고유 식별자입니다. 기술문의 시 `traceId`를 첨부하면 더 빠르게 답변을 받을 수 있습니다.



name: entityType
type: string


응답 객체 유형입니다.

\- 단건 객체가 응답되는 요청이라면 `payout`와 같이 객체 영문 이름이 소문자로 응답됩니다.

\- 객체 목록이 응답되는 요청이라면 `payout-list`와 같이 객체 이름 뒤에 [`-list`](#리스트-객체)가 붙습니다.

\- 객체가 삭제되는 요청이라면 [`deleted-entity`](#삭제된-객체)가 응답됩니다.



name: entityBody
type: string


응답 객체입니다. 단건 응답이라면 객체가 돌아옵니다. 목록 응답에는 pagination 정보와 응답 목록이 돌아옵니다.

#### 리스트 객체

리소스 목록을 조회하면 `entityType`에는 객체 이름 뒤에 `-list`가 붙고 아래 예시와 같은 객체가 돌아옵니다. `entityBody`에는 `hastNext`, `lastCursor`와 같은 pagination 정보와 `items` 필드에 객체 목록이 돌아옵니다.

```plain theme="grey"
{
  "version": "2022-11-16",
  "traceId": "{traceId}",
  "entityType": "{entityType}-list",
  "entityBody": {
    "hasNext": false,
    "lastCursor": 213805090,
    "items": [ {...}, {...} ]
  }
}
```

#### 삭제된 객체

리소스가 삭제되면 아래와 같이 `deleted-entity` 리소스 삭제 객체가 돌아옵니다. `entityBody`에는 삭제된 객체의 `id` 및 `ref*Id`가 돌아옵니다. `id`는 토스페이먼츠에서 발급한 리소스 식별자입니다. `ref*Id`는 내 상점에서 직접 발급한 리소스 식별자입니다.

```plain theme="grey" copyable="false"
{
  "version": "2022-11-16",
  "traceId": "{traceId}",
  "entityType": "deleted-entity",
  "entityBody": {
    "id": "{id}",
    "ref*Id": "{ref*id}" // nullable
  }
}
```

### 에러 객체

요청이 정상적으로 처리되지 않으면 응답으로 HTTP 상태 코드와 함께 아래와 같은 에러 객체가 돌아옵니다.
API 별 에러 코드와 메시지는 [에러 코드](/reference/error-codes#코어-api-별-에러) 페이지에서 살펴보세요.

#### API v1 에러 객체

```plain theme="grey" copyable="false" feedbackable="false"
{
  "code": "NOT_FOUND_PAYMENT",
  "message": "존재하지 않는 결제 입니다."
}
```



name: code
type: string


에러 코드입니다.



name: message
type: string


에러 메시지입니다.

#### API v2 에러 객체

```plain theme="grey"
{
  "version": "2022-11-16",
  "traceId": "{traceId}",
  "error": {
    "code": "{CODE}",
    "message": "{MESSAGE}",
  }
}
```



name: version
type: string


API 버전입니다. 토스페이먼츠의 [API 버전 정책](/reference/versioning) 및 [API 변경사항](/resources/release-note)을 확인해보세요.



name: traceId
type: string


토스페이먼츠에서 발급하는 API 요청의 고유 식별자입니다. 기술문의 시 `traceId`를 첨부하면 더 빠르게 답변을 받을 수 있습니다.



name: error
type: string


에러 객체입니다.



name: code
type: string


에러 코드입니다.



name: message
type: string


에러 메시지입니다.

### 유의사항

**API 응답이나 웹훅 이벤트 본문에 새로운 필드가 추가와 같이 [하위 호환을 지원하는 변경 사항](/reference/versioning#하위-호환을-지원하는-변경-사항)은 버전 릴리즈 없이 기존 API에 반영됩니다.** 클라이언트 코드는 이러한 변경에 유연하게 대응할 수 있도록 작성해 주세요. 추가된 새로운 필드를 무시하거나 기본값을 설정하는 방식으로 JSON 파싱 로직을 구성해 주세요.

예를 들어 Java에서는 `ObjectMapper`를 사용해서 JSON 응답을 처리할 때 `.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)` 옵션을 설정하면 새로운 필드가 추가되어도 오류가 발생하지 않을 수 있습니다.
