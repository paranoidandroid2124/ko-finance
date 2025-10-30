import { describe, expect, it } from "vitest";

import { getPlanCopy, parsePlanTier } from "@/components/alerts/planMessaging";

describe("planMessaging copy", () => {
  it("플랜 문자열을 안전하게 파싱한다", () => {
    expect(parsePlanTier("pro")).toBe("pro");
    expect(parsePlanTier("enterprise")).toBe("enterprise");
    expect(parsePlanTier("unknown")).toBe("free");
    expect(parsePlanTier(undefined)).toBe("free");
  });

  it("Free 플랜은 업그레이드 잠금 정보를 제공한다", () => {
    const copy = getPlanCopy("free");
    expect(copy.builder.lock?.requiredTier).toBe("pro");
    expect(copy.builder.disabledHint).toContain("Slack");
    const message = copy.builder.quotaToast.description({ remaining: 0, max: 1 });
    expect(message).toContain("Free");
    expect(message).toMatch(/\b1\b/);
  });

  it("Pro 플랜은 잠금 없이 채널 안내만 노출한다", () => {
    const copy = getPlanCopy("pro");
    expect(copy.builder.lock).toBeUndefined();
    expect(copy.builder.disabledHint).toContain("Webhook");
    const banner = copy.builder.quotaBanner({ remaining: 2, max: 10 });
    expect(banner).toContain("10");
  });

  it("Enterprise 플랜은 무제한 메시지를 안내한다", () => {
    const copy = getPlanCopy("enterprise");
    const banner = copy.builder.quotaBanner({ remaining: 5, max: 0 });
    expect(banner).toMatch(/무제한|Free/);
    const bellToast = copy.bell.quotaToast.description({ remaining: 24, max: 30 });
    expect(bellToast).toContain("30");
  });
});

