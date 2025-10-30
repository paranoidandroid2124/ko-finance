import { describe, expect, it } from "vitest";
import { parseLLMText } from "../parseLLMText.js";
import * as fs from "node:fs";
import path from "node:path";

describe("parseLLMText", () => {
  it("정상적으로 파싱한다", async () => {
    const data = fs.readFileSync(
      path.join(__dirname, "data", "test_llms.txt"),
      "utf-8"
    );

    const parsed = parseLLMText(data);

    expect(parsed.length).toBeGreaterThan(0);
  });
});
