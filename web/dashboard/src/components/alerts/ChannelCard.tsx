import { useEffect, useMemo, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import clsx from "classnames";
import type { AlertChannelType } from "@/lib/alertsApi";
import type { ChannelConfigState } from "@/components/alerts/channelForm";
import type { ChannelValidationError } from "@/components/alerts/useChannelValidation";

type ChannelUIConfig = {
  placeholder?: string;
  helper?: string;
  templateOptions?: Array<{ value: string; label: string }>;
};

type ChannelCardProps = {
  channelKey: string;
  channelType: AlertChannelType;
  state: ChannelConfigState;
  requiresTarget: boolean;
  ui: ChannelUIConfig;
  errors?: ChannelValidationError;
  onToggle: (enabled: boolean) => void;
  onTargetChange: (value: string) => void;
  onTemplateChange: (value: string) => void;
  onMetadataChange: (key: string, value: string) => void;
  autoFocusTarget: boolean;
  onAutoFocusHandled: () => void;
};

export function ChannelCard({
  channelKey,
  channelType,
  state,
  requiresTarget,
  ui,
  errors,
  onToggle,
  onTargetChange,
  onTemplateChange,
  onMetadataChange,
  autoFocusTarget,
  onAutoFocusHandled,
}: ChannelCardProps) {
  const targetRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const templateOptions = ui.templateOptions ?? [{ value: "default", label: "기본" }];
  const helperText = ui.helper ?? "";
  const targetError = errors?.targets;
  const metadataErrors = errors?.metadata ?? {};
  const subjectError = metadataErrors.subject_template;
  const replyToError = metadataErrors.reply_to;
  const severityError = metadataErrors.severity;

  useEffect(() => {
    if (!autoFocusTarget || !state.enabled) {
      return;
    }
    const focusTarget = () => {
      const el = targetRef.current;
      if (!el) {
        onAutoFocusHandled();
        return;
      }
      el.focus();
      if (el instanceof HTMLTextAreaElement) {
        const length = el.value.length;
        el.setSelectionRange(length, length);
      }
      onAutoFocusHandled();
    };
    if (typeof window === "undefined") {
      focusTarget();
      return;
    }
    let frameOne: number | null = null;
    let frameTwo: number | null = null;
    frameOne = window.requestAnimationFrame(() => {
      if (prefersReducedMotion) {
        focusTarget();
        return;
      }
      frameTwo = window.requestAnimationFrame(focusTarget);
    });
    return () => {
      if (frameOne !== null) {
        window.cancelAnimationFrame(frameOne);
      }
      if (frameTwo !== null) {
        window.cancelAnimationFrame(frameTwo);
      }
    };
  }, [autoFocusTarget, onAutoFocusHandled, prefersReducedMotion, state.enabled]);

  const panelTransition = useMemo(
    () =>
      prefersReducedMotion
        ? { duration: 0 }
        : {
            type: "spring",
            stiffness: 220,
            damping: 28,
            mass: 1,
          },
    [prefersReducedMotion],
  );

  const hoverScale = useMemo(() => {
    if (prefersReducedMotion) {
      return undefined;
    }
    return { scale: state.enabled ? 1.012 : 1.005 };
  }, [prefersReducedMotion, state.enabled]);

  const betaBadge = useMemo(() => {
    if (channelType === "telegram") {
      return "텔레그램 Beta";
    }
    if (channelType === "email") {
      return "Email";
    }
    return "Beta";
  }, [channelType]);

  const targetInput = requiresTarget
    ? channelType === "email"
      ? (
        <input
          ref={targetRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={state.input}
          onChange={(event) => onTargetChange(event.target.value)}
          placeholder={ui.placeholder ?? "수신자 정보를 입력하세요."}
          className={clsx(
            "w-full rounded-lg border bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition dark:bg-background-cardDark dark:text-text-primaryDark",
            targetError
              ? "border-destructive focus:border-destructive dark:border-destructive"
              : "border-border-light/60 focus:border-primary dark:border-border-dark/60 dark:focus:border-primary.dark",
          )}
          aria-invalid={targetError ? "true" : undefined}
          aria-describedby={
            targetError
              ? `${channelKey}-target-error`
              : helperText
                ? `${channelKey}-target-helper`
                : undefined
          }
        />
        )
      : (
        <textarea
          ref={targetRef as React.RefObject<HTMLTextAreaElement>}
          value={state.input}
          onChange={(event) => onTargetChange(event.target.value)}
          placeholder={ui.placeholder ?? "수신 대상을 입력하세요."}
          rows={2}
          className={clsx(
            "w-full rounded-lg border bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition dark:bg-background-cardDark dark:text-text-primaryDark",
            targetError
              ? "border-destructive focus:border-destructive dark:border-destructive"
              : "border-border-light/60 focus:border-primary dark:border-border-dark/60 dark:focus:border-primary.dark",
          )}
          aria-invalid={targetError ? "true" : undefined}
          aria-describedby={
            targetError
              ? `${channelKey}-target-error`
              : helperText
                ? `${channelKey}-target-helper`
                : undefined
          }
        />
        )
    : null;

  return (
    <motion.div
      layout
      data-enabled={state.enabled}
      whileHover={hoverScale}
      transition={panelTransition}
      className={clsx(
        "rounded-lg border border-border-light/70 bg-white/80 p-3 shadow-sm transition-all dark:border-border-dark/70 dark:bg-background-cardDark",
        state.enabled ? "ring-1 ring-primary/40 dark:ring-primary.dark/50" : "opacity-90",
      )}
    >
      <label className="flex items-center justify-between gap-3 text-sm">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={state.enabled}
            onChange={(event) => onToggle(event.target.checked)}
          />
          <span className="font-semibold capitalize text-text-primaryLight dark:text-text-primaryDark">
            {channelKey}
          </span>
        </div>
        <span className="text-[11px] uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
          {betaBadge}
        </span>
      </label>

      <AnimatePresence initial={false}>
        {state.enabled ? (
          <motion.div
            key="channel-fields"
            layout
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto", marginTop: 8 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            transition={panelTransition}
            className="overflow-hidden"
          >
            <div className="space-y-2">
              {requiresTarget ? targetInput : null}
            </div>
            <AnimatePresence mode="wait">
              {targetError ? (
                <motion.p
                  key="target-error"
                  id={`${channelKey}-target-error`}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  aria-live="assertive"
                  className="mt-1 text-[11px] text-destructive"
                >
                  {targetError}
                </motion.p>
              ) : helperText ? (
                <motion.p
                  key="target-helper"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  id={`${channelKey}-target-helper`}
                  aria-live="polite"
                  className="mt-1 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark"
                >
                  {helperText}
                </motion.p>
              ) : null}
            </AnimatePresence>
            {templateOptions.length > 1 ? (
              <div className="space-y-1">
                <p className="text-xs font-medium text-text-secondaryLight dark:text-text-secondaryDark">알림 템플릿</p>
                <select
                  value={state.template}
                  onChange={(event) => onTemplateChange(event.target.value)}
                  className="w-full rounded-lg border border-border-light/60 bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary dark:border-border-dark/60 dark:bg-background-cardDark dark:text-text-primaryDark dark:focus:border-primary.dark"
                  aria-describedby={`${channelKey}-template-helper`}
                >
                  {templateOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <span id={`${channelKey}-template-helper`} className="sr-only">
                  템플릿 선택 시 미리 정의된 형식으로 알림이 발송됩니다.
                </span>
              </div>
            ) : null}
            {channelType === "email" ? (
              <div className="space-y-2">
                <div>
                  <input
                    type="text"
                    value={state.metadata.subject_template ?? ""}
                    onChange={(event) => onMetadataChange("subject_template", event.target.value)}
                    placeholder="제목 템플릿 (예: {message})"
                    className={clsx(
                      "w-full rounded-lg border bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition dark:bg-background-cardDark dark:text-text-primaryDark",
                      subjectError
                        ? "border-destructive focus:border-destructive dark:border-destructive"
                        : "border-border-light/60 focus:border-primary dark:border-border-dark/60 dark:focus:border-primary.dark",
                    )}
                    aria-invalid={subjectError ? "true" : undefined}
                    aria-describedby={subjectError ? `${channelKey}-subject-error` : undefined}
                    aria-label="이메일 제목 템플릿"
                  />
                  {subjectError ? (
                    <p id={`${channelKey}-subject-error`} className="mt-1 text-[11px] text-destructive" aria-live="assertive">
                      {subjectError}
                    </p>
                  ) : null}
                </div>
                <div>
                  <input
                    type="email"
                    value={state.metadata.reply_to ?? ""}
                    onChange={(event) => onMetadataChange("reply_to", event.target.value)}
                    placeholder="Reply-To (선택 입력)"
                    className={clsx(
                      "w-full rounded-lg border bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition dark:bg-background-cardDark dark:text-text-primaryDark",
                      replyToError
                        ? "border-destructive focus:border-destructive dark:border-destructive"
                        : "border-border-light/60 focus:border-primary dark:border-border-dark/60 dark:focus:border-primary.dark",
                    )}
                    aria-invalid={replyToError ? "true" : undefined}
                    aria-describedby={replyToError ? `${channelKey}-reply-error` : undefined}
                    aria-label="Reply-To 이메일 주소"
                  />
                  {replyToError ? (
                    <p id={`${channelKey}-reply-error`} className="mt-1 text-[11px] text-destructive" aria-live="assertive">
                      {replyToError}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}
            {channelType === "pagerduty" ? (
              <div className="space-y-1">
                <p className="text-xs font-medium text-text-secondaryLight dark:text-text-secondaryDark">중요도</p>
                <select
                  value={state.metadata.severity ?? "info"}
                  onChange={(event) => onMetadataChange("severity", event.target.value)}
                  className={clsx(
                    "w-full rounded-lg border bg-white/80 px-3 py-2 text-sm text-text-primaryLight outline-none transition dark:bg-background-cardDark dark:text-text-primaryDark",
                    severityError
                      ? "border-destructive focus:border-destructive dark:border-destructive"
                      : "border-border-light/60 focus:border-primary dark:border-border-dark/60 dark:focus:border-primary.dark",
                  )}
                  aria-invalid={severityError ? "true" : undefined}
                  aria-describedby={severityError ? `${channelKey}-severity-error` : undefined}
                  aria-label="PagerDuty 긴급도"
                >
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="error">Error</option>
                  <option value="critical">Critical</option>
                </select>
                {severityError ? (
                  <p id={`${channelKey}-severity-error`} className="text-[11px] text-destructive" aria-live="assertive">
                    {severityError}
                  </p>
                ) : null}
              </div>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}

