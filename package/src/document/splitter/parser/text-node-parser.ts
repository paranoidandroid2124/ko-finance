import { TextNode, NodeParser, ParsedNode } from "../types.js";

export class TextNodeParser implements NodeParser {
  supportType = "text" as const;

  parse(node: TextNode): ParsedNode {
    const text = node.value.trim();
    return {
      value: text,
      finished: false,
    };
  }
}