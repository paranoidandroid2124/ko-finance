import type { Meta, StoryObj } from "@storybook/react";

import { NewsSignalCards } from "../src/components/company/NewsSignalCards";
import type { NewsWindowInsight } from "../src/hooks/useCompanySnapshot";

const mockSignals: NewsWindowInsight[] = [
  {
    scope: "ticker",
    ticker: "KRX:005930",
    windowDays: 7,
    computedFor: "2025-10-25",
    articleCount: 42,
    avgSentiment: 0.18,
    sentimentZ: 1.9,
    noveltyKl: 0.32,
    topicShift: 0.12,
    domesticRatio: 0.78,
    domainDiversity: 0.64,
    topTopics: [
      { topic: "AI 반도체", count: 15, weight: 0.32 },
      { topic: "공급망", count: 8, weight: 0.18 },
      { topic: "환율", count: 6, weight: 0.14 }
    ],
    sourceReliability: 0.92,
    deduplicationClusterId: "cluster-20251025-01"
  },
  {
    scope: "global",
    windowDays: 30,
    computedFor: "2025-10-25",
    articleCount: 120,
    avgSentiment: -0.05,
    sentimentZ: -0.7,
    noveltyKl: 0.21,
    topicShift: 0.08,
    domesticRatio: 0.45,
    domainDiversity: 0.82,
    topTopics: [
      { topic: "에너지 가격", count: 20, weight: 0.22 },
      { topic: "Fed 정책", count: 12, weight: 0.18 }
    ],
    sourceReliability: null,
    deduplicationClusterId: null
  }
];

const meta: Meta<typeof NewsSignalCards> = {
  title: "Company/NewsSignalCards",
  component: NewsSignalCards,
  parameters: {
    layout: "padded"
  }
};

export default meta;

type Story = StoryObj<typeof NewsSignalCards>;

export const Default: Story = {
  args: {
    signals: mockSignals,
    companyName: "삼성전자"
  }
};
