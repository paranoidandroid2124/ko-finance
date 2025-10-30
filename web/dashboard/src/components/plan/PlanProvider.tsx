"use client";

import { useEffect } from "react";
import { usePlanStore, type PlanContextPayload } from "@/store/planStore";

type PlanProviderProps = {
  children: React.ReactNode;
  initialPlan?: PlanContextPayload | null;
};

export function PlanProvider({ children, initialPlan }: PlanProviderProps) {
  const setPlanFromServer = usePlanStore((state) => state.setPlanFromServer);
  const fetchPlan = usePlanStore((state) => state.fetchPlan);
  const initialized = usePlanStore((state) => state.initialized);

  useEffect(() => {
    if (initialPlan) {
      setPlanFromServer(initialPlan);
      return;
    }
    if (initialized) {
      return;
    }
    const controller = new AbortController();
    fetchPlan({ signal: controller.signal }).catch(() => undefined);
    return () => controller.abort();
  }, [fetchPlan, initialPlan, initialized, setPlanFromServer]);

  return <>{children}</>;
}
