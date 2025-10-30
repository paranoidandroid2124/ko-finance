import * as fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { MarkdownSplitter } from "../splitter/markdown-splitter.js";

describe("MarkdownSplitter", () => {
  it("정상적으로 파싱한다2", async () => {
    const data = fs.readFileSync(
      path.join(__dirname, "data", "core-api.md"),
      "utf-8"
    );

    const parsed = MarkdownSplitter.create(data).split();

    expect(parsed.metadata).toMatchInlineSnapshot(`
      {
        "description": "토스페이먼츠 API 엔드포인트(Endpoint)와 객체 정보, 파라미터, 요청 및 응답 예제를 살펴보세요.",
        "keyword": [],
        "title": "코어 API",
      }
    `);

    expect(parsed.enhancedChunks).toMatchSnapshot();
    expect(parsed.enhancedChunks.length).toBeGreaterThan(0);
  });

  it("정상적으로 파싱한다", async () => {
    const data = fs.readFileSync(
      path.join(__dirname, "data", "test.md"),
      "utf-8"
    );

    const parsed = MarkdownSplitter.create(data).split();

    expect(parsed.metadata).toMatchInlineSnapshot(`
      {
        "description": "카드 결제는 인증, 승인, 매입 순으로 이루어집니다. 각 단계에서 일어나는 일을 카드사, PG사, 고객 관점에서 알아볼게요.",
        "keyword": [
          "인증",
          "승인",
          "매입",
          "인증 결제",
          "비인증 결제",
          "추가 인증",
          "환금성 결제",
          "수동 매입",
        ],
        "title": "카드 결제",
      }
    `);

    expect(parsed.enhancedChunks.length).toBeGreaterThan(0);
  });

  it("SDK 마크다운을 정상적으로 파싱한다", async () => {
    const data = fs.readFileSync(
      path.join(__dirname, "data", "sdk.md"),
      "utf-8"
    );

    const parsed = MarkdownSplitter.create(data).split();

    expect(parsed.metadata).toMatchInlineSnapshot(`
      {
        "description": "토스페이먼츠 JavaScript SDK를 추가하고 메서드를 사용하는 방법을 알아봅니다.",
        "keyword": [
          "SDK",
          "JavaScript",
          "렌더링",
          "위젯",
          "메서드",
        ],
        "title": "토스페이먼츠 JavaScript SDK",
      }
    `);
    expect(parsed.enhancedChunks).toMatchSnapshot();
    expect(parsed.enhancedChunks.length).toBeGreaterThan(0);
  });
});
