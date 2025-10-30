"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useId } from "react";
import type { FocusEvent as ReactFocusEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAlertRules, useDeleteAlertRule, useUpdateAlertRule } from "@/hooks/useAlerts";
import { useDashboardOverview, type DashboardAlert } from "@/hooks/useDashboardOverview";
import { ApiError, type AlertPlanInfo, type AlertRule } from "@/lib/alertsApi";
import { logEvent } from "@/lib/telemetry";
import { useChatStore, selectActiveSession, type ChatSession } from "@/store/chatStore";
import { useToastStore } from "@/store/toastStore";
import { getPlanCopy, parsePlanTier, UNKNOWN_PLAN_COPY } from "@/components/alerts/planMessaging";
import { usePlanUpgrade } from "@/hooks/usePlanUpgrade";
import type { PlanTier } from "@/store/planStore";
import type { BuilderMode } from "@/components/alerts/channelForm";

const ALERT_LIMIT = 9;
const CLOSE_DELAY_MS = 120;

export type AlertBellTriggerProps = {
  containerId: string;
  isOpen: boolean;
  isPinned: boolean;
  showBadge: boolean;
  badgeValue: string;
  onClick: () => void;
  onKeyDown: (event: ReactKeyboardEvent<HTMLButtonElement>) => void;
};

export type AlertBellPanelProps = {
  containerId: string;
  isPinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
  builder: {
    isOpen: boolean;
    mode: BuilderMode;
    editingRule: AlertRule | null;
    plan: AlertPlanInfo | null;
    existingCount: number;
    ctaLabel: string;
    isDisabled: boolean;
    disabledReason: string;
    disabledHint: string;
    quotaReached: boolean;
    quotaInfo: { remaining: number; max: number };
    copy: ReturnType<typeof getPlanCopy>["builder"];
    onOpenCreate: (trigger?: HTMLElement | null) => void;
    onSuccess: () => void;
    onCancel: () => void;
    onRequestUpgrade: (tier: PlanTier) => void;
  };
  planSummary: {
    alertPlan: AlertPlanInfo | null;
    alertChannelSummary: string;
    maxRules: number;
    remainingSlots: number;
    builderQuotaReached: boolean;
    builderMode: BuilderMode;
    isBuilderDisabled: boolean;
    builderDisabledReason: string;
    builderDisabledHint: string;
    bellCopy: ReturnType<typeof getPlanCopy>["bell"];
    quotaInfo: { remaining: number; max: number };
  };
  alerts: {
    alerts: DashboardAlert[];
    visibleAlerts: DashboardAlert[];
    isLoading: boolean;
    isError: boolean;
    onNavigate: (alert: DashboardAlert) => void;
  };
  rules: {
    rules: AlertRule[];
    isLoading: boolean;
    isError: boolean;
    mutatingRuleId: string | null;
    builderMode: BuilderMode;
    isBuilderOpen: boolean;
    editingRule: AlertRule | null;
    onEdit: (rule: AlertRule, trigger?: HTMLElement | null) => void;
    onDuplicate: (rule: AlertRule, trigger?: HTMLElement | null) => void;
    onToggle: (rule: AlertRule) => void;
    onDelete: (rule: AlertRule) => void;
  };
  chat: {
    activeSession: ChatSession | null;
    otherSessions: ChatSession[];
    onSelect: (sessionId: string) => void;
    onStartNew: () => void;
  };
};

export type AlertBellContainerHandlers = {
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onFocusCapture: () => void;
  onBlurCapture: (event: ReactFocusEvent<HTMLDivElement>) => void;
};

export type AlertBellController = {
  containerRef: React.MutableRefObject<HTMLDivElement | null>;
  containerHandlers: AlertBellContainerHandlers;
  triggerProps: AlertBellTriggerProps;
  panelProps: AlertBellPanelProps;
  isOpen: boolean;
};

