import { CodeNode, NodeParser, ParsedNode } from "../types.js";

export class CodeNodeParser implements NodeParser {
  supportType = "code" as const;

  parse(node: CodeNode): ParsedNode {
    return {
      value: `\n\`\`\`${node.lang || ""}\n${node.value}\n\`\`\`\n`,
      finished: false,
    };
  }
}
