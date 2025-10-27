import { useEffect, useRef } from "react";
import { within, userEvent } from "@storybook/testing-library";
import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertBell } from "../src/components/ui/AlertBell";
import type { DashboardAlert } from "../src/hooks/useDashboardOverview";
import { useChatStore, type ChatSession } from "../src/store/chatStore";

type AlertBellStoryProps = {
  alerts: DashboardAlert[];
  sessions: ChatSession[];
};

function ensureSessionShape(partialSessions: Partial<ChatSession>[]): ChatSession[] {
  return partialSessions.map((session, index) => ({
    id: session.id ?? `session-${index + 1}`,
    title: session.title ?? `세션 ${index + 1}`,
    updatedAt: session.updatedAt ?? "방금 전",
    context: session.context ?? { type: "custom" },
    messages: session.messages ?? [],
    messagesLoaded: session.messagesLoaded ?? false,
    lastMessageAt: session.lastMessageAt ?? null,
    version: session.version ?? 1,
    evidence: session.evidence ?? { status: "idle", items: [] },
    telemetry:
      session.telemetry ?? {
        guardrail: { status: "idle" },
        metrics: { status: "idle", items: [] }
      }
  }));
}

function AlertBellStoryProvider({ alerts, sessions }: AlertBellStoryProps) {
  const queryClientRef = useRef<QueryClient>();
  const storeSnapshotRef = useRef(useChatStore.getState());

  if (!queryClientRef.current) {
    queryClientRef.current = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnMount: false,
          refetchOnWindowFocus: false
        }
      }
    });
  }

  useEffect(() => {
    const client = queryClientRef.current!;
    client.setQueryDefaults(["dashboard", "overview"], {
      queryFn: async () => ({
        metrics: [],
        alerts,
        news: []
      }),
      staleTime: Infinity
    });
    client.setQueryData(["dashboard", "overview"], {
      metrics: [],
      alerts,
      news: []
    });
  }, [alerts]);

  useEffect(() => {
    const snapshot = storeSnapshotRef.current;
    const seededSessions = ensureSessionShape(sessions);
    useChatStore.setState(
      {
        ...snapshot,
        sessions: seededSessions,
        activeSessionId: seededSessions[0]?.id ?? null
      },
      true
    );
    return () => {
      useChatStore.setState(snapshot, true);
    };
  }, [sessions]);

  return (
    <QueryClientProvider client={queryClientRef.current!}>
      <div className="flex w-full max-w-md justify-end">
        <AlertBell />
      </div>
    </QueryClientProvider>
  );
}

const meta: Meta<typeof AlertBell> = {
  title: "Dashboard/AlertBell",
  component: AlertBell,
  parameters: {
    layout: "centered"
  }
};

export default meta;

type Story = StoryObj<typeof AlertBell>;

const baseSessions: ChatSession[] = ensureSessionShape([
  {
    id: "session-1",
    title: "최신 실적 브리핑",
    updatedAt: "5분 전"
  },
  {
    id: "session-2",
    title: "AI 산업 리서치",
    updatedAt: "어제"
  },
  {
    id: "session-3",
    title: "주간 공시 체크",
    updatedAt: "3일 전"
  }
]);

export const HoverOpen: Story = {
  render: () => (
    <AlertBellStoryProvider
      alerts={[
        {
          id: "alert-1",
          title: "삼성전자, 3분기 실적 발표",
          body: "분기 매출이 전년 대비 12% 증가했습니다.",
          timestamp: "2분 전",
          tone: "positive",
          targetUrl: "/filings/krx-005930"
        },
        {
          id: "alert-2",
          title: "해외 뉴스 속보",
          body: "미국 CPI 지수가 예상을 상회했습니다.",
          timestamp: "8분 전",
          tone: "warning",
          targetUrl: "https://news.example.com/cpi"
        },
        {
          id: "alert-3",
          title: "기업 공시 업데이트",
          body: "신규 IR 자료가 등록되었습니다.",
          timestamp: "12분 전",
          tone: "neutral",
          targetUrl: "/filings/latest"
        }
      ]}
      sessions={baseSessions}
    />
  )
};

export const EmptyState: Story = {
  render: () => <AlertBellStoryProvider alerts={[]} sessions={baseSessions.slice(0, 1)} />
};

export const PinnedOpen: Story = {
  render: () => (
    <AlertBellStoryProvider
      alerts={[
        {
          id: "alert-1",
          title: "긴급 공시",
          body: "정정 공시가 등록되었습니다.",
          timestamp: "1분 전",
          tone: "negative",
          targetUrl: "/filings/correction"
        }
      ]}
      sessions={baseSessions}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = await canvas.findByRole("button", { name: "실시간 신호 패널 열기" });
    await userEvent.click(trigger);
    const pinButton = await canvas.findByRole("button", { name: "핀 고정" });
    await userEvent.click(pinButton);
  }
};
