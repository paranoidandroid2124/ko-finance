"use client";

import { useMemo, useState } from "react";
import { Pencil, Tag, Trash2 } from "lucide-react";

import { NotebookEntryComposer } from "@/components/notebook/NotebookEntryComposer";
import { NotebookListPanel } from "@/components/notebook/NotebookListPanel";
import { NotebookSharePanel } from "@/components/notebook/NotebookSharePanel";
import type {
  NotebookDetailResponse,
  NotebookEntry,
  NotebookEntryCreatePayload,
  NotebookEntryUpdatePayload,
  NotebookShare,
  NotebookShareCreatePayload,
  NotebookSummary,
  NotebookCreatePayload,
  NotebookUpdatePayload,
} from "@/lib/notebookApi";

type NotebookWorkspaceProps = {
  notebooks: NotebookSummary[];
  activeNotebook: NotebookDetailResponse | null;
  shares: NotebookShare[];
  loadingNotebooks?: boolean;
  loadingDetail?: boolean;
  onSelectNotebook: (notebookId: string) => void;
  onCreateNotebook: (payload: NotebookCreatePayload) => Promise<void>;
  onUpdateNotebook: (payload: NotebookUpdatePayload) => Promise<void>;
  onDeleteNotebook: () => Promise<void>;
  onCreateEntry: (payload: NotebookEntryCreatePayload) => Promise<void>;
  onUpdateEntry: (entryId: string, payload: NotebookEntryUpdatePayload) => Promise<void>;
  onDeleteEntry: (entryId: string) => Promise<void>;
  onCreateShare: (payload: NotebookShareCreatePayload) => Promise<void>;
  onRevokeShare: (shareId: string) => Promise<void>;
};

export function NotebookWorkspace({
  notebooks,
  activeNotebook,
  shares,
  loadingNotebooks,
  loadingDetail,
  onSelectNotebook,
  onCreateNotebook,
  onUpdateNotebook,
  onDeleteNotebook,
  onCreateEntry,
  onUpdateEntry,
  onDeleteEntry,
  onCreateShare,
  onRevokeShare,
}: NotebookWorkspaceProps) {
  const [editingMeta, setEditingMeta] = useState(false);
  const [pendingEntryId, setPendingEntryId] = useState<string | null>(null);
  const [metaDraft, setMetaDraft] = useState<NotebookUpdatePayload>({});

  const selectedId = activeNotebook?.notebook.id;
  const entries = useMemo(() => activeNotebook?.entries ?? [], [activeNotebook]);

  const handleMetaEdit = () => {
    if (!activeNotebook) {
      return;
    }
    setEditingMeta(true);
    setMetaDraft({
      title: activeNotebook.notebook.title,
      summary: activeNotebook.notebook.summary ?? "",
      tags: activeNotebook.notebook.tags,
    });
  };

  const handleMetaSubmit = async () => {
    await onUpdateNotebook(metaDraft);
    setEditingMeta(false);
  };

  const handleEntryUpdate = async (entryId: string, payload: NotebookEntryUpdatePayload) => {
    setPendingEntryId(entryId);
    try {
      await onUpdateEntry(entryId, payload);
    } finally {
      setPendingEntryId(null);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <NotebookListPanel notebooks={notebooks} activeId={selectedId} loading={loadingNotebooks} onSelect={onSelectNotebook} onCreate={onCreateNotebook} />
      <div className="space-y-6">
        {loadingDetail ? (
          <div className="space-y-3 rounded-2xl border border-border-light/80 bg-background-light/60 p-6 dark:border-border-dark/80 dark:bg-background-dark/60">
            <div className="h-6 w-1/3 rounded bg-border-light/70 dark:bg-border-dark/70" />
            <div className="h-4 w-2/3 rounded bg-border-light/60 dark:bg-border-dark/60" />
            <div className="h-32 rounded-xl border border-dashed border-border-light/70 dark:border-border-dark/70" />
          </div>
        ) : activeNotebook ? (
          <>
            <section className="space-y-4 rounded-2xl border border-border-light bg-background-light/60 p-6 shadow-sm dark:border-border-dark dark:bg-background-dark/60">
              {editingMeta ? (
                <div className="space-y-3">
                  <input
                    value={metaDraft.title ?? ""}
                    onChange={(event) => setMetaDraft((draft) => ({ ...draft, title: event.target.value }))}
                    className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-lg font-semibold text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                  <textarea
                    value={metaDraft.summary ?? ""}
                    onChange={(event) => setMetaDraft((draft) => ({ ...draft, summary: event.target.value }))}
                    placeholder="요약"
                    rows={2}
                    className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                  <input
                    value={(metaDraft.tags ?? []).join(", ")}
                    onChange={(event) =>
                      setMetaDraft((draft) => ({
                        ...draft,
                        tags: event.target.value
                          .split(",")
                          .map((token) => token.trim())
                          .filter(Boolean),
                      }))
                    }
                    placeholder="태그를 콤마로 구분"
                    className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                  <div className="flex justify-end gap-3">
                    <button type="button" onClick={() => setEditingMeta(false)} className="rounded-lg border border-border-light px-4 py-2 text-sm text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark">
                      취소
                    </button>
                    <button
                      type="button"
                      onClick={handleMetaSubmit}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                    >
                      저장
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{activeNotebook.notebook.title}</h2>
                      {activeNotebook.notebook.summary ? (
                        <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">{activeNotebook.notebook.summary}</p>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleMetaEdit}
                        className="inline-flex items-center gap-1 rounded-lg border border-border-light px-3 py-1.5 text-xs text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                      >
                        <Pencil className="h-3.5 w-3.5" /> 편집
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteNotebook()}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-400 transition hover:border-red-400 hover:text-red-300"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> 삭제
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    <Tag className="h-3.5 w-3.5 text-primary" />
                    {activeNotebook.notebook.tags.length > 0
                      ? activeNotebook.notebook.tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                            #{tag}
                          </span>
                        ))
                      : "태그 없음"}
                  </div>
                </>
              )}
            </section>
            <NotebookEntryComposer onSubmit={onCreateEntry} />
            <section className="space-y-3">
              {entries.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border-light px-4 py-8 text-center text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                  아직 작성된 하이라이트가 없습니다.
                </p>
              ) : (
                entries.map((entry) => (
                  <EntryCard
                    key={entry.id}
                    entry={entry}
                    pending={pendingEntryId === entry.id}
                    onUpdate={(payload) => handleEntryUpdate(entry.id, payload)}
                    onDelete={() => onDeleteEntry(entry.id)}
                  />
                ))
              )}
            </section>
            <NotebookSharePanel notebookTitle={activeNotebook.notebook.title} shares={shares} onCreate={onCreateShare} onRevoke={onRevokeShare} />
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-border-light px-6 py-12 text-center text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            노트북을 선택하거나 새로 생성해 주세요.
          </div>
        )}
      </div>
    </div>
  );
}

