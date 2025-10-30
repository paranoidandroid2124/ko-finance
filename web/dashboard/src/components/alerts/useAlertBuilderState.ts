import { useCallback, useMemo, useReducer, useRef } from "react";

import type { AlertRule } from "@/lib/alertsApi";
import type { BuilderMode } from "./channelForm";

export const DEFAULT_NEWS_SENTIMENT = "0.2";

export type AlertBuilderFormState = {
  name: string;
  description: string;
  conditionType: "filing" | "news";
  tickers: string;
  categories: string;
  sectors: string;
  minSentiment: string;
  evaluationMinutes: number;
  windowMinutes: number;
  cooldownMinutes: number;
  maxTriggersPerDay: string;
};

type AlertBuilderFormAction =
  | { type: "hydrate"; snapshot: AlertBuilderFormState }
  | { type: "set"; field: keyof AlertBuilderFormState; value: AlertBuilderFormState[keyof AlertBuilderFormState] };

const cloneFormState = (state: AlertBuilderFormState): AlertBuilderFormState => ({ ...state });

const reducer = (state: AlertBuilderFormState, action: AlertBuilderFormAction): AlertBuilderFormState => {
  switch (action.type) {
    case "hydrate":
      return cloneFormState(action.snapshot);
    case "set":
      if (state[action.field] === action.value) {
        return state;
      }
      return {
        ...state,
        [action.field]: action.value,
      } as AlertBuilderFormState;
    default: {
      return state;
    }
  }
};

export type BuildInitialFormStateArgs = {
  editingRule: AlertRule | null;
  mode: BuilderMode;
  defaultEvaluationInterval: number;
  defaultWindowMinutes: number;
  defaultCooldownMinutes: number;
  planDailyCap?: number;
};

export const buildInitialFormState = ({
  editingRule,
  mode,
  defaultEvaluationInterval,
  defaultWindowMinutes,
  defaultCooldownMinutes,
  planDailyCap,
}: BuildInitialFormStateArgs): AlertBuilderFormState => {
  if (editingRule) {
    const conditionType = (editingRule.condition?.type as "filing" | "news") ?? "filing";
    const maxTriggers =
      editingRule.maxTriggersPerDay !== null && editingRule.maxTriggersPerDay !== undefined
        ? String(editingRule.maxTriggersPerDay)
        : planDailyCap
        ? String(planDailyCap)
        : "";
    const minSentiment =
      conditionType === "news" && editingRule.condition?.minSentiment !== undefined
        ? String(editingRule.condition.minSentiment)
        : DEFAULT_NEWS_SENTIMENT;
    return {
      name: mode === "duplicate" ? `${editingRule.name} (복사본)` : editingRule.name,
      description: editingRule.description ?? "",
      conditionType,
      tickers: editingRule.condition?.tickers?.join(", ") ?? "",
      categories: editingRule.condition?.categories?.join(", ") ?? "",
      sectors: editingRule.condition?.sectors?.join(", ") ?? "",
      minSentiment,
      evaluationMinutes: editingRule.evaluationIntervalMinutes ?? defaultEvaluationInterval,
      windowMinutes: editingRule.windowMinutes ?? defaultWindowMinutes,
      cooldownMinutes: editingRule.cooldownMinutes ?? defaultCooldownMinutes,
      maxTriggersPerDay: maxTriggers,
    };
  }

  return {
    name: "",
    description: "",
    conditionType: "filing",
    tickers: "",
    categories: "",
    sectors: "",
    minSentiment: DEFAULT_NEWS_SENTIMENT,
    evaluationMinutes: defaultEvaluationInterval,
    windowMinutes: defaultWindowMinutes,
    cooldownMinutes: defaultCooldownMinutes,
    maxTriggersPerDay: planDailyCap ? String(planDailyCap) : "",
  };
};

type UseAlertBuilderStateOptions = {
  initialState: AlertBuilderFormState;
};

type AlertBuilderStateActions = {
  setName: (value: string) => void;
  setDescription: (value: string) => void;
  setConditionType: (value: "filing" | "news") => void;
  setTickers: (value: string) => void;
  setCategories: (value: string) => void;
  setSectors: (value: string) => void;
  setMinSentiment: (value: string) => void;
  setEvaluationMinutes: (value: number) => void;
  setWindowMinutes: (value: number) => void;
  setCooldownMinutes: (value: number) => void;
  setMaxTriggersPerDay: (value: string) => void;
};

export type UseAlertBuilderStateResult = {
  state: AlertBuilderFormState;
  actions: AlertBuilderStateActions;
  applySnapshot: (snapshot: AlertBuilderFormState, options?: { asBaseline?: boolean }) => void;
  resetToBaseline: () => void;
};

export const useAlertBuilderState = ({ initialState }: UseAlertBuilderStateOptions): UseAlertBuilderStateResult => {
  const baselineRef = useRef<AlertBuilderFormState>(cloneFormState(initialState));
  const [state, dispatch] = useReducer(reducer, baselineRef.current);

  const hydrate = useCallback((snapshot: AlertBuilderFormState) => {
    dispatch({ type: "hydrate", snapshot });
  }, []);

  const applySnapshot = useCallback(
    (snapshot: AlertBuilderFormState, options?: { asBaseline?: boolean }) => {
      const cloned = cloneFormState(snapshot);
      hydrate(cloned);
      if (options?.asBaseline) {
        baselineRef.current = cloned;
      }
    },
    [hydrate],
  );

  const resetToBaseline = useCallback(() => {
    hydrate(baselineRef.current);
  }, [hydrate]);

  const setField = useCallback((field: keyof AlertBuilderFormState, value: AlertBuilderFormState[keyof AlertBuilderFormState]) => {
    dispatch({ type: "set", field, value });
  }, []);

  const actions = useMemo<AlertBuilderStateActions>(
    () => ({
      setName: (value) => setField("name", value),
      setDescription: (value) => setField("description", value),
      setConditionType: (value) => setField("conditionType", value),
      setTickers: (value) => setField("tickers", value),
      setCategories: (value) => setField("categories", value),
      setSectors: (value) => setField("sectors", value),
      setMinSentiment: (value) => setField("minSentiment", value),
      setEvaluationMinutes: (value) => setField("evaluationMinutes", value),
      setWindowMinutes: (value) => setField("windowMinutes", value),
      setCooldownMinutes: (value) => setField("cooldownMinutes", value),
      setMaxTriggersPerDay: (value) => setField("maxTriggersPerDay", value),
    }),
    [setField],
  );

  return {
    state,
    actions,
    applySnapshot,
    resetToBaseline,
  };
};
