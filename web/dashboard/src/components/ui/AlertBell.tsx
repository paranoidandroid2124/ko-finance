"use client";

import { useId, useMemo, useState, useEffect, useRef, useCallback } from "react";
import type { FocusEvent, KeyboardEvent } from "react";
import clsx from "classnames";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, Loader2, Pin, PinOff, X } from "lucide-react";
import { useRouter, usePathname } from "next/navigation";
import { useDashboardOverview, type DashboardAlert } from "@/hooks/useDashboardOverview";
import { useChatStore, selectActiveSession } from "@/store/chatStore";

const ALERT_LIMIT = 9;
const CLOSE_DELAY_MS = 120;

const toneStyles: Record<DashboardAlert["tone"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  negative: "bg-accent-negative/15 text-accent-negative",
  warning: "bg-accent-warning/20 text-accent-warning",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark"
};

const isExternalUrl = (value: string) => /^https?:\/\//i.test(value);

export function AlertBell() {
  const containerId = useId();
  const router = useRouter();
  const pathname = usePathname();
  const { data, isLoading, isError } = useDashboardOverview();

  const alerts = useMemo(() => data?.alerts ?? [], [data?.alerts]);
  const visibleAlerts = useMemo(() => alerts.slice(0, ALERT_LIMIT), [alerts]);

  const sessions = useChatStore((state) => state.sessions);
  const activeSession = useChatStore(selectActiveSession);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const createSession = useChatStore((state) => state.createSession);

  const [isPinned, setIsPinned] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [hasFocusWithin, setHasFocusWithin] = useState(false);

  const closeTimerRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const isOpen = isPinned || isHovering || hasFocusWithin;
  const badgeValue = alerts.length > 9 ? "10+" : alerts.length.toString();

  const otherSessions = useMemo(
    () => sessions.filter((session) => session.id !== activeSessionId).slice(0, 3),
    [sessions, activeSessionId]
  );

  const clearCloseTimer = () => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const requestClose = useCallback(() => {
    if (isPinned) {
      return;
    }
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setIsHovering(false);
      setHasFocusWithin(false);
      closeTimerRef.current = null;
    }, CLOSE_DELAY_MS);
  }, [isPinned]);

  const closeImmediately = useCallback(() => {
    clearCloseTimer();
    setIsPinned(false);
    setIsHovering(false);
    setHasFocusWithin(false);
  }, []);

  useEffect(() => {
    return () => {
      clearCloseTimer();
    };
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeImmediately();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeImmediately, isOpen]);

  const handlePointerEnter = () => {
    clearCloseTimer();
    setIsHovering(true);
  };

  const handlePointerLeave = () => {
    setIsHovering(false);
    requestClose();
  };

  const handleFocusIn = () => {
    clearCloseTimer();
    setHasFocusWithin(true);
  };

  const handleFocusOut = (event: FocusEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget as HTMLElement | null;
    if (nextTarget && containerRef.current?.contains(nextTarget)) {
      return;
    }
    setHasFocusWithin(false);
    requestClose();
  };

  const handleTriggerClick = () => {
    setIsPinned((prev) => {
      const next = !prev;
      if (next) {
        clearCloseTimer();
        setIsHovering(true);
      } else {
        closeImmediately();
      }
      return next;
    });
  };

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleTriggerClick();
    }
  };

  const handleTogglePin = () => {
    setIsPinned((prev) => {
      if (prev) {
        requestClose();
        return false;
      }
      clearCloseTimer();
      setHasFocusWithin(true);
      return true;
    });
  };

  const handleAlertNavigate = useCallback(
    (alert: DashboardAlert) => {
      const target = alert.targetUrl?.trim();
      if (target) {
        if (isExternalUrl(target)) {
          window.open(target, "_blank", "noopener,noreferrer");
        } else if (pathname !== target) {
          router.push(target);
        }
        closeImmediately();
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
      closeImmediately();
    },
    [activeSessionId, closeImmediately, pathname, router]
  );

  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      void (async () => {
        await setActiveSession(sessionId);
        if (pathname !== "/chat") {
          router.push(`/chat?session=${sessionId}`);
        } else {
          router.push(`/chat?session=${sessionId}`);
        }
        closeImmediately();
      })();
    },
    [closeImmediately, pathname, router, setActiveSession]
  );

  const handleStartNewSession = () => {
    void (async () => {
      try {
        const sessionId = await createSession({ context: { type: "custom" } });
        await setActiveSession(sessionId);
        router.push(`/chat?session=${sessionId}`);
        closeImmediately();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "새 대화를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.";
        window.alert(message);
      }
    })();
  };

  const alertCount = alerts.length;
  const showBadge = alertCount > 0;

  return (
    <div
      ref={containerRef}
      data-testid="alert-bell"
      className="relative flex h-10 w-10 items-center justify-center"
      onMouseEnter={handlePointerEnter}
      onMouseLeave={handlePointerLeave}
      onFocusCapture={handleFocusIn}
      onBlurCapture={handleFocusOut}
    >
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls={containerId}
        aria-label="실시간 신호 패널 열기"
        className={clsx(
          "relative h-10 w-10 rounded-full border border-border-light text-text-secondaryLight shadow-sm transition-transform duration-150 hover:scale-[1.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark",
          isOpen && "border-primary text-primary dark:border-primary.dark dark:text-primary.dark"
        )}
        onClick={handleTriggerClick}
        onKeyDown={handleTriggerKeyDown}
      >
        <Bell className="mx-auto h-5 w-5" aria-hidden />
        {showBadge ? (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-white shadow-sm"
          >
            {badgeValue}
          </span>
        ) : null}
        {isPinned ? <Pin className="absolute right-0 top-1 h-3 w-3 text-primary" aria-hidden /> : null}
      </button>

      <AnimatePresence>
        {isOpen ? (
          <motion.div
            key="alert-panel"
            id={containerId}
            role="dialog"
            aria-label="실시간 신호"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            className="absolute right-0 top-[calc(100%+12px)] z-50 w-[384px] max-w-[90vw] rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-xl ring-1 ring-black/5 dark:border-border-dark dark:bg-background-cardDark"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">실시간 신호</p>
                <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최신 공시·뉴스 업데이트</p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleTogglePin}
                  className="rounded-full p-1 text-text-secondaryLight transition hover:bg-border-light/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:text-text-secondaryDark dark:hover:bg-border-dark/50"
                >
                  {isPinned ? <Pin className="h-4 w-4" aria-hidden /> : <PinOff className="h-4 w-4" aria-hidden />}
                  <span className="sr-only">{isPinned ? "핀 해제" : "핀 고정"}</span>
                </button>
                <button
                  type="button"
                  onClick={closeImmediately}
                  className="rounded-full p-1 text-text-secondaryLight transition hover:bg-border-light/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:text-text-secondaryDark dark:hover:bg-border-dark/50"
                >
                  <X className="h-4 w-4" aria-hidden />
                  <span className="sr-only">패널 닫기</span>
                </button>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <section className="rounded-xl border border-border-light/70 bg-white/70 px-3 py-3 dark:border-border-dark/70 dark:bg-white/5">
                {isLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div key={`alert-skeleton-${index}`} className="space-y-2">
                        <div className="h-3 w-24 rounded bg-border-light/70 dark:bg-border-dark/60" />
                        <div className="h-3 w-full rounded bg-border-light/60 dark:bg-border-dark/50" />
                        <div className="h-2 w-20 rounded bg-border-light/50 dark:bg-border-dark/40" />
                      </div>
                    ))}
                  </div>
                ) : isError ? (
                  <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-4 text-xs text-destructive dark:border-destructive/60 dark:bg-destructive/10">
                    대시보드 알림을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
                  </div>
                ) : visibleAlerts.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border-light px-3 py-4 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                    표시할 알림이 아직 없습니다. 데이터가 수집되면 자동으로 채워집니다.
                  </div>
                ) : (
                  <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
                    {visibleAlerts.map((alert) => (
                      <button
                        key={alert.id}
                        type="button"
                        className="w-full rounded-lg border border-border-light/60 bg-white/80 px-3 py-2 text-left text-sm transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark/60 dark:bg-white/10 dark:hover:border-primary.dark dark:hover:text-primary.dark"
                        onClick={() => handleAlertNavigate(alert)}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium leading-tight">{alert.title}</p>
                            <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{alert.body}</p>
                          </div>
                          {alert.tone ? (
                            <span
                              className={clsx(
                                "rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize",
                                toneStyles[alert.tone]
                              )}
                            >
                              {alert.tone}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                          {alert.timestamp}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-border-light/70 bg-gradient-to-br from-primary/12 via-background-cardLight to-white px-4 py-4 shadow-sm dark:border-border-dark/70 dark:from-primary.dark/15 dark:via-background-cardDark dark:to-background-cardDark">
                <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">대화형 분석</p>
                <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  챗봇을 통해 공시·뉴스를 빠르게 탐색하고 필요한 인사이트를 확보하세요.
                </p>
                <button
                  type="button"
                  onClick={handleStartNewSession}
                  className="mt-3 inline-flex w-full items-center justify-center rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition hover:scale-[1.02] hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-background-cardDark"
                >
                  새 대화 시작
                </button>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="rounded-lg border border-border-light/70 bg-white/70 px-3 py-3 dark:border-border-dark/70 dark:bg-white/10">
                    <p className="text-xs uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                      현재 세션
                    </p>
                    <p className="mt-1 font-medium text-text-primaryLight dark:text-text-primaryDark">
                      {activeSession ? activeSession.title : "활성 세션이 없습니다"}
                    </p>
                    <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                      {activeSession?.updatedAt ?? "최신 활동 정보 없음"}
                    </p>
                  </div>
                  {otherSessions.length > 0 ? (
                    <div>
                      <p className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">최근 세션</p>
                      <div className="mt-2 space-y-2">
                        {otherSessions.map((session) => (
                          <button
                            key={session.id}
                            type="button"
                            onClick={() => handleSessionSelect(session.id)}
                            className="w-full rounded-lg border border-border-light/70 bg-background-cardLight px-3 py-2 text-left text-[13px] font-medium text-text-primaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark/70 dark:bg-background-cardDark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                          >
                            <span className="block truncate">{session.title}</span>
                            <span className="text-[11px] font-normal text-text-secondaryLight dark:text-text-secondaryDark">
                              {session.updatedAt}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
