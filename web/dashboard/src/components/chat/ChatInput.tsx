"use client";

import { useEffect, useRef, useState } from "react";
import { ChatInputDisclaimer } from "@/components/legal";

export type ChatInputProps = {
  onSubmit?: (message: string) => void;
  disabled?: boolean;
};

const QUICK_COMMANDS = [
  { label: "최근 분석 비교", value: "/compare recent analysis" },
  { label: "LightMem 상태", value: "/memory status" },
];

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value.trim()) return;
    onSubmit?.(value.trim());
    setValue("");
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

  return (
    <div className="space-y-3" data-onboarding-id="chat-input">
      {!disabled && (
        <div className="flex flex-wrap gap-2 text-[11px]">
          {QUICK_COMMANDS.map((command) => (
            <button
              key={command.value}
              type="button"
              onClick={() => handleCommandInsert(command.value)}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-white/40 hover:text-white"
            >
              {command.label}
              <span className="ml-2 text-[10px] text-cyan-300/80">{command.value}</span>
            </button>
          ))}
        </div>
      )}
      <form
        onSubmit={handleSubmit}
        className="relative flex items-center gap-3 rounded-full border border-white/15 bg-[#0f1c2f]/80 px-5 py-2 shadow-[0_20px_60px_rgba(3,7,18,0.5)] backdrop-blur-2xl focus-within:border-blue-500/40 focus-within:ring-2 focus-within:ring-blue-500/10"
      >
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          ref={textareaRef}
          placeholder="질문을 입력하면 공시 기반 분석을 바로 제공합니다..."
          className="min-h-[48px] flex-1 resize-none bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-blue-600/40 transition hover:scale-105 hover:from-blue-500 hover:to-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          전송
        </button>
      </form>
      <ChatInputDisclaimer className="text-center text-[10px] text-slate-500" />
    </div>
  );
}
