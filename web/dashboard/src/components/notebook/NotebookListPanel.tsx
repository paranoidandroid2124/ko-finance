"use client";

import { FormEvent, useMemo, useState } from "react";
import clsx from "clsx";
import { PlusCircle } from "lucide-react";

import type { NotebookCreatePayload, NotebookSummary } from "@/lib/notebookApi";

type NotebookListPanelProps = {
  notebooks: NotebookSummary[];
  activeId?: string | null;
  loading?: boolean;
  onSelect: (notebookId: string) => void;
  onCreate: (payload: NotebookCreatePayload) => Promise<void>;
};

export function NotebookListPanel({ notebooks, activeId, loading, onSelect, onCreate }: NotebookListPanelProps) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const grouped = useMemo(() => notebooks.slice().sort((a, b) => (b.lastActivityAt || "").localeCompare(a.lastActivityAt || "")), [notebooks]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onCreate({
        title: title.trim(),
        summary: summary.trim() || undefined,
        tags: tags
          .split(",")
          .map((token) => token.trim())
          .filter(Boolean),
      });
      setTitle("");
      setSummary("");
      setTags("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleCreate} className="rounded-xl border border-border-light bg-background-light/60 p-4 shadow-sm dark:border-border-dark dark:bg-background-dark/60">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
          <PlusCircle className="h-4 w-4 text-primary" />
          새 노트북
        </div>
        <div className="mt-3 space-y-2">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            placeholder="제목"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
          />
          <textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="요약 (선택)"
            rows={2}
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
          />
          <input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="태그를 콤마로 구분 (예: macro,earnings)"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
          />
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "생성 중..." : "생성"}
          </button>
        </div>
      </form>
      <div className="space-y-2">
        {loading ? (
          <div className="animate-pulse rounded-xl border border-border-light/80 bg-background-light/60 p-4 dark:border-border-dark/80 dark:bg-background-dark/60">
            <div className="h-4 w-3/4 rounded bg-border-light/70 dark:bg-border-dark/70" />
            <div className="mt-2 h-3 w-1/2 rounded bg-border-light/60 dark:bg-border-dark/60" />
          </div>
        ) : grouped.length === 0 ? (
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">생성된 노트북이 없습니다.</p>
        ) : (
          grouped.map((notebook) => {
            const isActive = notebook.id === activeId;
            return (
              <button
                key={notebook.id}
                type="button"
                onClick={() => onSelect(notebook.id)}
                className={clsx(
                  "w-full rounded-xl border px-4 py-3 text-left transition",
                  isActive
                    ? "border-primary bg-primary/10 text-primary shadow"
                    : "border-border-light bg-background-light/50 text-text-primaryLight hover:border-primary/60 hover:text-primary dark:border-border-dark dark:bg-background-dark/60 dark:text-text-primaryDark",
                )}
              >
                <div className="flex items-center justify-between text-sm font-semibold">
                  <span>{notebook.title}</span>
                  <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {notebook.entryCount}개 · {notebook.tags.slice(0, 3).join(", ")}
                  </span>
                </div>
                {notebook.summary ? (
                  <p className="mt-1 line-clamp-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{notebook.summary}</p>
                ) : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
