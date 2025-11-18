"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  useAlertEventMatches,
  useAlertRules,
  useDeleteAlertRule,
  useUpdateAlertRule,
} from "@/hooks/useAlerts";
import {
  ApiError,
  type AlertEventMatch,
  type AlertPlanInfo,
  type AlertRule,
  type WatchlistRuleDetail,
} from "@/lib/alertsApi";
import { convertAlertRuleToDetail } from "@/components/watchlist/ruleDetail";
import { useToastStore } from "@/store/toastStore";

type WizardState = {
  open: boolean;
  mode: "create" | "edit";
  initialRule: WatchlistRuleDetail | null;
};

type MatchesState = {
  matches: AlertEventMatch[];
  isLoading: boolean;
  errorMessage: string | null;
};

type AlertsControllerOptions = {
  recentEventsLimit: number;
};

export type AlertsWatchlistController = {
  plan: AlertPlanInfo | null;
  totalRules: number;
  rules: AlertRule[];
  rulesLoading: boolean;
  rulesError: boolean;
  rulesErrorValue: unknown;
  matchesState: MatchesState;
  wizardState: WizardState;
  simulationRule: AlertRule | null;
  mutatingRuleId: string | null;
  actions: {
    openWizard: () => void;
    closeWizard: () => void;
    editRule: (rule: AlertRule) => void;
    completeWizard: (rule: AlertRule) => void;
    toggleRule: (rule: AlertRule) => Promise<void>;
    deleteRule: (rule: AlertRule) => Promise<void>;
    simulateRule: (rule: AlertRule) => void;
    clearSimulation: () => void;
  };
};

export function useWatchlistAlertsController({
  recentEventsLimit,
}: AlertsControllerOptions): AlertsWatchlistController {
  const showToast = useToastStore((state) => state.show);
  const alertRulesQuery = useAlertRules();
  const matchesQuery = useAlertEventMatches({ limit: recentEventsLimit });
  const updateRuleMutation = useUpdateAlertRule();
  const deleteRuleMutation = useDeleteAlertRule();

  const [localRules, setLocalRules] = useState<AlertRule[]>([]);
  const [mutatingRuleId, setMutatingRuleId] = useState<string | null>(null);
  const [wizardState, setWizardState] = useState<WizardState>({
    open: false,
    mode: "create",
    initialRule: null,
  });
  const [simulationRule, setSimulationRule] = useState<AlertRule | null>(null);

  useEffect(() => {
    setLocalRules(alertRulesQuery.data?.items ?? []);
  }, [alertRulesQuery.data?.items]);

  const matches = matchesQuery.data?.matches ?? [];
  const matchesErrorMessage = matchesQuery.error
    ? matchesQuery.error instanceof ApiError
      ? matchesQuery.error.message
      : matchesQuery.error instanceof Error
        ? matchesQuery.error.message
        : "ìµœê·¼ ì´ë²¤íŠ¸ë¥¼ ë¶ˆëŸ¬ì˜¤ì§€ ëª»í–ˆì–´ìš”."
    : null;

  const matchesState: MatchesState = useMemo(
    () => ({
      matches,
      isLoading: matchesQuery.isLoading,
      errorMessage: matchesErrorMessage,
    }),
    [matches, matchesErrorMessage, matchesQuery.isLoading],
  );

  const openWizard = useCallback(() => {
    setWizardState({ open: true, mode: "create", initialRule: null });
  }, []);

  const closeWizard = useCallback(() => {
    setWizardState({ open: false, mode: "create", initialRule: null });
  }, []);

  const editRule = useCallback((rule: AlertRule) => {
    setWizardState({
      open: true,
      mode: "edit",
      initialRule: convertAlertRuleToDetail(rule),
    });
  }, []);

  const completeWizard = useCallback(
    (rule: AlertRule) => {
      setLocalRules((prev) => {
        const exists = prev.some((item) => item.id === rule.id);
        if (exists) {
          return prev.map((item) => (item.id === rule.id ? rule : item));
        }
        return [rule, ...prev];
      });
      setSimulationRule(rule);
      void alertRulesQuery.refetch();
    },
    [alertRulesQuery],
  );

  const toggleRule = useCallback(
    async (rule: AlertRule) => {
      const nextStatus = rule.status === "active" ? "paused" : "active";
      setMutatingRuleId(rule.id);
      try {
        await updateRuleMutation.mutateAsync({
          id: rule.id,
          payload: { status: nextStatus },
        });
        showToast({
          intent: "success",
          message:
            nextStatus === "active"
              ? "ì•Œë¦¼ì„ ë‹¤ì‹œ í™œì„±í™”í–ˆìŠµë‹ˆë‹¤."
              : "ì•Œë¦¼ì„ ì¼ì‹œ ì¤‘ì§€í–ˆìŠµë‹ˆë‹¤.",
        });
        setLocalRules((prev) =>
          prev.map((item) =>
            item.id === rule.id ? { ...item, status: nextStatus } : item,
          ),
        );
        void alertRulesQuery.refetch();
      } catch (cause) {
        const message =
          cause instanceof ApiError
            ? cause.message
            : cause instanceof Error
              ? cause.message
              : "ì•Œë¦¼ ìƒíƒœë¥¼ ë³€ê²½í•˜ì§€ ëª»í–ˆì–´ìš”.";
        showToast({ intent: "error", message });
      } finally {
        setMutatingRuleId(null);
      }
    },
    [alertRulesQuery, showToast, updateRuleMutation],
  );

  const deleteRule = useCallback(
    async (rule: AlertRule) => {
      setMutatingRuleId(rule.id);
      try {
        await deleteRuleMutation.mutateAsync(rule.id);
        showToast({
          intent: "success",
          message: `${rule.name} ì•Œë¦¼ì„ ì‚­ì œí–ˆìŠµë‹ˆë‹¤.`,
        });
        setLocalRules((prev) => prev.filter((item) => item.id !== rule.id));
        void alertRulesQuery.refetch();
      } catch (cause) {
        const message =
          cause instanceof ApiError
            ? cause.message
            : cause instanceof Error
              ? cause.message
              : "ì•Œë¦¼ì„ ì‚­ì œí•˜ì§€ ëª»í–ˆì–´ìš”.";
        showToast({ intent: "error", message });
      } finally {
        setMutatingRuleId(null);
      }
    },
    [alertRulesQuery, deleteRuleMutation, showToast],
  );

  const simulateRule = useCallback((rule: AlertRule) => {
    setSimulationRule(rule);
  }, []);

  const clearSimulation = useCallback(() => {
    setSimulationRule(null);
  }, []);

  return {
    plan: alertRulesQuery.data?.plan ?? null,
    totalRules: localRules.length,
    rules: localRules,
    rulesLoading: alertRulesQuery.isLoading,
    rulesError: Boolean(alertRulesQuery.error),
    rulesErrorValue: alertRulesQuery.error,
    matchesState,
    wizardState,
    simulationRule,
    mutatingRuleId,
    actions: {
      openWizard,
      closeWizard,
      editRule,
      completeWizard,
      toggleRule,
      deleteRule,
      simulateRule,
      clearSimulation,
    },
  };
}
