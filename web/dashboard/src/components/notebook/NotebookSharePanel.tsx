"use client";

import { FormEvent, useState } from "react";
import { CalendarClock, Copy, EyeOff, Link, Lock, Trash2 } from "lucide-react";

import type { NotebookShare, NotebookShareCreatePayload } from "@/lib/notebookApi";
import { toast } from "@/store/toastStore";

type NotebookSharePanelProps = {
  notebookTitle?: string;
  shares: NotebookShare[];
  onCreate: (payload: NotebookShareCreatePayload) => Promise<void>;
  onRevoke: (shareId: string) => Promise<void>;
  busy?: boolean;
};

const TTL_OPTIONS: Array<{ label: string; minutes: number }> = [
  { label: "1시간", minutes: 60 },
  { label: "24시간", minutes: 1440 },
  { label: "7일", minutes: 10080 },
  { label: "30일", minutes: 43200 },
];

export function NotebookSharePanel({ notebookTitle, shares, onCreate, onRevoke, busy }: NotebookSharePanelProps) {
  const [ttl, setTtl] = useState(10080);
  const [password, setPassword] = useState("");
  const [hint, setHint] = useState("");

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    await onCreate({
      expiresInMinutes: ttl,
      password: password.trim() || undefined,
      passwordHint: hint.trim() || undefined,
      accessScope: "view",
    });
    setPassword("");
    setHint("");
  };

  const formatExpires = (value?: string | null) => {
    if (!value) {
      return "제한 없음";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString("ko-KR");
  };

  const copyLink = async (share: NotebookShare) => {
    const url = `${window.location.origin}/labs/notebook/share/${encodeURIComponent(share.token)}`;
    await navigator.clipboard.writeText(url);
    toast.show({ message: "공유 링크가 복사되었습니다.", intent: "success" });
  };

  return (
    <div className="space-y-4 rounded-xl border border-border-light/80 bg-background-base/60 p-4 dark:border-border-dark/60 dark:bg-background-cardDark/60">
      <div>
        <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">공유 링크</h3>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          {notebookTitle ? `"${notebookTitle}" 노트북을 외부와 공유합니다.` : "노트북을 선택하면 공유 옵션이 활성화됩니다."}
        </p>
      </div>
      <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          만료 시간
          <select
            value={ttl}
            onChange={(event) => setTtl(Number(event.target.value))}
            disabled={busy}
            className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
          >
            {TTL_OPTIONS.map((option) => (
              <option key={option.minutes} value={option.minutes}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          비밀번호 (선택)
          <input
            type="text"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="공유 링크 보호용"
            disabled={busy}
            className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
          />
        </label>
        <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          힌트 (선택)
          <input
            type="text"
            value={hint}
            onChange={(event) => setHint(event.target.value)}
            placeholder="수취인이 기억할 수 있는 힌트"
            disabled={busy}
            className="w-full rounded-lg border border-border-light bg-background-light px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
          />
        </label>
        <div className="md:col-span-3 flex justify-end">
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? "생성 중..." : "공유 링크 생성"}
          </button>
        </div>
      </form>
      <div className="space-y-2">
        {shares.length === 0 ? (
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">아직 생성된 공유 링크가 없습니다.</p>
        ) : (
          shares.map((share) => (
            <div key={share.id} className="rounded-lg border border-border-light/80 bg-background-light/80 px-3 py-2 text-sm shadow-sm dark:border-border-dark/60 dark:bg-background-dark/60">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 text-xs uppercase tracking-wide text-primary">
                  <Link className="h-3.5 w-3.5" /> {share.accessScope}
                </span>
                {share.passwordProtected ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                    <Lock className="h-3 w-3" /> 보호됨
                  </span>
                ) : null}
                {share.revokedAt ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-border-light/60 px-2 py-0.5 text-xs text-text-secondaryLight">
                    <EyeOff className="h-3 w-3" /> 비활성화
                  </span>
                ) : null}
                <div className="flex-1" />
                <button
                  type="button"
                  onClick={() => copyLink(share)}
                  className="inline-flex items-center gap-1 rounded-md border border-border-light px-2 py-1 text-xs text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                >
                  <Copy className="h-3.5 w-3.5" /> 복사
                </button>
                <button
                  type="button"
                  onClick={() => onRevoke(share.id)}
                  disabled={!!share.revokedAt}
                  className="inline-flex items-center gap-1 rounded-md border border-border-light px-2 py-1 text-xs text-red-400 transition hover:border-red-400 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-50 dark:border-border-dark dark:text-red-300"
                >
                  <Trash2 className="h-3.5 w-3.5" /> 폐기
                </button>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="h-3.5 w-3.5" />
                  만료: {formatExpires(share.expiresAt)}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Link className="h-3.5 w-3.5" />
                  토큰: {share.token.slice(0, 6)}...
                </span>
                {share.lastAccessedAt ? (
                  <span>최근 조회: {formatExpires(share.lastAccessedAt)}</span>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
