import { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { isNativeError } from "node:util/types";

import { createTossPaymentDocsRepository } from "../repository/createTossPaymentDocsRepository.js";
import { GetDocumentParams } from "../schema/get-document-schema.js";

export const repository = await createTossPaymentDocsRepository();

/**
 * Toss Payment V1 문서 검색 도구
 */
export async function getV1DocumentsByKeyword(
  params: GetDocumentParams
): Promise<CallToolResult> {
  try {
    const { keywords, searchMode, maxTokens = 25000 } = params;

    const text = await repository.findV1DocumentsByKeyword(
      keywords,
      searchMode,
      maxTokens
    );

    return {
      content: [{ type: "text", text }],
    };
  } catch (e) {
    return {
      content: [
        {
          type: "text",
          text: isNativeError(e) ? e.message : "오류가 발생하였습니다.",
        },
      ],
      isError: true,
    };
  }
}

/**
 * Toss Payment V2 문서 검색 도구
 */
export async function getV2DocumentsByKeyword(
  params: GetDocumentParams
): Promise<CallToolResult> {
  try {
    const { keywords, searchMode, maxTokens = 25000 } = params;
    const text = await repository.findV2DocumentsByKeyword(
      keywords,
      searchMode,
      maxTokens
    );

    return {
      content: [{ type: "text", text }],
    };
  } catch (e) {
    return {
      content: [
        {
          type: "text",
          text: isNativeError(e) ? e.message : "오류가 발생하였습니다.",
        },
      ],
      isError: true,
    };
  }
}

/**
 * 문서 ID로 전체 내용 조회
 */
export async function getDocumentById(id: string): Promise<CallToolResult> {
  try {
    const numericId = parseInt(id, 10);

    if (isNaN(numericId)) {
      throw new Error("유효하지 않은 문서 ID입니다.");
    }

    const document = repository.findOneById(numericId);

    if (!document) {
      throw new Error("문서를 찾을 수 없습니다.");
    }

    const chunks = document.getChunks();

    const contents = chunks.map((chunk): { type: "text"; text: string } => ({
      type: "text",
      text: chunk.text,
    }));

    return {
      content: contents,
    };
  } catch (e) {
    return {
      content: [
        {
          type: "text",
          text: isNativeError(e) ? e.message : "오류가 발생하였습니다.",
        },
      ],
      isError: true,
    };
  }
}
