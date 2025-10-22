"use client";

import { useState } from "react";
import type { ChatSession } from "@/store/chatStore";

type Props = {
  sessions: ChatSession[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  onNewSession?: () => void;
  onDeleteSession?: (id: string) => void;
  onClearAll?: () => void;
  persistenceError?: string | null;
  disabled?: boolean;
};

type ConfirmState =
  | { type: "delete"; sessionId: string; title: string }
  | { type: "clear" }
  | null;

const renderUpdatedAt = (updatedAt: string) => `마지막 업데이트 · ${updatedAt}`;

export function ChatHistoryList({
  sessions,
  selectedId,
  onSelect,
  onNewSession,
  onDeleteSession,
  onClearAll,
  persistenceError,
  disabled
}: Props) {
  const [confirm, setConfirm] = useState<ConfirmState>(null);

  const handleConfirm = () => {
    if (!confirm) return;
    if (confirm.type === "delete" && confirm.sessionId) {
      onDeleteSession?.(confirm.sessionId);
    }
    if (confirm.type === "clear") {
      onClearAll?.();
    }
    setConfirm(null);
  };

  const handleCancel = () => setConfirm(null);

  const openDelete = (session: ChatSession) => {
    if (disabled) return;
    setConfirm({ type: "delete", sessionId: session.id, title: session.title });
  };

  const openClearAll = () => {
    if (disabled || sessions.length === 0) return;
    setConfirm({ type: "clear" });
  };

  const isEmpty = sessions.length === 0;
  const showLoadingState = Boolean(disabled && isEmpty);

  return (
    <aside className="hidden w-64 flex-none flex-col gap-3 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark xl:flex">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">대화 히스토리</h3>
            {persistenceError && (
              <span className="rounded-full bg-accent-negative/10 px-2 py-0.5 text-[10px] font-semibold text-accent-negative">
                저장 실패
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={openClearAll}
              disabled={disabled || isEmpty}
              className="rounded-md border border-border-light px-2 py-1 text-xs text-text-secondaryLight transition-colors hover:border-accent-negative hover:text-accent-negative disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-accent-negative.dark dark:hover:text-accent-negative.dark"
            >
              전체 삭제
            </button>
            <button
              type="button"
              onClick={onNewSession}
              disabled={disabled}
              className="rounded-md border border-border-light px-2 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              새 세션
            </button>
          </div>
        </div>
        {persistenceError && (
          <p className="text-xs text-accent-negative">{persistenceError}</p>
        )}
      </div>
      <div className="space-y-2 text-sm">
        {showLoadingState ? (
          <p className="rounded-lg border border-dashed border-border-light px-3 py-4 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            대화 기록을 불러오는 중입니다...
          </p>
        ) : isEmpty ? (
          <p className="rounded-lg border border-dashed border-border-light px-3 py-4 text-center text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 생성된 대화가 없습니다.
          </p>
        ) : (
          sessions.map((session) => (
            <div key={session.id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onSelect?.(session.id)}
                className={`flex-1 rounded-lg border px-3 py-2 text-left transition-colors ${
                  selectedId === session.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                }`}
                disabled={disabled}
              >
                <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">{session.title}</p>
                <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                  {renderUpdatedAt(session.updatedAt)}
                </p>
              </button>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  openDelete(session);
                }}
                disabled={disabled}
                className="rounded-md border border-border-light px-2 py-1 text-[11px] text-text-secondaryLight transition-colors hover:border-accent-negative hover:text-accent-negative disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-accent-negative.dark dark:hover:text-accent-negative.dark"
              >
                삭제
              </button>
            </div>
          ))
        )}
      </div>
      {confirm && (
        <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 text-sm shadow-xl dark:bg-background-cardDark">
            <h4 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {confirm.type === "clear" ? "모든 세션 삭제" : "세션 삭제"}
            </h4>
            <p className="mt-2 text-text-secondaryLight dark:text-text-secondaryDark">
              {confirm.type === "clear"
                ? "저장된 모든 대화를 삭제할까요? 이 작업은 되돌릴 수 없습니다."
                : `"${confirm.title}" 세션을 삭제할까요?`}
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={handleCancel}
                className="rounded-md border border-border-light px-3 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="rounded-md bg-accent-negative px-3 py-1 text-xs font-semibold text-white shadow hover:bg-accent-negative/90"
              >
                {confirm.type === "clear" ? "전체 삭제" : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
