"use client";

import clsx from "classnames";
import { useCallback } from "react";
import { PlanLock } from "@/components/ui/PlanLock";
import type { PlanTier } from "@/store/planStore/types";

type PlanTrialBannerProps = {
  requiredTier?: PlanTier;
  currentTier?: PlanTier;
  title: string;
  description: string;
  errorMessage?: string | null;
  onUpgrade?: () => void;
  className?: string;
  children?: React.ReactNode;
};

export function PlanTrialBanner({
  requiredTier = "pro",
  currentTier,
  title,
  description,
  errorMessage,
  onUpgrade,
  className,
  children,
}: PlanTrialBannerProps) {
  const upgradeHandler = useCallback(() => {
    onUpgrade?.();
  }, [onUpgrade]);

  const planLockUpgradeHandler = useCallback(
    (_tier: PlanTier) => {
      upgradeHandler();
    },
    [upgradeHandler],
  );

  return (
    <div className={clsx("w-full max-w-3xl", className)}>
      <PlanLock
        requiredTier={requiredTier}
        currentTier={currentTier}
        title={title}
        description={description}
        onUpgrade={onUpgrade ? planLockUpgradeHandler : undefined}
      >
        {errorMessage ? (
          <p className="mt-3 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{errorMessage}</p>
        ) : null}
        {children}
      </PlanLock>
    </div>
  );
}
