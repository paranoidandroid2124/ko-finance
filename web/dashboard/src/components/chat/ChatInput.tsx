"use client";

import { useRef, useState } from "react";
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

  return (
    <div className="space-y-2">
      {!disabled && (
        <div className="flex flex-wrap gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
          {QUICK_COMMANDS.map((command) => (
            <button
              key={command.value}
              type="button"
              onClick={() => handleCommandInsert(command.value)}
              className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              {command.label}
              <span className="ml-2 text-[10px] text-primary/70">{command.value}</span>
            </button>
          ))}
        </div>
      )}
      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-3 rounded-xl border border-border-light bg-background-cardLight p-3 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark"
      >
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          ref={textareaRef}
          placeholder="질문을 입력하면 공시 내용을 기반으로 답변해 드립니다."
          className="min-h-[60px] flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-text-secondaryLight dark:placeholder:text-text-secondaryDark"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-primary/40"
        >
          전송
        </button>
      </form>
      <ChatInputDisclaimer className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark" />
    </div>
  );
}
