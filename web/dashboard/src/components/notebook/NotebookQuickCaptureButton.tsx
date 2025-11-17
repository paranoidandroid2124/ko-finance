"use client";

import { createPortal } from "react-dom";
import { useEffect, useMemo, useState } from "react";

import {
  createNotebookEntry,
  fetchNotebookList,
  type NotebookEntrySource,
  type NotebookSummary
} from "@/lib/notebookApi";
import { toast } from "@/store/toastStore";

type NotebookQuickCaptureButtonProps = {
  highlight: string;
  source?: NotebookEntrySource;
  tags?: string[];
  className?: string;
};

export function NotebookQuickCaptureButton({ highlight, source, tags, className }: NotebookQuickCaptureButtonProps) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [notebooks, setNotebooks] = useState<NotebookSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoadingList(true);
      try {
        const response = await fetchNotebookList({ limit: 20 });
        if (cancelled) {
          return;
        }
        setNotebooks(response.items);
        if (!selectedId && response.items.length > 0) {
          setSelectedId(response.items[0].id);
        }
        setError(response.items.length === 0 ? "선택할 수 있는 노트북이 없습니다." : null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "노트북 목록을 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) {
          setLoadingList(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [open, selectedId]);

  const handleSubmit = async () => {
    if (!selectedId) {
      setError("저장할 노트북을 선택해주세요.");
      return;
    }
    setBusy(true);
    try {
      await createNotebookEntry(selectedId, {
        highlight,
        annotation: note || undefined,
        tags,
        source
      });
      toast.show({ intent: "success", message: "노트북에 저장했습니다." });
      setOpen(false);
      setNote("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "노트북 저장에 실패했습니다.";
      toast.show({ intent: "error", message });
    } finally {
      setBusy(false);
    }
  };

  const renderModal = () => {
    if (!mounted || !open) {
      return null;
    }
    return createPortal(
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-6">
        <div className="w-full max-w-md rounded-2xl bg-white p-6 text-slate-900 shadow-2xl dark:bg-slate-900 dark:text-slate-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-emerald-400">Notebook Capture</p>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">하이라이트 저장</h2>
            </div>
            <button type="button" className="text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" onClick={() => setOpen(false)}>
              닫기
            </button>
          </div>
          <div className="mt-4 space-y-4 text-sm">
            <label className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">저장할 노트북</span>
              <select
                value={selectedId}
                onChange={(event) => setSelectedId(event.target.value)}
                disabled={loadingList}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              >
                <option value="">노트북을 선택하세요</option>
                {notebooks.map((nb) => (
                  <option key={nb.id} value={nb.id}>
                    {nb.title} ({nb.entryCount}개)
                  </option>
                ))}
              </select>
            </label>
            <div>
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">하이라이트</span>
              <p className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {highlight}
              </p>
            </div>
            <label className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">메모 (선택)</span>
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                placeholder="추가 설명이나 태그를 남겨주세요."
              />
            </label>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 transition hover:border-slate-400 dark:border-slate-600 dark:text-slate-200 dark:hover:border-slate-500"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={busy || loadingList}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? "저장 중..." : "노트북에 저장"}
            </button>
          </div>
        </div>
      </div>,
      document.body
    );
  };

  const buttonLabel = useMemo(() => "노트에 저장", []);
  return (
    <>
      <button
        type="button"
        className={className || "rounded border border-slate-300 px-2 py-1 text-[11px] text-primary hover:border-primary"}
        onClick={() => setOpen(true)}
      >
        {buttonLabel}
      </button>
      {renderModal()}
    </>
  );
}
