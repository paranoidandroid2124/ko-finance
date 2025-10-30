import remarkParse from "remark-parse";
import { unified } from "unified";
import { visit } from "unist-util-visit";
import { TokenEstimator } from "../token-estimator.js";
import { DocumentMetadata } from "../types.js";
import { extractMetadata } from "./extractMetadata.js";
import { MarkdownTableBuilder } from "./markdown-table.builder.js";
import { CodeNodeParser } from "./parser/code-node-parser.js";
import { HeadingNodeParser } from "./parser/heading-node-parser.js";
import { InlineCodeNodeParser } from "./parser/inline-code-node-parser.js";
import { ParagraphNodeParser } from "./parser/paragraph-node-parser.js";
import { TextNodeParser } from "./parser/text-node-parser.js";
import {
  BaseNode,
  EnhancedChunk,
  NodeParser,
  NodeParserContext,
  NodeType,
  TableNodes,
} from "./types.js";

export class MarkdownSplitter {
  private readonly chunks: EnhancedChunk[] = [];
  private readonly buffer: string[] = [];

  private readonly context: NodeParserContext = {
    headingDepth: 4,
    headerStack: [],
  };

  private tableBuilder: MarkdownTableBuilder | null = null;

  constructor(
    private readonly markdown: string,
    private readonly metadata: DocumentMetadata,
    private readonly parsers: Map<NodeType, NodeParser>
  ) {
    this.context.headerStack.push(this.metadata.title);
  }

  static create(markdown: string) {
    const metadata = extractMetadata(markdown);

    const index = markdown.indexOf("-----");

    if (metadata.title !== "No Title" && index !== -1) {
      markdown = markdown.substring(index);
    }

    return new MarkdownSplitter(
      markdown,
      metadata,
      new Map(parsers.map((parser) => [parser.supportType, parser]))
    );
  }

  split() {
    const { parsers } = this;

    const tree = unified().use(remarkParse).parse(this.markdown);

    visit(tree, (node) => {
      if (this.isTableNodes(node)) {
        this.parseTableNodes(node);
        return;
      }

      // tableBuilder 가 있지만 tableNode 가 아닌 경우
      if (this.tableBuilder) {
        this.clearTableBuilder();
      }

      const parser = parsers.get(node.type);

      if (!parser) {
        return;
      }

      const { value, finished } = parser.parse(node, this.context);

      if (finished) {
        this.flush();
      }

      this.append(value);
    });

    // visit 완료 후 남은 테이블 처리
    if (this.tableBuilder) {
      this.clearTableBuilder();
    }

    if (this.buffer.length > 0) {
      this.flush();
    }

    const additionalMetadata = this.chunks.find(
      (chunk) => !chunk.content.startsWith("#")
    );

    return {
      markdown: this.markdown,
      enhancedChunks: this.chunks, // 새로운 필드 추가
      metadata: this.metadata,
      additionalMetadata: additionalMetadata?.content,
    };
  }

  private append(value: string) {
    this.buffer.push(value);
  }

  private parseTableNodes(node: TableNodes) {
    if (node.type === "table") {
      if (this.tableBuilder) {
        this.clearTableBuilder();
      }

      this.tableBuilder = new MarkdownTableBuilder();
    }

    if (node.type === "tableRow") {
      this.tableBuilder?.addRow();
    }

    if (node.type === "tableCell") {
      this.tableBuilder?.addColumn(node);
    }
  }

  private clearTableBuilder() {
    if (this.tableBuilder) {
      const tableText = this.tableBuilder.build();
      this.append(`\n${tableText}\n`);
      this.tableBuilder = null;
    }
  }

  private isTableNodes(node: BaseNode): node is TableNodes {
    return (
      node.type === "table" ||
      node.type === "tableCell" ||
      node.type === "tableRow"
    );
  }

  private flush() {
    const content = this.buffer.join(" ").trim();
    if (!content) return;

    // 현재 헤더 스택 복사 (참조가 아닌 값 복사)
    const currentHeaderStack = [...this.context.headerStack];

    // 토큰 수 사전 계산
    const estimatedTokens = TokenEstimator.estimate(content);

    const enhancedChunk: EnhancedChunk = {
      content,
      headerStack: currentHeaderStack,
      estimatedTokens,
    };

    this.chunks.push(enhancedChunk);
    this.buffer.length = 0;

    // 헤더 스택은 HeadingNodeParser에서 관리하므로 여기서는 pop하지 않음
  }
}

const parsers = [
  new HeadingNodeParser(),
  new InlineCodeNodeParser(),
  new CodeNodeParser(),
  new TextNodeParser(),
  new ParagraphNodeParser(),
];
