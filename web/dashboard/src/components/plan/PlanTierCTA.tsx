"use client";

import clsx from "classnames";
import Link from "next/link";
import { useMemo } from "react";

import type { PlanTier } from "@/store/planStore/types";
import type { PlanTierAction } from "@/config/planConfig";
import { usePlanUpgrade } from "@/hooks/usePlanUpgrade";

type PlanTierCTAProps = {
  tier: PlanTier;
  action?: PlanTierAction | null;
  className?: string;
  variant?: "primary" | "secondary";
  fullWidth?: boolean;
  unstyled?: boolean;
  onUpgrade?: (tier: PlanTier) => void;
  onBeforeUpgrade?: (tier: PlanTier) => void;
};

export function PlanTierCTA({
  tier,
  action,
  className,
  variant = "primary",
  fullWidth,
  unstyled = false,
  onUpgrade,
  onBeforeUpgrade,
}: PlanTierCTAProps) {
  const { requestUpgrade, isPreparing } = usePlanUpgrade();

  const baseClass = useMemo(
    () =>
      clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition",
        !unstyled &&
          (variant === "secondary"
            ? "border border-border-light text-text-primaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            : "bg-primary text-white hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed"),
        unstyled && "disabled:cursor-not-allowed",
        fullWidth && "w-full",
        className,
      ),
    [className, fullWidth, unstyled, variant],
  );

  if (!action) {
    return null;
  }

  if (action.action === "upgrade") {
    const targetTier = action.tier ?? tier;
    const handleUpgradeClick = async () => {
      onBeforeUpgrade?.(targetTier);
      if (onUpgrade) {
        onUpgrade(targetTier);
        return;
      }
      const redirectPath =
        typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/settings";
      await requestUpgrade(targetTier, { redirectPath });
    };

    return (
      <button
        type="button"
        className={baseClass}
        onClick={handleUpgradeClick}
        disabled={isPreparing}
        data-testid="plan-tier-cta-upgrade"
      >
        {isPreparing ? "진행 중..." : action.label}
      </button>
    );
  }

  const href = action.href ?? "/pricing";
  const isExternal = /^https?:\/\//i.test(href) || action.target === "_blank";

  if (isExternal) {
    return (
      <a
        href={href}
        target={action.target ?? "_blank"}
        rel="noreferrer"
        className={baseClass}
        data-testid="plan-tier-cta-link"
      >
        {action.label}
      </a>
    );
  }

  return (
    <Link href={href} target={action.target} className={baseClass} data-testid="plan-tier-cta-link">
      {action.label}
    </Link>
  );
}