type EntryCardProps = {
  entry: NotebookEntry;
  pending?: boolean;
  onUpdate: (payload: NotebookEntryUpdatePayload) => Promise<void>;
  onDelete: () => Promise<void>;
};

const EntryCard = ({ entry, pending, onUpdate, onDelete }: EntryCardProps) => {
  const [editing, setEditing] = useState(false);

  const initialValue: NotebookEntryCreatePayload = {
    highlight: entry.highlight,
    annotation: entry.annotation ?? "",
    annotationFormat: entry.annotationFormat,
    tags: entry.tags,
    source: entry.source,
    isPinned: entry.isPinned,
    position: entry.position,
  };

  const handleSubmit = async (payload: NotebookEntryCreatePayload) => {
    await onUpdate(payload);
    setEditing(false);
  };

  if (editing) {
    return (
      <NotebookEntryComposer
        initialValue={initialValue}
        onSubmit={handleSubmit}
        submitLabel="하이라이트 수정"
        busy={pending}
        resetOnSubmit={false}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <article className="space-y-3 rounded-2xl border border-border-light bg-background-light/60 p-4 shadow-sm dark:border-border-dark dark:bg-background-dark/60">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{entry.highlight}</p>
          {entry.annotation ? (
            <p className="mt-2 whitespace-pre-wrap text-sm text-text-secondaryLight dark:text-text-secondaryDark">{entry.annotation}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {entry.tags.map((tag) => (
              <span key={tag} className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">
                #{tag}
              </span>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded-lg border border-border-light px-3 py-1 text-xs text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
          >
            편집
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-lg border border-red-500/30 px-3 py-1 text-xs text-red-400 transition hover:border-red-400 hover:text-red-300"
          >
            삭제
          </button>
        </div>
      </div>
      <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        {entry.source?.label ? <span>{entry.source.label}</span> : null} {entry.source?.url ? <a href={entry.source.url} target="_blank" rel="noreferrer" className="text-primary">링크 이동</a> : null}
      </div>
    </article>
  );
};
