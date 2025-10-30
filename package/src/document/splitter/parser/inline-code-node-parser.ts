import { InlineCodeNode, NodeParser, ParsedNode } from "../types.js";

export class InlineCodeNodeParser implements NodeParser {
  supportType = "inlineCode" as const;

  parse(node: InlineCodeNode): ParsedNode {
    return { value: `\`${node.value}\``, finished: false };
  }
}
