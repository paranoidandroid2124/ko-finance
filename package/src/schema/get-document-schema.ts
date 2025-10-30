import { z } from "zod";
import { SearchMode } from "../constants/search-mode.js";

export const GetDocumentSchema = {
  keywords: z
    .array(z.string())
    .describe(
      "검색할 키워드 배열. 예: ['결제위젯', '연동'] - 관련성이 높은 문서를 찾기 위한 핵심 단어들"
    ),
  searchMode: z
    .nativeEnum(SearchMode)
    .default(SearchMode.BALANCED)
    .describe(
      `
      검색 모드에 따라 결과의 관련성과 정확도가 달라집니다.
      
      검색 모드:
      - broad: 폭넓은 결과 (관련성 낮아도 포함, 개념 탐색 시)
      - balanced: 균형잡힌 결과 (일반적인 검색)  
      - precise: 정확한 결과만 (정확한 답변 필요 시)
    `
    )
    .optional(),
  maxTokens: z
    .number()
    .int()
    .min(500)
    .max(50000)
    .default(25000)
    .describe(
      `
      응답에 포함할 최대 토큰 수입니다. 허용가능한 토큰 숫자는 500에서 50000 사이입니다. 
      
      권장값:
      - 1000: 간단한 답변 (빠른 응답)
      - 10000: 균형잡힌 상세도 
      - 25000: 매우 상세한 분석 (기본값)
      - 50000: 최대 상세도 (긴 문서나 복잡한 내용) 단, 허용가능한 토큰의 크기를 초과할 수 있으므로 주의가 필요합니다.
    `
    )
    .optional(),
};

export type GetDocumentParams = {
  keywords: string[];
  searchMode?: SearchMode;
  maxTokens?: number;
};
