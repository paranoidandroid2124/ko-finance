"use client";

import clsx from "classnames";

type SpinnerProps = {
  className?: string;
};

export const formatJsonValue = (value: unknown, fallback = "{}") => {
  try {
    return JSON.stringify(value ?? JSON.parse(fallback), null, 2);
  } catch {
    return fallback;
  }
};

export const parseJsonRecord = (value: string, label: string) => {
  const text = value.trim();
  if (!text) {
    return {};
  }
  const parsed = JSON.parse(text);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label}는 객체 형태여야 해요.`);
  }
  return parsed as Record<string, unknown>;
};

export const AdminButtonSpinner = ({ className }: SpinnerProps) => (
  <span
    aria-hidden="true"
    className={clsx("inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-transparent", className)}
  />
);

export const AdminSuccessIcon = ({ className }: SpinnerProps) => (
  <svg
    aria-hidden="true"
    viewBox="0 0 20 20"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    className={clsx("h-3.5 w-3.5", className)}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 10.5 8.5 15 16 5" />
  </svg>
);
