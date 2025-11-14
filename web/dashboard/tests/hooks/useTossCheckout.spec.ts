import { act, renderHook } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { useTossCheckout } from "@/hooks/useTossCheckout";

const fetchMock = vi.fn();
const fetchWithAuthMock = vi.fn();
const loadTossPaymentsMock = vi.fn();
const toastMock = vi.fn();

vi.mock("@/lib/apiBase", () => ({
  resolveApiBase: () => "https://api.test",
}));

vi.mock("@/lib/fetchWithAuth", () => ({
  fetchWithAuth: (...args: unknown[]) => fetchWithAuthMock(...args),
}));

vi.mock("@/lib/tossPayments", () => ({
  loadTossPayments: (...args: unknown[]) => loadTossPaymentsMock(...args),
}));

vi.mock("@/store/toastStore", () => ({
  useToastStore: (selector: (state: { show: typeof toastMock }) => typeof toastMock) =>
    selector({ show: toastMock }),
}));

const originalFetch = global.fetch;

beforeEach(() => {
  fetchMock.mockReset();
  fetchWithAuthMock.mockReset();
  loadTossPaymentsMock.mockReset();
  toastMock.mockReset();
  global.fetch = fetchMock as typeof global.fetch;
});

afterEach(() => {
  global.fetch = originalFetch;
});

const mockConfigResponse = {
  ok: true,
  json: () =>
    Promise.resolve({
      clientKey: "client-key",
      successUrl: "/success",
      failUrl: "/fail",
    }),
};

const mockCheckoutResponse = {
  ok: true,
  json: () =>
    Promise.resolve({
      orderId: "order-123",
      planTier: "pro",
      amount: 1000,
      currency: "KRW",
      orderName: "K-Finance Pro",
      successPath: "/payments/success",
      failPath: "/payments/fail",
    }),
};

describe("useTossCheckout", () => {
  it("loads config and requests payment", async () => {
    const requestPayment = vi.fn().mockResolvedValue(undefined);
    fetchMock.mockResolvedValueOnce(mockConfigResponse);
    fetchWithAuthMock.mockResolvedValueOnce(mockCheckoutResponse as Response);
    loadTossPaymentsMock.mockResolvedValueOnce({
      requestPayment,
    });

    const { result } = renderHook(() => useTossCheckout());

    await act(async () => {
      await result.current.startCheckout({ targetTier: "pro" });
    });

    expect(fetchMock).toHaveBeenCalledWith("https://api.test/api/v1/payments/toss/config", expect.any(Object));
    expect(fetchWithAuthMock).toHaveBeenCalled();
    expect(requestPayment).toHaveBeenCalledWith(
      "CARD",
      expect.objectContaining({
        orderId: "order-123",
        amount: 1000,
      }),
    );
    expect(result.current.lastError).toBeNull();
  });

  it("surfaces checkout failures and shows a toast", async () => {
    const failureMessage = "결제 한도가 초과되었습니다.";
    fetchMock.mockResolvedValueOnce(mockConfigResponse);
    const requestPayment = vi.fn();
    loadTossPaymentsMock.mockResolvedValueOnce({ requestPayment });
    fetchWithAuthMock.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          detail: {
            message: failureMessage,
          },
        }),
    } as unknown as Response);

    const { result } = renderHook(() => useTossCheckout());

    await act(async () => {
      await expect(result.current.startCheckout({ targetTier: "pro", redirectPath: "/plans" })).rejects.toThrow(
        failureMessage,
      );
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.current.lastError).toBe(failureMessage);
  });
});
