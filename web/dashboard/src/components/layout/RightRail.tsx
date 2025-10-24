"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useDashboardOverview, type DashboardAlert } from "@/hooks/useDashboardOverview";
import { useChatStore, selectActiveSession } from "@/store/chatStore";

const MAX_ALERT_ITEMS = 5;

export function RightRail() {
  const router = useRouter();
  const pathname = usePathname();
  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const createSession = useChatStore((state) => state.createSession);
  const activeSession = useChatStore(selectActiveSession);

  const { data, isLoading, isError } = useDashboardOverview();
  const alerts = data?.alerts ?? [];

  const topAlerts = useMemo(() => alerts.slice(0, MAX_ALERT_ITEMS), [alerts]);

  const secondarySessions = useMemo(
    () => sessions.filter((session) => session.id !== activeSessionId).slice(0, 2),
    [sessions, activeSessionId]
  );

  const handleAlertClick = useCallback(
    (alert: DashboardAlert) => {
      const target = alert.targetUrl?.trim();
      if (target) {
        if (/^https?:\/\//i.test(target)) {
          window.open(target, "_blank", "noopener,noreferrer");
          return;
        }
        if (pathname !== target) {
          router.push(target);
        }
        return;
      }
      if (alert.title.includes("뉴스")) {
        router.push("/news");
      } else if (alert.title.includes("공시")) {
        router.push("/filings");
      } else if (pathname !== "/chat") {
        if (activeSessionId) {
          router.push(`/chat?session=${activeSessionId}`);
        } else {
          router.push("/chat");
        }
      }
    },
    [activeSessionId, pathname, router]
  );

  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      void (async () => {
        await setActiveSession(sessionId);
        if (pathname !== "/chat") {
          router.push(`/chat?session=${sessionId}`);
        }
      })();
    },
    [pathname, router, setActiveSession]
  );

  const handleStartNewSession = useCallback(() => {
    void (async () => {
      try {
        const sessionId = await createSession({ context: { type: "custom" } });
        await setActiveSession(sessionId);
        if (pathname !== "/chat") {
          router.push(`/chat?session=${sessionId}`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "새 세션을 생성하지 못했습니다.";
        window.alert(message);
      }
    })();
  }, [createSession, pathname, router, setActiveSession]);

  return (
    <aside className="hidden w-80 flex-none space-y-4 rounded-xl border border-border-light bg-background-cardLight px-4 py-5 shadow-card dark:border-border-dark dark:bg-background-cardDark xl:block">
      <section>
        <h2 className="text-sm font-semibold">실시간 알림</h2>
        <div className="mt-3 space-y-3 text-sm">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, index) => (
              <div
                key={`alert-skeleton-${index}`}
                className="animate-pulse rounded-lg border border-border-light/60 bg-white/70 px-3 py-3 dark:border-border-dark/60 dark:bg-white/10"
              >
                <div className="h-4 w-28 rounded bg-border-light/60 dark:bg-border-dark/50" />
                <div className="mt-2 h-3 w-full rounded bg-border-light/50 dark:bg-border-dark/40" />
              </div>
            ))
          ) : isError ? (
            <div className="rounded-lg border border-destructive/50 bg-destructive/5 px-3 py-4 text-xs text-destructive dark:border-destructive/60 dark:bg-destructive/10">
              대시보드 알림을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
            </div>
          ) : topAlerts.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border-light px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
              표시할 알림이 없습니다. 데이터가 수집되면 자동으로 표시됩니다.
            </div>
          ) : (
            topAlerts.map((alert) => (
              <button
                key={alert.id}
                type="button"
                className="w-full rounded-lg border border-border-light/60 bg-white/70 px-3 py-2 text-left transition-colors hover:border-primary hover:text-primary dark:border-border-dark/60 dark:bg-white/5 dark:hover:border-primary.dark"
                onClick={() => handleAlertClick(alert)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium leading-tight">{alert.title}</p>
                    <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{alert.body}</p>
                  </div>
                  {alert.tone && (
                    <span className="rounded-full border border-border-light/60 px-2 py-0.5 text-[11px] font-semibold capitalize dark:border-border-dark/60">
                      {alert.tone}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{alert.timestamp}</p>
              </button>
            ))
          )}
        </div>
      </section>
      <section>
        <h2 className="text-sm font-semibold">대화형 분석</h2>
        <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          챗봇을 통해 공시·뉴스에 대해 질문하고 근거를 확인하세요.
        </p>
        <button
          onClick={handleStartNewSession}
          className="mt-3 w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow hover:bg-primary-hover"
        >
          새 대화 시작
        </button>
        <div className="mt-3 space-y-2 text-xs">
          <p className="text-text-secondaryLight dark:text-text-secondaryDark">선택된 세션</p>
          <div className="rounded-md border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">
              {activeSession ? activeSession.title : "세션이 없습니다"}
            </p>
            <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
              {activeSession ? activeSession.updatedAt : "최근 기록 없음"}
            </p>
          </div>
          {secondarySessions.length > 0 && (
            <ul className="space-y-1">
              {secondarySessions.map((session) => (
                <li key={session.id}>
                  <button
                    type="button"
                    onClick={() => handleSessionSelect(session.id)}
                    className="w-full rounded-md border border-border-light px-3 py-2 text-left text-[11px] transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                  >
                    <span className="block font-medium text-text-primaryLight dark:text-text-primaryDark">
                      {session.title}
                    </span>
                    <span>{session.updatedAt}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </aside>
  );
}
