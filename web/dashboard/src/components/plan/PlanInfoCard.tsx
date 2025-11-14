"use client";

import clsx from "classnames";
import type { ReactNode } from "react";
import { PLAN_DESCRIPTIONS } from "@/constants/planMetadata";
import type { PlanTier } from "@/store/planStore/types";

type PlanInfoCardProps = {
  title: string;
  description?: string;
  loading?: boolean;
  className?: string;
  children?: ReactNode;
  planTier?: PlanTier;
};

export function PlanInfoCard({ title, description, loading = false, className, children, planTier }: PlanInfoCardProps) {
  const fallbackDescription = planTier ? PLAN_DESCRIPTIONS[planTier] : undefined;
  const body = description ?? fallbackDescription;

  return (
    <div
      className={clsx(
        "w-full max-w-3xl rounded-xl border border-dashed border-border-light/80 bg-white/80 p-6 text-sm text-text-secondaryLight shadow-card transition-colors dark:border-border-dark/70 dark:bg-background-cardDark/70 dark:text-text-secondaryDark",
        className,
      )}
    >
      <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</p>
      {loading ? (
        <div className="mt-4 space-y-2">
          <div className="h-3 w-3/5 animate-pulse rounded bg-border-light/80 dark:bg-border-dark/60" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-border-light/60 dark:bg-border-dark/40" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-border-light/40 dark:bg-border-dark/30" />
        </div>
      ) : body ? (
        <p className="mt-3 leading-relaxed">{body}</p>
      ) : null}
      {children ? <div className="mt-4 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{children}</div> : null}
    </div>
  );
}

