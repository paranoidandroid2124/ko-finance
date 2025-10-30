import { LinkNode, NodeParser, ParsedNode } from "../types.js";
import { extractTextFromNode } from "../extractTextFromNode.js";

export class LinkNodeParser implements NodeParser {
  supportType = "link" as const;

  parse(node: LinkNode): ParsedNode {
    const linkText = extractTextFromNode(node);
    const value = linkText ? `[${linkText}](${node.url})` : "";
    
    return {
      value,
      finished: false,
    };
  }
}
