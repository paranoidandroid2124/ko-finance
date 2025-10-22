"use client";

import { useState } from "react";

export type ChatInputProps = {
  onSubmit?: (message: string) => void;
  disabled?: boolean;
};

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value.trim()) return;
    onSubmit?.(value.trim());
    setValue("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 rounded-xl border border-border-light bg-background-cardLight p-3 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark"
    >
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
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
  );
}
