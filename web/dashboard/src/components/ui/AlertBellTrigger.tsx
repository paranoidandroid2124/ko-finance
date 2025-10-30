"use client";

import type { AlertBellTriggerProps } from "./useAlertBellController";
import clsx from "classnames";
import { Bell, Pin } from "lucide-react";

export function AlertBellTrigger({
  containerId,
  isOpen,
  isPinned,
  showBadge,
  badgeValue,
  onClick,
  onKeyDown,
}: AlertBellTriggerProps) {
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      aria-controls={containerId}
      aria-label="실시간 소식 패널 열기"
      className={clsx(
        "relative h-10 w-10 rounded-full border border-border-light text-text-secondaryLight shadow-sm transition-transform duration-150 hover:scale-[1.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark",
        isOpen && "border-primary text-primary dark:border-primary.dark dark:text-primary.dark",
      )}
      onClick={onClick}
      onKeyDown={onKeyDown}
    >
      <Bell className="mx-auto h-5 w-5" aria-hidden />
      {showBadge ? (
        <span
          aria-hidden="true"
          className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-white shadow-sm"
        >
          {badgeValue}
        </span>
      ) : null}
      {isPinned ? <Pin className="absolute right-0 top-1 h-3 w-3 text-primary" aria-hidden /> : null}
    </button>
  );
}
