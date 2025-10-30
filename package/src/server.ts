import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { BasePrompt, BasePromptForV1 } from "./constants/base-prompt.js";
import { GetDocumentSchema } from "./schema/get-document-schema.js";
import {
  getDocumentById,
  getV1DocumentsByKeyword,
  getV2DocumentsByKeyword,
} from "./tool/tools.js";

const server = new McpServer({
  name: "tosspayments-integration-guide",
  description:
    "MCP-compatible toolset for integrating with tosspayments systems. Includes tools for retrieving LLM-structured text and fetching actual documentation through URLs. (토스페이먼츠 시스템과의 연동을 위한 MCP 도구 모음입니다. LLM이 활용할 수 있는 텍스트 및 관련 문서를 가져오는 기능을 포함합니다.)",
  version: "1.0.0",
});

server.tool(
  "get-v2-documents",
  `토스페이먼츠 v2 문서들을 조회합니다. 명시적으로 유저가 버전에 관련된 질의가 없다면 사용해주세요.
${BasePrompt}`,
  GetDocumentSchema,
  async (params) => {
    return await getV2DocumentsByKeyword(params);
  }
);

server.tool(
  "get-v1-documents",
  `토스페이먼츠 v1 문서들을 조회합니다. 명시적으로 유저가 버전1을 질의하는 경우 사용해주세요.
${BasePromptForV1}`,
  GetDocumentSchema,
  async (params) => {
    return await getV1DocumentsByKeyword(params);
  }
);

server.tool(
  "document-by-id",
  `문서의 원본 ID 로 해당 문서의 전체 내용을 조회합니다.`,
  { id: z.string().describe("문서별 id 값") },
  async ({ id }) => {
    return await getDocumentById(id);
  }
);

const transport = new StdioServerTransport();

await server.connect(transport);
