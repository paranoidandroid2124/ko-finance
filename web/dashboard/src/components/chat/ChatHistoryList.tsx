"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
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
  disabled,
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
    <aside className="hidden w-[260px] max-h-[calc(100vh-160px)] flex-shrink-0 flex-col gap-4 overflow-hidden rounded-3xl border border-white/5 bg-slate-900/30 p-4 text-sm text-slate-300 shadow-[0_20px_80px_rgba(8,15,40,0.65)] backdrop-blur-xl xl:flex">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.4em] text-slate-500">History</p>
          <p className="text-lg font-semibold text-white">대화 히스토리</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onNewSession}
            disabled={disabled}
            className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-300 transition hover:border-white/30 hover:text-white disabled:opacity-50"
            aria-label="새 세션"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={openClearAll}
            disabled={disabled || isEmpty}
            className="rounded-2xl border border-white/5 bg-white/0 p-2 text-slate-500 transition hover:border-rose-400/60 hover:text-rose-300 disabled:opacity-40"
            aria-label="전체 삭제"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      {persistenceError ? (
        <p className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{persistenceError}</p>
      ) : null}
      <div className="flex-1 min-h-0 space-y-2 overflow-y-auto pr-1">
        {showLoadingState ? (
          <p className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-xs text-slate-400">
            대화 기록을 불러오고 있습니다...
          </p>
        ) : isEmpty ? (
          <p className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-xs text-slate-500">
            아직 생성된 대화가 없습니다.
          </p>
        ) : (
          sessions.map((session) => {
            const isActive = selectedId === session.id;
            const baseClasses =
              "w-full rounded-2xl border px-4 py-3 text-left transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50";
            const palette = isActive
              ? "border-blue-500/40 bg-blue-500/10 text-white shadow-lg shadow-blue-500/30"
              : "border-white/5 text-slate-300 hover:border-white/20 hover:bg-white/5";
            return (
              <div key={session.id} className="group relative flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onSelect?.(session.id)}
                  className={`${baseClasses} ${palette}`}
                  disabled={disabled}
                >
                  <p className="font-semibold">{session.title}</p>
                  <p className="text-[11px] text-slate-400">{renderUpdatedAt(session.updatedAt)}</p>
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    openDelete(session);
                  }}
                  disabled={disabled}
                  aria-label="세션 삭제"
                  className="rounded-2xl border border-white/5 bg-white/0 p-2 text-slate-500 opacity-0 transition hover:border-rose-400/60 hover:text-rose-300 group-hover:opacity-100 disabled:opacity-20"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>
      {confirm && (
        <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-sm rounded-3xl border border-white/10 bg-[#050a1c]/95 p-6 text-sm text-slate-200 shadow-[0_40px_120px_rgba(4,7,15,0.85)] backdrop-blur-2xl">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{confirm.type === "clear" ? "Clear All" : "Delete Session"}</p>
            <h4 className="mt-2 text-xl font-semibold text-white">{confirm.type === "clear" ? "모든 세션 삭제" : "세션 삭제"}</h4>
            <p className="mt-3 text-sm text-slate-400">
              {confirm.type === "clear"
                ? "저장된 모든 대화를 삭제할까요? 이 작업은 되돌릴 수 없습니다."
                : `"${confirm.title}" 세션을 삭제할까요?`}
            </p>
            <div className="mt-6 flex justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={handleCancel}
                className="rounded-full border border-white/10 px-4 py-2 text-slate-400 transition hover:border-white/40 hover:text-white"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="rounded-full border border-rose-500/40 bg-rose-500/20 px-4 py-2 font-semibold text-rose-100 transition hover:bg-rose-500/30"
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
