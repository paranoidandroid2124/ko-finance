import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminTokenLoginCard } from "@/components/admin/AdminTokenLoginCard";
import { ADMIN_SESSION_STORAGE_KEY } from "@/lib/adminApi";
import { renderWithProviders, flushAsync } from "../testUtils";

const toastMock = vi.fn();

let unauthorizedState = true;
let refetchSpy: ReturnType<typeof vi.fn>;

vi.mock("@/hooks/useAdminSession", () => ({
  useAdminSession: () => ({
    data: undefined,
    error: unauthorizedState ? new Error("unauthorized") : null,
    isLoading: false,
    isFetching: false,
    isFetched: true,
    status: unauthorizedState ? "error" : "success",
    refetch: (...args: unknown[]) => refetchSpy(...(args as Parameters<typeof refetchSpy>)),
    isUnauthorized: unauthorizedState,
  }),
}));

vi.mock("@/store/toastStore", () => ({
  useToastStore: (selector: (store: { show: typeof toastMock }) => unknown) => selector({ show: toastMock }),
}));

describe("AdminTokenLoginCard", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    refetchSpy = vi.fn().mockResolvedValue(undefined);
    unauthorizedState = true;
    toastMock.mockClear();
    localStorage.clear();
    document.cookie = "";
    global.fetch = originalFetch ?? (vi.fn() as unknown as typeof fetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    toastMock.mockReset();
    localStorage.clear();
    document.cookie = "";
    if (originalFetch) {
      global.fetch = originalFetch;
    }
  });

  it("automatically retries session fetch when a stored token exists", async () => {
    localStorage.setItem(ADMIN_SESSION_STORAGE_KEY, "stored-token");

    renderWithProviders(<AdminTokenLoginCard />);
    await flushAsync();

    expect(refetchSpy).toHaveBeenCalledTimes(1);
    expect(refetchSpy).toHaveBeenCalledWith({ throwOnError: false });
  });

  it("persists token and refetches on successful login", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ actor: "ops@kfinance.ai", issuedAt: new Date().toISOString(), tokenHint: "****" }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    renderWithProviders(<AdminTokenLoginCard />);

    fireEvent.change(screen.getByLabelText("관리자 토큰"), { target: { value: "ops_live_token" } });
    fireEvent.submit(screen.getByRole("button", { name: "운영 세션 열기" }).closest("form")!);

    await flushAsync();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const fetchArgs = fetchMock.mock.calls[0] as Parameters<typeof fetch>;
    expect(fetchArgs[1]?.headers).toMatchObject({
      Authorization: "Bearer ops_live_token",
    });
    expect(localStorage.getItem(ADMIN_SESSION_STORAGE_KEY)).toBe("ops_live_token");
    expect(refetchSpy).toHaveBeenCalledWith({ throwOnError: false });
  });

  it("allows clearing a stored token when unauthorized", async () => {
    localStorage.setItem(ADMIN_SESSION_STORAGE_KEY, "legacy-token");
    renderWithProviders(<AdminTokenLoginCard />);

    fireEvent.click(screen.getByRole("button", { name: "저장된 토큰 초기화" }));

    expect(localStorage.getItem(ADMIN_SESSION_STORAGE_KEY)).toBeNull();
    expect(toastMock).toHaveBeenCalled();
  });
});
