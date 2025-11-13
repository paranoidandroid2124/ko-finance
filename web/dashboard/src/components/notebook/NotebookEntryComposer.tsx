"use client";

import { FormEvent, useMemo, useState } from "react";
import clsx from "clsx";

import { TagInput } from "@/components/ui/TagInput";
import type { NotebookEntryCreatePayload } from "@/lib/notebookApi";

type NotebookEntryComposerProps = {
  onSubmit: (payload: NotebookEntryCreatePayload) => Promise<void> | void;
  submitLabel?: string;
  busy?: boolean;
  resetOnSubmit?: boolean;
  initialValue?: Partial<NotebookEntryCreatePayload>;
  onCancel?: () => void;
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const renderMarkdown = (value: string) => {
  const safe = escapeHtml(value);
  const inline = safe
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  return inline
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${paragraph.replace(/\n/g, "<br />")}</p>`)
    .join("");
};

export function NotebookEntryComposer({
  onSubmit,
  submitLabel = "하이라이트 추가",
  busy,
  resetOnSubmit = true,
  initialValue,
  onCancel,
}: NotebookEntryComposerProps) {
  const [highlight, setHighlight] = useState(initialValue?.highlight ?? "");
  const [annotation, setAnnotation] = useState(initialValue?.annotation ?? "");
  const [tags, setTags] = useState<string[]>(initialValue?.tags ?? []);
  const [sourceType, setSourceType] = useState(initialValue?.source?.type ?? "");
  const [sourceLabel, setSourceLabel] = useState(initialValue?.source?.label ?? "");
  const [sourceUrl, setSourceUrl] = useState(initialValue?.source?.url ?? "");
  const [sourceSnippet, setSourceSnippet] = useState(initialValue?.source?.snippet ?? "");
  const [isPinned, setIsPinned] = useState(initialValue?.isPinned ?? false);
  const [position, setPosition] = useState<number | undefined>(initialValue?.position ?? undefined);
  const [tab, setTab] = useState<"edit" | "preview">("edit");

  const previewHtml = useMemo(() => (annotation ? renderMarkdown(annotation) : "<em>내용이 없습니다.</em>"), [annotation]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const payload: NotebookEntryCreatePayload = {
      highlight: highlight.trim(),
      annotation: annotation.trim() || undefined,
      annotationFormat: "markdown",
      tags,
      isPinned,
      position,
      source: {
        type: sourceType || undefined,
        label: sourceLabel || undefined,
        url: sourceUrl || undefined,
        snippet: sourceSnippet || undefined,
      },
    };
    await onSubmit(payload);
    if (resetOnSubmit) {
      setHighlight("");
      setAnnotation("");
      setTags([]);
      setSourceType("");
      setSourceLabel("");
      setSourceUrl("");
      setSourceSnippet("");
      setIsPinned(false);
      setPosition(undefined);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border-light bg-background-light p-4 shadow-sm dark:border-border-dark dark:bg-background-dark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">새 하이라이트</h3>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">하이라이트 · 태그 · 소스 메타데이터를 함께 보관하세요.</p>
        </div>
        <label className="flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <input type="checkbox" checked={isPinned} onChange={(event) => setIsPinned(event.target.checked)} className="accent-primary" />
          상단 고정
        </label>
      </div>
      <label className="space-y-2">
        <span className="text-sm font-semibold text-text-secondaryLight dark:text-text-secondaryDark">하이라이트</span>
        <textarea
          value={highlight}
          onChange={(event) => setHighlight(event.target.value)}
          required
          rows={3}
          placeholder="문서에서 발췌한 핵심 문장을 붙여넣으세요."
          className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <div>
        <div className="flex items-center gap-3 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          <button type="button" onClick={() => setTab("edit")} className={clsx("border-b-2 px-1 pb-1 font-semibold", tab === "edit" ? "border-primary text-primary" : "border-transparent opacity-60")}>
            주석 편집
          </button>
          <button type="button" onClick={() => setTab("preview")} className={clsx("border-b-2 px-1 pb-1 font-semibold", tab === "preview" ? "border-primary text-primary" : "border-transparent opacity-60")}>
            Markdown 미리보기
          </button>
        </div>
        {tab === "edit" ? (
          <textarea
            value={annotation}
            onChange={(event) => setAnnotation(event.target.value)}
            rows={4}
            placeholder="Markdown으로 주석을 남기세요. **굵게**, _기울임_, `코드` 등을 지원합니다."
            className="mt-2 w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        ) : (
          <div
            className="mt-2 rounded-lg border border-dashed border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        )}
      </div>
      <div>
        <span className="text-sm font-semibold text-text-secondaryLight dark:text-text-secondaryDark">태그</span>
        <TagInput values={tags} onChange={setTags} placeholder="예: #earnings, #macro" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          소스 타입
          <input
            value={sourceType}
            onChange={(event) => setSourceType(event.target.value)}
            placeholder="예: filing / news"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          소스 라벨
          <input
            value={sourceLabel}
            onChange={(event) => setSourceLabel(event.target.value)}
            placeholder="문서명 혹은 기사 제목"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>
      <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        소스 URL
        <input
          value={sourceUrl}
          onChange={(event) => setSourceUrl(event.target.value)}
          placeholder="https://..."
          className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <label className="space-y-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        소스 스니펫
        <textarea
          value={sourceSnippet}
          onChange={(event) => setSourceSnippet(event.target.value)}
          rows={2}
          placeholder="문맥을 이해할 수 있는 추가 설명을 적어주세요."
          className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          순서
          <input
            type="number"
            value={position ?? ""}
            onChange={(event) => setPosition(event.target.value ? Number(event.target.value) : undefined)}
            min={0}
            className="ml-2 w-20 rounded-md border border-border-light bg-background-base px-2 py-1 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <div className="flex-1" />
        {onCancel ? (
          <button type="button" onClick={onCancel} className="rounded-lg border border-border-light px-4 py-2 text-sm text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark">
            취소
          </button>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "저장 중..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
