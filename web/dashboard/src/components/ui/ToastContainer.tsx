"use client";

import { useEffect } from "react";
import classNames from "classnames";
import { useToastStore, type ToastDescriptor, type ToastIntent } from "@/store/toastStore";

const intentStyles: Record<ToastIntent, string> = {
  info: "border border-border-light bg-white text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark",
  success: "border border-accent-positive/50 bg-accent-positive/10 text-accent-positive",
  warning: "border border-accent-warning/50 bg-accent-warning/10 text-accent-warning",
  error: "border border-accent-negative/50 bg-accent-negative/10 text-accent-negative"
};

type ToastItemProps = {
  toast: ToastDescriptor;
  onDismiss: (id: string) => void;
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  useEffect(() => {
    if (!toast.duration || toast.duration <= 0) {
      return;
    }
    const timer = window.setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => {
      window.clearTimeout(timer);
    };
  }, [onDismiss, toast.duration, toast.id]);

  return (
    <div
      className={classNames(
        "pointer-events-auto flex w-full flex-col gap-1 rounded-lg px-4 py-3 text-sm shadow-lg",
        intentStyles[toast.intent ?? "info"]
      )}
    >
      {toast.title && <p className="text-xs font-semibold uppercase tracking-wide">{toast.title}</p>}
      <p className="whitespace-pre-line leading-relaxed">{toast.message}</p>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (!toasts.length) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[1000] flex justify-center px-4 sm:justify-end sm:px-6">
      <div className="flex w-full max-w-sm flex-col gap-3">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </div>
  );
}
