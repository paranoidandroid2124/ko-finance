"use client";

import type { ChatSession } from "@/store/chatStore";

type Props = {
  sessions: ChatSession[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  onNewSession?: () => void;
};

export function ChatHistoryList({ sessions, selectedId, onSelect, onNewSession }: Props) {
  return (
    <aside className="hidden w-64 flex-none flex-col gap-3 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark xl:flex">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">대화 히스토리</h3>
        <button
          type="button"
          onClick={onNewSession}
          className="rounded-md border border-border-light px-2 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          새 세션
        </button>
      </div>
      <div className="space-y-2 text-sm">
        {sessions.map((session) => (
          <button
            type="button"
            key={session.id}
            onClick={() => onSelect?.(session.id)}
            className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
              selectedId === session.id
                ? "border-primary bg-primary/10 text-primary"
                : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            }`}
          >
            <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">{session.title}</p>
            <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">{session.updatedAt}</p>
          </button>
        ))}
        {sessions.length === 0 && (
          <p className="rounded-lg border border-dashed border-border-light px-3 py-4 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 생성된 대화가 없습니다.
          </p>
        )}
      </div>
    </aside>
  );
}