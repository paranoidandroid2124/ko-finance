"use client";

import { useEffect, useRef, useState } from "react";

export type ChatInputProps = {
  onSubmit?: (message: string) => void;
  disabled?: boolean;
  onFocusChange?: (focused: boolean) => void;
};

const QUICK_COMMANDS: Array<{ label: string; value: string }> = [];

export function ChatInput({ onSubmit, disabled, onFocusChange }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  const sendMessage = () => {
    if (disabled || !value.trim()) return;
    onSubmit?.(value.trim());
    setValue("");
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    sendMessage();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const handleCommandInsert = (command: string) => {
    setValue(command);
    textareaRef.current?.focus();
  };

  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ value: string }>).detail;
      if (detail?.value) {
        setValue(detail.value);
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("onboarding:prefill", listener as EventListener);
    return () => {
      window.removeEventListener("onboarding:prefill", listener as EventListener);
    };
  }, []);

  const toggleFocus = (focused: boolean) => {
    setIsFocused(focused);
    onFocusChange?.(focused);
  };

  return (
    <div className="space-y-3" data-onboarding-id="chat-input">
      {Boolean(QUICK_COMMANDS.length) && !disabled ? (
        <div className="flex flex-wrap gap-2 text-[11px]">
          {QUICK_COMMANDS.map((command) => (
            <button
              key={command.value}
              type="button"
              onClick={() => handleCommandInsert(command.value)}
              className="group relative overflow-hidden rounded-full border border-border-subtle bg-surface-2/70 px-3 py-1 text-[12px] font-semibold text-text-primary transition duration-200 hover:-translate-y-[1px] hover:border-primary/70 hover:text-text-primary"
            >
              <span
                className="pointer-events-none absolute inset-0 opacity-0 transition duration-200 group-hover:opacity-100"
                aria-hidden
                style={{
                  background:
                    "radial-gradient(circle at 20% 40%, rgba(88,166,255,0.22), transparent 52%)",
                }}
              />
              {command.label}
              <span className="ml-2 text-[10px] font-medium text-primary/80">{command.value}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="relative">
        <div
          aria-hidden
          className={`pointer-events-none absolute -inset-x-3 -inset-y-3 rounded-[28px] blur-2xl transition duration-500 ${isFocused ? "opacity-100" : "opacity-0"
            }`}
          style={{
            background: "radial-gradient(circle at 20% 20%, rgba(88,166,255,0.32), transparent 45%)",
          }}
        />
        <form
          onSubmit={handleSubmit}
          onFocusCapture={() => toggleFocus(true)}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              toggleFocus(false);
            }
          }}
          className="relative isolate flex items-start gap-3 rounded-[24px] border border-border-subtle bg-surface-2/80 px-4 py-3 shadow-card dark:shadow-[0_18px_48px_rgba(0,0,0,0.45)] ring-1 ring-border-hair/10 backdrop-blur-xl transition-all duration-300 focus-within:-translate-y-0.5 focus-within:border-primary/70 focus-within:shadow-glow-brand dark:focus-within:shadow-[0_24px_88px_rgba(88,166,255,0.28)] focus-within:ring-primary/20"
        >
          <div className="pointer-events-none absolute inset-0 rounded-[28px] border border-border-hair/5" aria-hidden />
          <textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            ref={textareaRef}
            placeholder="종목·이슈를 입력하면 공시·뉴스·시세 기반 분석을 바로 제공합니다. 예) “카카오 2023년 정정공시 이슈 정리해줘”"
            className="min-h-[64px] flex-1 resize-none bg-transparent text-base leading-relaxed text-text-primary outline-none placeholder:text-text-muted"
          />
          <button
            type="submit"
            disabled={disabled}
            className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full bg-gradient-to-r from-[#58A6FF] to-[#58A6FF] px-6 py-3 text-base font-semibold text-white shadow-[0_12px_42px_rgba(88,166,255,0.45)] transition duration-200 hover:-translate-y-[1px] hover:shadow-[0_16px_60px_rgba(88,166,255,0.65)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#58A6FF]/70 focus-visible:ring-offset-2 focus-visible:ring-offset-[#161B22] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span
              className="absolute inset-0 opacity-0 blur-2xl transition duration-200 group-hover:opacity-70"
              aria-hidden
              style={{
                background: "radial-gradient(circle at 30% 50%, rgba(255,255,255,0.22), transparent 55%)",
              }}
            />
            <span className="relative z-10">전송</span>
          </button>
        </form>
      </div>
      <p className="text-center text-[10px] text-slate-500">
        Nuvien AI Copilot의 답변은 참고용 일반 정보이며, 투자·법률·세무 자문이 아닙니다. 중요한 의사결정 전에는 반드시 원문과
        공시 자료를 확인해 주세요.
      </p>
    </div>
  );
}
