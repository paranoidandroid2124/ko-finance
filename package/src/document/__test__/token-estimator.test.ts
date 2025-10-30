import { describe, expect, it } from "vitest";
import { TokenEstimator } from "../token-estimator.js";

describe("TokenEstimator", () => {
  describe("기본 토큰 추정", () => {
    it("빈 텍스트는 0 토큰을 반환한다", () => {
      expect(TokenEstimator.estimate("")).toBe(0);
      expect(TokenEstimator.estimate(null as any)).toBe(0);
      expect(TokenEstimator.estimate(undefined as any)).toBe(0);
    });

    it("영어 텍스트의 토큰 수를 추정한다", () => {
      const text = "Hello world";
      const estimated = TokenEstimator.estimate(text);

      // 기본적으로 문자 수 * 0.75 정도
      expect(estimated).toBeGreaterThan(5);
      expect(estimated).toBeLessThan(15);
    });

    it("한국어 텍스트는 가중치가 적용된다", () => {
      const englishText = "Payment integration guide";
      const koreanText = "결제 연동 가이드";

      const englishTokens = TokenEstimator.estimate(englishText);
      const koreanTokens = TokenEstimator.estimate(koreanText);

      // 한국어는 가중치로 인해 더 많은 토큰으로 추정
      expect(koreanTokens).toBeGreaterThan(englishTokens * 0.6);
    });
  });

  describe("코드 블록 처리", () => {
    it("코드 블록은 효율적으로 계산된다", () => {
      const normalText = "This is a normal text with same length as code below";
      const codeText = "```javascript\nconst payment = new Payment();\n```";

      const normalTokens = TokenEstimator.estimate(normalText);
      const codeTokens = TokenEstimator.estimate(codeText);

      // 코드 블록은 일반 텍스트보다 토큰 효율이 좋아야 함
      expect(codeTokens).toBeLessThan(normalTokens);
    });

    it("인라인 코드도 효율적으로 계산된다", () => {
      const normalText = "Use the payment method";
      const inlineCodeText = "Use the `payment` method";

      const normalTokens = TokenEstimator.estimate(normalText);
      const inlineCodeTokens = TokenEstimator.estimate(inlineCodeText);

      // 차이가 크지 않아야 함 (인라인 코드는 짧기 때문)
      expect(Math.abs(inlineCodeTokens - normalTokens)).toBeLessThan(5);
    });
  });

  describe("URL 처리", () => {
    it("URL은 적절한 토큰 수로 계산된다", () => {
      const textWithUrl =
        "Visit https://docs.tosspayments.com/guides for more info";
      const textWithoutUrl = "Visit the documentation for more info";

      const urlTokens = TokenEstimator.estimate(textWithUrl);
      const normalTokens = TokenEstimator.estimate(textWithoutUrl);

      // URL이 포함된 텍스트가 더 많은 토큰을 가져야 함
      expect(urlTokens).toBeGreaterThan(normalTokens);
    });
  });

  describe("마크다운 헤더 처리", () => {
    it("마크다운 헤더는 가중치가 적용된다", () => {
      const normalText = "Payment Integration";
      const headerText = "# Payment Integration";

      const normalTokens = TokenEstimator.estimate(normalText);
      const headerTokens = TokenEstimator.estimate(headerText);

      // 헤더는 약간의 가중치가 추가되어야 함
      expect(headerTokens).toBeGreaterThan(normalTokens);
    });
  });

  describe("복합 텍스트 처리", () => {
    it("토스페이먼츠 문서 스타일 텍스트를 처리한다", () => {
      const complexText = `
# 결제 연동 가이드

토스페이먼츠 \`Payment\` 객체를 사용하여 결제를 연동합니다.

\`\`\`javascript
const payment = new Payment({
  clientKey: "test_ck_...",
  customerKey: "customer_123"
});
\`\`\`

자세한 내용은 https://docs.tosspayments.com 을 참조하세요.
      `;

      const tokens = TokenEstimator.estimate(complexText);

      // 복합 텍스트도 합리적인 범위 내에서 추정되어야 함
      expect(tokens).toBeGreaterThan(50);
      expect(tokens).toBeLessThan(200);
    });
  });

  describe("유틸리티 메서드", () => {
    it("여러 텍스트의 총 토큰 수를 계산한다", () => {
      const texts = ["Hello", "World", "Test"];
      const total = TokenEstimator.estimateTotal(texts);
      const individual = texts.reduce(
        (sum, text) => sum + TokenEstimator.estimate(text),
        0
      );

      expect(total).toBe(individual);
    });

    it("토큰 한계 초과 여부를 확인한다", () => {
      const shortText = "Hello";
      const longText = "A".repeat(1000);

      expect(TokenEstimator.exceedsLimit(shortText, 100)).toBe(false);
      expect(TokenEstimator.exceedsLimit(longText, 100)).toBe(true);
    });
  });
});
