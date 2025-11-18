"use client";

import type { ReactNode } from "react";

import { PlanLock } from "@/components/ui/PlanLock";

import type { PlanTier } from "./types";

type PlanLockCTAProps = {
  currentTier: PlanTier;
  description: string;
  requiredTier?: PlanTier;
  onUpgrade?: (tier: PlanTier) => void;
  className?: string;
  children?: ReactNode;
};

export function PlanLockCTA({
  currentTier,
  description,
  requiredTier = "pro",
  onUpgrade,
  className,
  children,
}: PlanLockCTAProps) {
  return (
    <PlanLock
      requiredTier={requiredTier}
      currentTier={currentTier}
      description={description}
      onUpgrade={onUpgrade}
      className={className}
    >
      {children}
    </PlanLock>
  );
}

