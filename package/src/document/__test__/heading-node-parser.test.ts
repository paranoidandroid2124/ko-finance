import { beforeEach, describe, expect, it } from "vitest";
import { HeadingNodeParser } from "../splitter/parser/heading-node-parser.js";
import { HeadingNode, NodeParserContext } from "../splitter/types.js";

describe("HeadingNodeParser", () => {
  let parser: HeadingNodeParser;
  let context: NodeParserContext;

  beforeEach(() => {
    parser = new HeadingNodeParser();
    context = {
      headingDepth: 3,
      headerStack: [],
    };
  });

  describe("기본 헤더 파싱", () => {
    it("간단한 헤더를 파싱한다", () => {
      const node: HeadingNode = {
        type: "heading",
        depth: 1,
        children: [{ type: "text", value: "결제 연동" }],
      };

      const result = parser.parse(node, context);

      expect(result.value).toBe("\n\n# 결제 연동\n");
      expect(result.finished).toBe(true);
      expect(context.headerStack).toEqual(["결제 연동"]);
    });

    it("빈 헤더를 처리한다", () => {
      const node: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [],
      };

      const result = parser.parse(node, context);

      expect(result.value).toBe("\n\n## \n");
      expect(result.finished).toBe(true);
      expect(context.headerStack).toEqual([undefined, ""]);
    });
  });

  describe("헤더 스택 관리", () => {
    it("계층적 헤더 구조를 올바르게 관리한다", () => {
      // H1: 결제 연동
      const h1: HeadingNode = {
        type: "heading",
        depth: 1,
        children: [{ type: "text", value: "결제 연동" }],
      };
      parser.parse(h1, context);
      expect(context.headerStack).toEqual(["결제 연동"]);

      // H2: 카드 결제
      const h2: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [{ type: "text", value: "카드 결제" }],
      };
      parser.parse(h2, context);
      expect(context.headerStack).toEqual(["결제 연동", "카드 결제"]);

      // H3: 인증 결제
      const h3: HeadingNode = {
        type: "heading",
        depth: 3,
        children: [{ type: "text", value: "인증 결제" }],
      };
      parser.parse(h3, context);
      expect(context.headerStack).toEqual([
        "결제 연동",
        "카드 결제",
        "인증 결제",
      ]);
    });

    it("깊은 헤더에서 얕은 헤더로 이동 시 스택을 정리한다", () => {
      // 초기 상태: H1 > H2 > H3
      context.headerStack = ["결제 연동", "카드 결제", "인증 결제"];

      // 새로운 H2가 나타나면 H3는 제거되어야 함
      const newH2: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [{ type: "text", value: "가상계좌 결제" }],
      };
      parser.parse(newH2, context);

      expect(context.headerStack).toEqual(["결제 연동", "가상계좌 결제"]);
    });

    it("H1에서 다른 H1으로 이동 시 스택을 리셋한다", () => {
      // 초기 상태: 복잡한 헤더 구조
      context.headerStack = ["결제 연동", "카드 결제", "인증 결제"];

      // 새로운 H1
      const newH1: HeadingNode = {
        type: "heading",
        depth: 1,
        children: [{ type: "text", value: "웹훅 연동" }],
      };
      parser.parse(newH1, context);

      expect(context.headerStack).toEqual(["웹훅 연동"]);
    });

    it("건너뛰는 헤더 레벨을 처리한다", () => {
      // H1 > H3 (H2 건너뜀)
      const h1: HeadingNode = {
        type: "heading",
        depth: 1,
        children: [{ type: "text", value: "결제 연동" }],
      };
      parser.parse(h1, context);

      const h3: HeadingNode = {
        type: "heading",
        depth: 3,
        children: [{ type: "text", value: "인증 결제" }],
      };
      parser.parse(h3, context);

      // H2 자리는 undefined, H3는 정상적으로 추가
      expect(context.headerStack).toEqual([
        "결제 연동",
        undefined,
        "인증 결제",
      ]);
    });
  });

  describe("headingDepth 제한", () => {
    it("headingDepth보다 깊은 헤더는 finished가 false다", () => {
      context.headingDepth = 2;

      const h3: HeadingNode = {
        type: "heading",
        depth: 3,
        children: [{ type: "text", value: "세부 내용" }],
      };

      const result = parser.parse(h3, context);

      expect(result.finished).toBe(false);
      expect(context.headerStack).toEqual([]); // 스택에 추가되지 않음
    });

    it("headingDepth와 같거나 얕은 헤더는 finished가 true다", () => {
      context.headingDepth = 3;

      const h2: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [{ type: "text", value: "섹션" }],
      };

      const result = parser.parse(h2, context);

      expect(result.finished).toBe(true);
      expect(context.headerStack).toEqual([undefined, "섹션"]);
    });
  });

  describe("복잡한 헤더 텍스트", () => {
    it("링크가 포함된 헤더를 처리한다", () => {
      const node: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [
          { type: "text", value: "결제 " },
          {
            type: "link",
            url: "https://example.com",
            children: [{ type: "text", value: "API" }],
          },
          { type: "text", value: " 가이드" },
        ],
      };

      const result = parser.parse(node, context);

      expect(result.value).toContain("## 결제 API 가이드");
      expect(context.headerStack[1]).toBe("결제 API 가이드");
    });

    it("인라인 코드가 포함된 헤더를 처리한다", () => {
      const node: HeadingNode = {
        type: "heading",
        depth: 2,
        children: [
          { type: "text", value: "Payment " },
          { type: "inlineCode", value: "객체" },
          { type: "text", value: " 사용법" },
        ],
      };

      const result = parser.parse(node, context);

      expect(result.value).toContain("## Payment 객체 사용법");
      expect(context.headerStack[1]).toBe("Payment 객체 사용법");
    });
  });
});
