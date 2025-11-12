import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminTokenLoginCard } from "@/components/admin/AdminTokenLoginCard";
import { loginAdminWithCredentials } from "@/lib/adminApi";
import { flushAsync, renderWithProviders } from "../testUtils";

vi.mock("@/lib/adminApi", () => ({
  loginAdminWithCredentials: vi.fn(),
}));

const toastMock = vi.fn();
const credentialLoginMock = loginAdminWithCredentials as unknown as ReturnType<typeof vi.fn>;

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
  beforeEach(() => {
    refetchSpy = vi.fn().mockResolvedValue(undefined);
    unauthorizedState = true;
    toastMock.mockReset();
    credentialLoginMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("submits credentials and refetches session state on success", async () => {
    credentialLoginMock.mockResolvedValue({
      actor: "ops",
      issuedAt: new Date().toISOString(),
      tokenHint: "sid:1234",
    });

    renderWithProviders(<AdminTokenLoginCard />);

    fireEvent.change(screen.getByLabelText(/운영자 이메일/i), { target: { value: "ops@kfinance.ai" } });
    fireEvent.change(screen.getByLabelText(/비밀번호/i), { target: { value: "super-secret" } });
    fireEvent.change(screen.getByLabelText(/MFA/i), { target: { value: "123456" } });
    fireEvent.submit(screen.getByRole("button", { name: "운영 세션 열기" }).closest("form")!);
    await flushAsync();

    expect(credentialLoginMock).toHaveBeenCalledWith({
      email: "ops@kfinance.ai",
      password: "super-secret",
      otp: "123456",
    });
    expect(refetchSpy).toHaveBeenCalledWith({ throwOnError: false });
    expect(toastMock).toHaveBeenCalled();
  });

  it("shows validation message when required fields are empty", async () => {
    renderWithProviders(<AdminTokenLoginCard />);

    fireEvent.submit(screen.getByRole("button", { name: "운영 세션 열기" }).closest("form")!);
    await flushAsync();

    expect(credentialLoginMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("surfaces API errors", async () => {
    credentialLoginMock.mockRejectedValue(new Error("forbidden"));

    renderWithProviders(<AdminTokenLoginCard />);
    fireEvent.change(screen.getByLabelText(/운영자 이메일/i), { target: { value: "ops@kfinance.ai" } });
    fireEvent.change(screen.getByLabelText(/비밀번호/i), { target: { value: "super-secret" } });
    fireEvent.submit(screen.getByRole("button", { name: "운영 세션 열기" }).closest("form")!);
    await flushAsync();

    expect(credentialLoginMock).toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("세션을 확인하지 못했어요");
  });

  it("does not render when already authorized", () => {
    unauthorizedState = false;
    const { container } = renderWithProviders(<AdminTokenLoginCard />);
    expect(container).toBeEmptyDOMElement();
  });
});
