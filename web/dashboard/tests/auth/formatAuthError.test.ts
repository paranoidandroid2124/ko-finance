import { describe, expect, it } from "vitest";

import { formatAuthError, toApiDetail } from "@/lib/authError";

describe("authError helpers", () => {
  it("formats generic API errors with fallback text", () => {
    expect(formatAuthError(null, "기본 메시지")).toBe("기본 메시지");
    expect(formatAuthError({ message: "실패", code: "auth.invalid_password" }, "fallback")).toBe("실패 (auth.invalid_password)");
  });

  it("adds retry-after guidance for rate limit responses", () => {
    expect(
      formatAuthError(
        { code: "auth.rate_limited", message: "요청이 너무 많습니다.", retryAfter: 9.2 },
        "fallback",
      ),
    ).toBe("요청이 너무 많습니다. (9초 후 다시 시도)");
  });

  it("parses JSON strings into ApiDetail", () => {
    const detail = toApiDetail('{"code":"auth.account_locked","message":"LOCKED"}');
    expect(detail).toEqual({ code: "auth.account_locked", message: "LOCKED", retryAfter: undefined });
    expect(toApiDetail(undefined)).toBeNull();
  });
});
