import { ListItemNode, NodeParser, ParsedNode } from "../types.js";
import { extractTextFromNode } from "../extractTextFromNode.js";

export class ListItemNodeParser implements NodeParser {
  supportType = "listItem" as const;

  parse(node: ListItemNode): ParsedNode {
    // 리스트 아이템 처리 (기존 processListItemNode 로직 개선)
    const itemText = extractTextFromNode(node);

    return {
      value: `\n\n* ${itemText}\n`,
      finished: false,
    };
  }
}
