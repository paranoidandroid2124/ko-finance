"use client";

import clsx from "classnames";
import Link from "next/link";

export type PaymentResultDetail = {
  label: string;
  value: string;
  emphasize?: boolean;
};

export type PaymentResultCardProps = {
  status: "success" | "confirming" | "error";
  title: string;
  description: string;
  details: PaymentResultDetail[];
  actionLabel: string;
  actionHref?: string;
  actionOnClick?: () => void;
  secondaryAction?: {
    label: string;
    href: string;
    external?: boolean;
  };
};

const STATUS_CLASSNAME: Record<PaymentResultCardProps["status"], string> = {
  success:
    "border-emerald-400/70 bg-emerald-50/60 text-emerald-900 dark:border-emerald-300/60 dark:bg-emerald-500/10 dark:text-emerald-100",
  confirming:
    "border-border-light bg-background-cardLight text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark",
  error:
    "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/70 dark:bg-destructive/15",
};

export function PaymentResultCard({
  status,
  title,
  description,
  details,
  actionLabel,
  actionHref,
  actionOnClick,
  secondaryAction,
}: PaymentResultCardProps) {
  const isActionButton = typeof actionOnClick === "function";

  return (
    <div
      className={clsx(
        "rounded-2xl border px-6 py-8 text-center shadow-card transition-colors",
        STATUS_CLASSNAME[status],
      )}
    >
      <h1 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>

      <dl className="mt-6 space-y-2 text-sm">
        {details.map((detail) => (
          <div key={detail.label} className="flex justify-between">
            <dt className="font-medium text-text-secondaryLight dark:text-text-secondaryDark">{detail.label}</dt>
            <dd
              className={clsx(
                "font-semibold text-text-primaryLight dark:text-text-primaryDark",
                detail.emphasize ? "font-semibold" : "font-medium",
              )}
            >
              {detail.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
        {isActionButton ? (
          <button
            type="button"
            onClick={actionOnClick}
            className={clsx(
              "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
              status === "error"
                ? "bg-white text-destructive shadow-sm hover:bg-destructive/10 focus-visible:outline-destructive dark:bg-destructive/20 dark:text-white dark:hover:bg-destructive/30"
                : "bg-primary text-white hover:bg-primary-hover focus-visible:outline-primary",
            )}
          >
            {actionLabel}
          </button>
        ) : (
          <Link
            href={actionHref ?? "#"}
            className={clsx(
              "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
              status === "error"
                ? "bg-white text-destructive shadow-sm hover:bg-destructive/10 focus-visible:outline-destructive dark:bg-destructive/20 dark:text-white dark:hover:bg-destructive/30"
                : "bg-primary text-white hover:bg-primary-hover focus-visible:outline-primary",
            )}
          >
            {actionLabel}
          </Link>
        )}
        {secondaryAction ? (
          <Link
            href={secondaryAction.href}
            target={secondaryAction.external ? "_blank" : undefined}
            rel={secondaryAction.external ? "noreferrer" : undefined}
            className="inline-flex items-center justify-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/30 dark:focus-visible:outline-border-dark"
          >
            {secondaryAction.label}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
