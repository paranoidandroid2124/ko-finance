import { useEffect } from "react";
import type { Meta, StoryObj } from "@storybook/react";

import { PlanSettingsForm } from "@/components/plan/PlanSettingsForm";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

const meta: Meta<typeof PlanSettingsForm> = {
  title: "Plan/PlanSettingsForm",
  component: PlanSettingsForm,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof PlanSettingsForm>;

const originalState = usePlanStore.getState();

const defaultPayload: PlanContextPayload = {
  planTier: "pro",
  expiresAt: "2026-01-01T00:00:00+09:00",
  entitlements: ["search.compare", "search.alerts", "search.export", "rag.core", "timeline.full"],
  featureFlags: {
    searchCompare: true,
    searchAlerts: true,
    searchExport: false,
    ragCore: true,
    evidenceInlinePdf: false,
    evidenceDiff: false,
    timelineFull: true,
    reportsEventExport: true,
  },
  memoryFlags: {
    watchlist: true,
    digest: true,
    chat: true,
  },
  quota: {
    chatRequestsPerDay: 500,
    ragTopK: 6,
    selfCheckEnabled: true,
    peerExportRowLimit: 120,
  },
  updatedAt: "2025-11-01T09:00:00+09:00",
  updatedBy: "hana@kfinance.ai",
  changeNote: "모프 테스트 저장본",
  checkoutRequested: false,
};

function PlanSettingsFormStory({ checkoutRequested }: { checkoutRequested?: boolean }) {
  useEffect(() => {
    usePlanStore.setState({
      ...defaultPayload,
      checkoutRequested: checkoutRequested ?? false,
      initialized: true,
      loading: false,
      saving: false,
      error: undefined,
      saveError: undefined,
      fetchPlan: async () => undefined,
      setPlanFromServer: () => undefined,
      savePlan: async () => Promise.resolve(defaultPayload),
    });
    return () => {
      usePlanStore.setState(originalState, true);
    };
  }, [checkoutRequested]);

  return <PlanSettingsForm />;
}

export const Default: Story = {
  render: () => <PlanSettingsFormStory />,
};

export const CheckoutRequested: Story = {
  render: () => <PlanSettingsFormStory checkoutRequested />,
};