export const useAlertBellController = (): AlertBellController => {
  const containerId = useId();
  const router = useRouter();
  const pathname = usePathname();

  const { data: dashboardData, isLoading, isError } = useDashboardOverview();
  const {
    data: alertRulesData,
    isLoading: isRulesLoading,
    isError: isRulesError,
  } = useAlertRules();
  const updateAlertMutation = useUpdateAlertRule();
  const deleteAlertMutation = useDeleteAlertRule();
  const showToast = useToastStore((state) => state.show);
  const { requestUpgrade } = usePlanUpgrade();

  const sessions = useChatStore((state) => state.sessions);
  const activeSession = useChatStore(selectActiveSession);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const createSession = useChatStore((state) => state.createSession);

  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const [builderMode, setBuilderMode] = useState<BuilderMode>("create");
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [hasFocusWithin, setHasFocusWithin] = useState(false);
  const [mutatingRuleId, setMutatingRuleId] = useState<string | null>(null);

  const closeTimerRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const builderReturnFocusRef = useRef<{ node: HTMLElement | null; key?: string }>({ node: null, key: undefined });

  const alerts = useMemo(() => dashboardData?.alerts ?? [], [dashboardData?.alerts]);
  const visibleAlerts = useMemo(() => alerts.slice(0, ALERT_LIMIT), [alerts]);
  const userAlertRules = useMemo(() => alertRulesData?.items ?? [], [alertRulesData?.items]);
  const alertPlan = alertRulesData?.plan ?? null;
  const alertPlanChannels = alertPlan?.channels ?? [];
  const planTierKey = parsePlanTier(alertPlan?.planTier);
  const planCopy = alertPlan ? getPlanCopy(planTierKey) : UNKNOWN_PLAN_COPY;
  const builderCopy = planCopy.builder;
  const bellCopy = planCopy.bell;
  const alertChannelSummary = alertPlanChannels.length ? alertPlanChannels.join(", ") : "허용된 채널이 없습니다";
  const maxRules = alertPlan?.maxAlerts ?? 0;
  const remainingSlots = alertPlan?.remainingAlerts ?? Math.max(maxRules - userAlertRules.length, 0);
  const quotaInfo = useMemo(
    () => ({
      remaining: remainingSlots,
      max: maxRules,
    }),
    [remainingSlots, maxRules],
  );
  const builderQuotaReached = maxRules > 0 && remainingSlots <= 0;
  const builderCtaLabel = isBuilderOpen && builderMode === "create" ? "빌더 닫기" : "새 알림 만들기";
  const isBuilderDisabled = !alertPlan || (builderMode === "create" && builderQuotaReached);
  const builderDisabledReason = !alertPlan ? UNKNOWN_PLAN_COPY.builder.disabledTooltip : builderCopy.disabledTooltip;
  const builderDisabledHint = !alertPlan ? UNKNOWN_PLAN_COPY.builder.disabledHint : builderCopy.disabledHint;

  const resetBuilderReturnFocus = useCallback(() => {
    builderReturnFocusRef.current = { node: null, key: undefined };
  }, []);

  const restoreFocusToReturnTarget = useCallback(() => {
    if (typeof window === "undefined") {
      resetBuilderReturnFocus();
      return;
    }

    const { node, key } = builderReturnFocusRef.current;
    const focusElement = (element: HTMLElement | null) => {
      if (element && element.isConnected) {
        element.focus();
        resetBuilderReturnFocus();
        return true;
      }
      return false;
    };

    if (focusElement(node)) {
      return;
    }

    window.requestAnimationFrame(() => {
      if (key) {
        const nextTarget = document.querySelector<HTMLElement>(`[data-focus-return="${key}"]`);
        if (focusElement(nextTarget)) {
          return;
        }
      } else {
        focusElement(node);
      }
      resetBuilderReturnFocus();
    });
  }, [resetBuilderReturnFocus]);

  const isOpen = isPinned || isHovering || hasFocusWithin;
  const badgeValue = alerts.length > 9 ? "10+" : alerts.length.toString();
  const showBadge = alerts.length > 0;

  const otherSessions = useMemo(
    () => sessions.filter((session) => session.id !== activeSessionId).slice(0, 3),
    [sessions, activeSessionId],
  );

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

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
  }, [clearCloseTimer, isPinned]);

  useEffect(() => {
    return () => {
      clearCloseTimer();
    };
  }, [clearCloseTimer]);

  const handlePointerEnter = useCallback(() => {
    clearCloseTimer();
    setIsHovering(true);
  }, [clearCloseTimer]);

  const handlePointerLeave = useCallback(() => {
    setIsHovering(false);
    requestClose();
  }, [requestClose]);

  const handleFocusIn = useCallback(() => {
    clearCloseTimer();
    setHasFocusWithin(true);
  }, [clearCloseTimer]);

  const handleFocusOut = useCallback(
    (event: ReactFocusEvent<HTMLDivElement>) => {
      const nextTarget = event.relatedTarget as HTMLElement | null;
      if (nextTarget && containerRef.current?.contains(nextTarget)) {
        return;
      }
      setHasFocusWithin(false);
      requestClose();
    },
    [requestClose],
  );

  const closeBuilder = useCallback(
    (shouldRestoreFocus: boolean) => {
      setIsBuilderOpen(false);
      setEditingRule(null);
      setBuilderMode("create");
      if (shouldRestoreFocus) {
        restoreFocusToReturnTarget();
      } else {
        resetBuilderReturnFocus();
      }
    },
    [resetBuilderReturnFocus, restoreFocusToReturnTarget],
  );

  const openBuilder = useCallback(
    (mode: BuilderMode, rule: AlertRule | null, trigger?: HTMLElement | null) => {
      builderReturnFocusRef.current = {
        node: trigger ?? null,
        key: trigger?.getAttribute("data-focus-return") ?? undefined,
      };
      setBuilderMode(mode);
      setEditingRule(rule);
      setIsBuilderOpen(true);
      setIsPinned(true);
    },
    [],
  );

  const closeImmediately = useCallback(() => {
    clearCloseTimer();
    setIsPinned(false);
    setIsHovering(false);
    setHasFocusWithin(false);
    closeBuilder(false);
  }, [clearCloseTimer, closeBuilder]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        closeImmediately();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeImmediately, isOpen]);

  const handleTriggerClick = useCallback(() => {
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
  }, [clearCloseTimer, closeImmediately]);

  const handleTriggerKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleTriggerClick();
      }
    },
    [handleTriggerClick],
  );

  const handleTogglePin = useCallback(() => {
    setIsPinned((prev) => {
      if (prev) {
        requestClose();
        return false;
      }
      clearCloseTimer();
      setHasFocusWithin(true);
      return true;
    });
  }, [clearCloseTimer, requestClose]);

  const pushRoute = useCallback(
    (path: string) => {
      router.push(path as never);
    },
    [router],
  );

  const handleAlertNavigate = useCallback(
    (alert: DashboardAlert) => {
      const target = alert.targetUrl?.trim();
      if (target) {
        if (/^https?:\/\//i.test(target)) {
          window.open(target, "_blank", "noopener,noreferrer");
        } else if (pathname !== target) {
          pushRoute(target);
        }
        closeImmediately();
        return;
      }

      if (alert.title.includes("뉴스")) {
        pushRoute("/news");
      } else if (alert.title.includes("공시")) {
        pushRoute("/filings");
      } else if (pathname !== "/chat") {
        if (activeSessionId) {
          pushRoute(`/chat?session=${activeSessionId}`);
        } else {
          pushRoute("/chat");
        }
      }
      closeImmediately();
    },
    [activeSessionId, closeImmediately, pathname, pushRoute],
  );

  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      void (async () => {
        await setActiveSession(sessionId);
        const chatPath = `/chat?session=${sessionId}`;
        if (pathname !== "/chat") {
          pushRoute(chatPath);
        } else {
          pushRoute(chatPath);
        }
        closeImmediately();
      })();
    },
    [closeImmediately, pathname, pushRoute, setActiveSession],
  );

  const handleStartNewSession = useCallback(() => {
    void (async () => {
      try {
        const sessionId = await createSession({ context: { type: "custom" } });
        await setActiveSession(sessionId);
        pushRoute(`/chat?session=${sessionId}`);
        closeImmediately();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "새 대화를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.";
        window.alert(message);
      }
    })();
  }, [closeImmediately, createSession, pushRoute, setActiveSession]);

  const handleToggleRule = useCallback(
    (rule: AlertRule) => {
      const nextStatus = rule.status === "active" ? "paused" : "active";
      setMutatingRuleId(rule.id);
      void (async () => {
        try {
          await updateAlertMutation.mutateAsync({ id: rule.id, payload: { status: nextStatus } });
          showToast({
            title: nextStatus === "active" ? "알림 재개" : "알림 일시 중지",
            message: `${rule.name} 알림이 ${nextStatus === "active" ? "활성화" : "일시 중지"}되었습니다.`,
            intent: "success",
          });
          logEvent("alerts.rule.status_changed", {
            ruleId: rule.id,
            nextStatus,
            planTier: planTierKey,
          });
        } catch (error) {
          let message = "요청을 처리하지 못했습니다.";
          if (error instanceof ApiError) {
            if (error.code === "plan.quota_exceeded") {
              showToast({
                title: bellCopy.quotaToast.title,
                message: bellCopy.quotaToast.description(quotaInfo),
                intent: "warning",
              });
              return;
            }
            message = error.message;
          } else if (error instanceof Error) {
            message = error.message;
          }
          showToast({
            title: "알림 상태를 변경할 수 없습니다",
            message,
            intent: "error",
          });
        } finally {
          setMutatingRuleId(null);
        }
      })();
    },
    [bellCopy.quotaToast, planTierKey, quotaInfo, showToast, updateAlertMutation],
  );

  const handleOpenCreateBuilder = useCallback(
    (trigger?: HTMLElement | null) => {
      if (isBuilderDisabled) {
        const copy = !alertPlan ? UNKNOWN_PLAN_COPY.builder : builderCopy;
        showToast({
          title: copy.quotaToast.title,
          message: copy.quotaToast.description(quotaInfo),
          intent: "warning",
        });
        return;
      }
      if (isBuilderOpen && builderMode === "create") {
        closeBuilder(true);
        return;
      }
      openBuilder("create", null, trigger ?? null);
    },
    [
      alertPlan,
      builderCopy,
      builderMode,
      closeBuilder,
      isBuilderDisabled,
      isBuilderOpen,
      openBuilder,
      quotaInfo,
      showToast,
    ],
  );

  const handleEditRule = useCallback(
    (rule: AlertRule, trigger?: HTMLElement | null) => {
      openBuilder("edit", rule, trigger ?? null);
    },
    [openBuilder],
  );

  const handleDuplicateRule = useCallback(
    (rule: AlertRule, trigger?: HTMLElement | null) => {
      openBuilder("duplicate", rule, trigger ?? null);
    },
    [openBuilder],
  );

  const handleDeleteRule = useCallback(
    (rule: AlertRule) => {
      setMutatingRuleId(rule.id);
      void (async () => {
        try {
          await deleteAlertMutation.mutateAsync(rule.id);
          showToast({
            title: "알림 삭제 완료",
            message: `${rule.name} 알림이 삭제되었습니다.`,
            intent: "success",
          });
          logEvent("alerts.rule.deleted", {
            ruleId: rule.id,
            planTier: planTierKey,
          });
        } catch (error) {
          let message = "알 수 없는 오류가 발생했습니다.";
          if (error instanceof ApiError) {
            if (error.code === "plan.locked_action") {
              message = "현재 플랜에서는 알림을 삭제할 수 없습니다.";
            } else {
              message = error.message;
            }
          } else if (error instanceof Error) {
            message = error.message;
          }
          showToast({
            title: "알림 삭제 실패",
            message,
            intent: "error",
          });
        } finally {
          setMutatingRuleId(null);
        }
      })();
    },
    [deleteAlertMutation, planTierKey, showToast],
  );

  const containerHandlers: AlertBellContainerHandlers = {
    onMouseEnter: handlePointerEnter,
    onMouseLeave: handlePointerLeave,
    onFocusCapture: handleFocusIn,
    onBlurCapture: handleFocusOut,
  };

  const triggerProps: AlertBellTriggerProps = {
    containerId,
    isOpen,
    isPinned,
    showBadge,
    badgeValue,
    onClick: handleTriggerClick,
    onKeyDown: handleTriggerKeyDown,
  };

  const panelProps: AlertBellPanelProps = {
    containerId,
    isPinned,
    onTogglePin: handleTogglePin,
    onClose: closeImmediately,
    builder: {
      isOpen: isBuilderOpen,
      mode: builderMode,
      editingRule,
      plan: alertPlan,
      existingCount: userAlertRules.length,
      ctaLabel: builderCtaLabel,
      isDisabled: isBuilderDisabled,
      disabledReason: builderDisabledReason,
      disabledHint: builderDisabledHint,
      quotaReached: builderQuotaReached,
      quotaInfo,
      copy: builderCopy,
      onOpenCreate: handleOpenCreateBuilder,
      onSuccess: () => closeBuilder(true),
      onCancel: () => closeBuilder(true),
      onRequestUpgrade: requestUpgrade,
    },
    planSummary: {
      alertPlan,
      alertChannelSummary,
      maxRules,
      remainingSlots,
      builderQuotaReached,
      builderMode,
      isBuilderDisabled,
      builderDisabledReason,
      builderDisabledHint,
      bellCopy,
      quotaInfo,
    },
    alerts: {
      alerts,
      visibleAlerts,
      isLoading,
      isError,
      onNavigate: handleAlertNavigate,
    },
    rules: {
      rules: userAlertRules,
      isLoading: isRulesLoading,
      isError: isRulesError,
      mutatingRuleId,
      builderMode,
      isBuilderOpen,
      editingRule,
      onEdit: handleEditRule,
      onDuplicate: handleDuplicateRule,
      onToggle: handleToggleRule,
      onDelete: handleDeleteRule,
    },
    chat: {
      activeSession,
      otherSessions,
      onSelect: handleSessionSelect,
      onStartNew: handleStartNewSession,
    },
  };

  return {
    containerRef,
    containerHandlers,
    triggerProps,
    panelProps,
    isOpen,
  };
};
