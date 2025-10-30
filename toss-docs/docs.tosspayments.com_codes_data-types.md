***

title: 데이터 타입
description: 토스페이먼츠 API/SDK에서 사용하는 데이터 타입을 설명합니다.
keyword: 데이터 유형, 데이터 형식, type, string, integer, number, boolean, array, object, 타입
----------------------------------------------------------------------------------

# 데이터 타입

토스페이먼츠의 API와 SDK는 [JSON Schema 사양](https://datatracker.ietf.org/doc/html/draft-wright-json-schema-00#section-4.2)을 기반으로 하는 [OAS(Open API Specification) 3.0](/resources/glossary/oas)의 기본 데이터 타입인 `string`, `number`, `integer`, `boolean`, `array`, `object`를 지원합니다.

## string

토스페이먼츠 API와 SDK에서는 일반 문자열과 `date-time` 형식을 포함합니다.

*   `string`: 일반적인 유니코드 문자열 데이터입니다.
*   `date-time`: [RFC 3339 - section 5.6](https://datatracker.ietf.org/doc/html/rfc3339#section-5.6)에 정의된 날짜-시간 데이터입니다. 토스페이먼츠 API/SDK에서는 `yyyy-MM-dd'T'HH:mm:ss` ISO 8601 형식을 사용합니다.

## integer

`int64` 형식으로 부호가 있는 62비트 정수입니다. -(263-1)부터 263-1까지의 값을 표현합니다.

토스페이먼츠 API/SDK에서는 금액 외의 숫자들을 표현할 때 사용합니다.

## number

`double` 형식으로 소수점을 표현할 수 있는 실수입니다. 1.7E-308부터 1.7E+308까지의 값을 표현합니다.

토스페이먼츠 API/SDK에서는 금액 정보를 표현할 때 사용합니다.

## boolean

논리형입니다. `true`, `false` 값으로 참/거짓을 표현합니다.

## array

배열 형식입니다. 순서가 있는 데이터의 집합을 표현합니다.

## object

객체 형식입니다. 순서가 없는 `key:value` 형식의 데이터 집합을 표현합니다.

***

문자열 데이터 타입의 [하위 포맷](https://swagger.io/docs/specification/data-models/data-types/#format)과 숫자 데이터 타입 `integer`와 `number`에서 지원하는 [하위 포맷](https://swagger.io/docs/specification/data-models/data-types/#numbers)은 토스페이먼츠에서 지원하는 타입만 소개합니다.
