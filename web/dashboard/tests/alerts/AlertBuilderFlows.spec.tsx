import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { flushAsync, renderWithProviders } from "../testUtils";
import { screen, act, fireEvent, waitFor } from "@testing-library/react";

import { AlertBuilder } from "@/components/alerts/AlertBuilder";
import { proPlanInfo, createAlertRuleFixture, resetAlertStores, loadPlanContext } from "@/testing/fixtures/alerts";
import type { AlertRuleCreatePayload } from "@/lib/alertsApi";
import { useToastStore } from "@/store/toastStore";

const mockCreateMutation = vi.fn<Promise<unknown>, [AlertRuleCreatePayload]>();
const mockUpdateMutation = vi.fn();

const mockChannelSchema = {
  channels: [
    {
      type: "email",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "이메일을 한 개 이상 입력해주세요." },
        { type: "regex", pattern: "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", message: "유효하지 않은 이메일: {invalid}", collectInvalid: true },
      ],
      metadataRules: {},
    },
    {
      type: "slack",
      requiresTarget: true,
      targetRules: [
        { type: "required", message: "Webhook을 입력해주세요." },
        { type: "regex", pattern: "^https?://[^\\s]+$", flags: "i", message: "유효한 URL을 입력해주세요." },
      ],
      metadataRules: {},
    },
    {
      type: "telegram",
      requiresTarget: false,
      targetRules: [],
      metadataRules: {},
    },
  ],
};

vi.mock("@/hooks/useAlerts", () => ({
  useCreateAlertRule: () => ({
    mutateAsync: mockCreateMutation,
    isPending: false,
  }),
  useUpdateAlertRule: () => ({
    mutateAsync: mockUpdateMutation,
    isPending: false,
  }),
  useAlertRules: () => ({
    data: { items: [], plan: proPlanInfo },
    isLoading: false,
    isError: false,
  }),
  useAlertChannelSchema: () => ({
    data: mockChannelSchema,
    isLoading: false,
  }),
}));

vi.mock("@/lib/telemetry", () => ({
  logEvent: vi.fn(),
}));

const typeBasicForm = async () => {
  const user = userEvent.setup();
  const nameField = screen.getByPlaceholderText(/TEST/i);
  await user.clear(nameField);
  await user.type(nameField, "친구들 공시 소식");

  const tickerField = screen.getByPlaceholderText(/KOSPI/i);
  await user.clear(tickerField);
  await user.type(tickerField, "KOFC");

  return { user };
};

describe("AlertBuilder 사용자 플로우", () => {
  beforeEach(() => {
    act(() => {
      resetAlertStores();
      loadPlanContext("pro");
    });
    mockCreateMutation.mockReset();
    mockCreateMutation.mockResolvedValue(createAlertRuleFixture());
  });

  it("새 규칙을 생성하면 mutation 호출과 성공 토스트로 완료된다", async () => {
    renderWithProviders(<AlertBuilder plan={proPlanInfo} existingCount={2} />);
    const { user } = await typeBasicForm();

    const emailToggle = screen.getByRole("checkbox", { name: /email/i });
    expect(emailToggle).toBeChecked();
    await user.click(emailToggle);
    expect(emailToggle).not.toBeChecked();

    const slackToggle = screen.getByRole("checkbox", { name: /slack/i });
    await user.click(slackToggle);

    const slackTarget = screen.getByPlaceholderText(/hooks\.slack\.com/i);
    await user.type(slackTarget, "https://hooks.slack.com/services/demo");

    const form = screen.getByTestId("alert-builder-form");
    const submit = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    expect(submit).not.toBeNull();

    await act(async () => {
      await user.click(submit!);
      await flushAsync();
    });

    await waitFor(() => {
      expect(mockCreateMutation).toHaveBeenCalledTimes(1);
    });
    const payload = mockCreateMutation.mock.calls[0][0];
    expect(payload.channels[0]).toMatchObject({
      type: "slack",
      target: "https://hooks.slack.com/services/demo",
    });
    await waitFor(() => {
      const toasts = useToastStore.getState().toasts;
      expect(toasts.map((toast) => toast.id)).toContain("alerts/builder/create-success");
    });
  });

  it("플랜 할당량이 모두 찼다면 경고 토스트를 보여준다", async () => {
    const quotaPlan = { ...proPlanInfo, remainingAlerts: 0 };
    renderWithProviders(<AlertBuilder plan={quotaPlan} existingCount={quotaPlan.maxAlerts} />);
    const { user } = await typeBasicForm();

    const slackToggle = screen.getByRole("checkbox", { name: /slack/i });
    await user.click(slackToggle);
    const slackTarget = screen.getByPlaceholderText(/hooks\.slack\.com/i);
    await user.type(slackTarget, "https://hooks.slack.com/services/demo");

    const submit = screen.getByTestId("alert-builder-form").querySelector<HTMLButtonElement>('button[type="submit"]');
    expect(submit).toBeDisabled();

    const form = screen.getByTestId("alert-builder-form");
    await act(async () => {
      fireEvent.submit(form);
      await flushAsync();
    });

    expect(mockCreateMutation).not.toHaveBeenCalled();
    await waitFor(() => {
      const toasts = useToastStore.getState().toasts;
      expect(toasts.map((toast) => toast.id)).toContain("alerts/builder/quota");
    });
  });

  it("채널 정보가 비어있으면 검증 토스트와 포커스 안내를 띄운다", async () => {
    renderWithProviders(<AlertBuilder plan={proPlanInfo} existingCount={2} />);
    const { user } = await typeBasicForm();

    const emailToggle = screen.getByRole("checkbox", { name: /email/i });
    await user.click(emailToggle); // 이메일 비활성화

    const slackToggle = screen.getByRole("checkbox", { name: /slack/i });
    await user.click(slackToggle); // 슬랙 활성화 (타겟 미입력)

    const submit = screen.getByTestId("alert-builder-form").querySelector<HTMLButtonElement>('button[type="submit"]');
    await act(async () => {
      await user.click(submit!);
      await flushAsync();
    });

    expect(mockCreateMutation).not.toHaveBeenCalled();

    await waitFor(() => {
      const toasts = useToastStore.getState().toasts;
      expect(toasts.map((toast) => toast.id)).toContain("alerts/builder/channel-invalid");
    });

    const slackTarget = screen.getByPlaceholderText(/hooks\.slack\.com/i);
    await waitFor(() => {
      expect(slackTarget).toHaveAttribute("aria-invalid", "true");
    });
  });
});
