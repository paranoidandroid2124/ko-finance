import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";

let themeValue = "light";
const setThemeMock = vi.fn();

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: themeValue,
    setTheme: setThemeMock
  })
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    themeValue = "light";
    setThemeMock.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  // 정상 흐름: 테마 토글 버튼이 현재 상태에 맞는 텍스트를 표시하고 클릭 시 setTheme이 호출된다.
  it("toggles theme when button is clicked", async () => {
    render(<SettingsPage />);

    const button = await screen.findByRole("button", { name: "다크 테마로 전환" });
    fireEvent.click(button);

    expect(setThemeMock).toHaveBeenCalledWith("dark");
  });

  // 정상 흐름: 알림 채널 토글이 체크 상태를 변경한다.
  it("updates notification channel state", async () => {
    render(<SettingsPage />);

    const [telegramCheckbox] = await screen.findAllByLabelText("사용", { selector: 'input[type="checkbox"]' });
    expect(telegramCheckbox).toBeChecked();

    fireEvent.click(telegramCheckbox);

    expect(telegramCheckbox).not.toBeChecked();
  });
});
