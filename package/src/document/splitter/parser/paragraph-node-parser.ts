import { ParagraphNode, NodeParser, ParsedNode } from "../types.js";

export class ParagraphNodeParser implements NodeParser {
  supportType = "paragraph" as const;

  parse(node: ParagraphNode): ParsedNode {
    // 단락 끝에 줄바꿈 추가 (기존 processParagraphNode 로직)
    return {
      value: "\n", // 빈 줄 추가로 단락 구분
      finished: false,
    };
  }
}
