import { describe, expect, it } from "vitest";
import { parseTargetsInput, emptyChannelState } from "@/components/alerts/channelForm";

describe("channelForm", () => {
  it("splits targets by commas and whitespace", () => {
    const input = "alpha@example.com, beta@example.com\n gamma@example.com";
    expect(parseTargetsInput(input)).toEqual([
      "alpha@example.com",
      "beta@example.com",
      "gamma@example.com",
    ]);
  });

  it("returns empty state blueprint", () => {
    const state = emptyChannelState();
    expect(state.enabled).toBe(false);
    expect(state.targets).toEqual([]);
    expect(state.metadata).toEqual({});
  });
});
