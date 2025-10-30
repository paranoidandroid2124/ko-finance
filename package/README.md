# @tosspayments/integration-guide-mcp

토스페이먼츠 연동 가이드 MCP 서버

## 소개

`@tosspayments/integration-guide-mcp`는 토스페이먼츠 시스템과의 연동을 위한 표준 입출력 기반 MCP(Model Context Protocol) 서버입니다.
이 서버는 LLM(대형 언어 모델)이 토스페이먼츠 공식 문서에서 키워드 기반으로 관련 정보를 탐색하고, 문서를 검색·조회할 수 있도록 다양한 MCP 도구를 제공합니다.

[기술 블로그 바로가기](https://toss.tech/article/tosspayments-mcp)

[Payments 개발자센터](https://docs.tosspayments.com/guides/v2/get-started)

[LLMs 로 결제 연동하기](https://docs.tosspayments.com/guides/v2/get-started/llms-guide)

## 설치

이 패키지는 Node.js 22 환경에서 동작합니다.

아래와 같이 설정하여 설치할 수 있습니다.

```json
{
  "mcpServers": {
    "tosspayments-integration-guide": {
      "command": "npx",
      "args": ["-y", "@tosspayments/integration-guide-mcp@latest"]
    }
  }
}
```

## 도구 목록

### `get-v2-documents`

- **설명**: 토스페이먼츠 v2 문서를 조회합니다. 유저가 버전을 명시하지 않은 경우 사용하세요.
- **파라미터**:
  - `keywords: string[]` — 검색할 키워드(UTF-8 문자열 배열)

### `get-v1-documents`

- **설명**: 토스페이먼츠 v1 문서를 조회합니다. 유저가 버전 1을 명시적으로 질의한 경우 사용하세요.
- **파라미터**:
  - `keywords: string[]` — 검색할 키워드(UTF-8 문자열 배열)

### `document-by-id`

- **설명**: 문서의 고유 ID로 전체 내용을 조회합니다.
- **파라미터**:
  - `id: string` — 문서의 고유 ID
