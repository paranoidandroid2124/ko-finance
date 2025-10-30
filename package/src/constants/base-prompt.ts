const PARAMETER = `## 파라미터 형식\n
{\n
  "keywords": string[]     // 질의에서 도출된 주요 키워드 (UTF-8 문자열 배열)\n
  "searchMode": "broad" | "balanced" | "precise" // 검색 모드 (기본값: "balanced")\n
  "maxTokens": number // 응답에 포함할 최대 토큰 수 (기본값: 25000, 최소: 500, 최대: 50000)\n
}\n\n

### 탐색 방법:\n
허용하는 토큰의 범위는 500에서 50000 사이입니다.\n 

\n\n
### searchMode 사용법:\n
• broad: "결제 관련해서 뭐가 있는지 둘러보고 싶어"\n
• balanced: "결제위젯 연동 방법을 알고 싶어"\n
• precise: "정확히 이 에러코드가 뭘 의미하는지 알고 싶어"\n
\n\n`;

export const BasePrompt = `유저의 질의를 분석하여 적절한 키워드와 카테고리를 추출 후 요청주세요.\n\n
${PARAMETER}
## 예제 모음\n

### case 1\n
User: 토스페이먼츠 결제위젯을 연동하고 싶어\n
Assistant: { "keywords": ["결제위젯", "연동"] }\n\n

### case 2\n
User: 토스에서 카드 승인 실패는 어떤 케이스가 있나요?\n
Assistant: { "keywords": ["카드", "승인", "실패"] }\n\n

### case 3\n
User: 비인증 결제가 뭐야?\n
Assistant: { "keywords": ["비인증 결제"] }\n\n

### case 4\n
User: SDK로 어떻게 연동하죠?\n
Assistant: { "keywords": ["sdk", "연동"] }\n\n

### case 5\n
User: 정책적으로 제한되는 부분이 있을까요?\n
Assistant: { "keywords": ["정책", "제한"] }\n\n
`;

export const BasePromptForV1 = `명시적으로 유저가 버전1을 질의하는 경우 사용해주세요.\n\n
유저의 질의를 분석하여 적절한 키워드를 추출 후 요청주세요. \n\n
${PARAMETER}

## 예제 모음

### case 1
User: 토스페이먼츠 결제위젯을 버전1으로 연동하고 싶어
Assistant: { "keywords": ["결제위젯", "연동"] }

### case 2
User: 토스페이먼츠 version1 sdk에서 오류가 나요
Assistant: { "keywords": ["sdk", "오류"] }

### case 3
User: 결제창 v1 에서 카드 결제는 어떻게 하나요?
Assistant: { "keywords": ["카드", "결제", "flow"] }
`;
