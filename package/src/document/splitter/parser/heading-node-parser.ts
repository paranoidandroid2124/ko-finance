import { extractTextFromNode } from "../extractTextFromNode.js";
import {
  HeadingNode,
  NodeParser,
  NodeParserContext,
  ParsedNode,
} from "../types.js";

/**
 * 계층적 헤더 스택 관리를 지원하는 개선된 헤딩 노드 파서
 * 마크다운 헤딩의 계층구조를 정확히 추적하고 관리합니다.
 */
export class HeadingNodeParser implements NodeParser {
  supportType = "heading" as const;

  parse(node: HeadingNode, context: NodeParserContext): ParsedNode {
    const cleanHeaderText = this.extractCleanHeaderText(node);
    const markdownValue = this.formatMarkdownHeader(node, cleanHeaderText);

    const finished = node.depth <= context.headingDepth;

    if (finished) {
      // 계층구조를 고려한 헤더 스택 업데이트
      this.updateHeaderStack(context, node.depth, cleanHeaderText);
    }

    return { value: markdownValue, finished };
  }

  /**
   * 마크다운 형식 제거한 순수 헤더 텍스트 추출
   * @param node 헤딩 노드
   * @returns 클린한 헤더 텍스트
   */
  private extractCleanHeaderText(node: HeadingNode): string {
    if (node.children && node.children.length > 0) {
      return extractTextFromNode(node).trim();
    }
    return "";
  }

  /**
   * 마크다운 형식으로 헤더 포맷팅
   * @param node 헤딩 노드
   * @param text 헤더 텍스트
   * @returns 포맷된 마크다운 헤더
   */
  private formatMarkdownHeader(node: HeadingNode, text: string): string {
    const headingPrefix = "#".repeat(node.depth);
    return text ? `\n\n${headingPrefix} ${text}\n` : `\n\n${headingPrefix} \n`;
  }

  /**
   * 계층구조를 고려한 헤더 스택 업데이트
   * 현재 depth보다 깊은 레벨의 헤더들을 제거하고 새 헤더 추가
   * @param context 파서 컨텍스트
   * @param depth 현재 헤더의 depth
   * @param headerText 클린한 헤더 텍스트
   */
  private updateHeaderStack(
    context: NodeParserContext,
    depth: number,
    headerText: string
  ): void {
    // 현재 depth보다 깊은 헤더들 제거
    // 예: depth 2인 헤더가 나오면 depth 2, 3, 4... 의 기존 헤더들 모두 제거
    while (context.headerStack.length >= depth) {
      context.headerStack.pop();
    }

    // 새 헤더를 적절한 위치에 추가
    // headerStack[0] = depth 1, headerStack[1] = depth 2, ...
    context.headerStack[depth - 1] = headerText;

    // depth보다 뒤의 undefined 요소들 제거
    context.headerStack.length = depth;
  }
}
