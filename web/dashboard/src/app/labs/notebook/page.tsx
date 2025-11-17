"use client";

import { useCallback, useEffect, useState } from "react";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { NotebookWorkspace } from "@/components/notebook/NotebookWorkspace";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import {
  NotebookApiError,
  NotebookCreatePayload,
  NotebookDetailResponse,
  NotebookEntryCreatePayload,
  NotebookEntryUpdatePayload,
  NotebookShare,
  NotebookShareCreatePayload,
  NotebookSummary,
  NotebookUpdatePayload,
  createNotebook,
  createNotebookEntry,
  createNotebookShare,
  deleteNotebook,
  deleteNotebookEntry,
  fetchNotebookDetail,
  fetchNotebookList,
  fetchNotebookShares,
  revokeNotebookShare,
  updateNotebook,
  updateNotebookEntry,
} from "@/lib/notebookApi";
import { toast } from "@/store/toastStore";

export default function NotebookLabPage() {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    notFound();
  }

  const [notebooks, setNotebooks] = useState<NotebookSummary[]>([]);
  const [activeNotebook, setActiveNotebook] = useState<NotebookDetailResponse | null>(null);
  const [shares, setShares] = useState<NotebookShare[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(
    async (notebookId: string) => {
      setDetailLoading(true);
      try {
        const [detail, shareList] = await Promise.all([fetchNotebookDetail(notebookId), fetchNotebookShares(notebookId)]);
        setActiveNotebook(detail);
        setShares(shareList.shares);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "노트북을 불러오지 못했습니다.";
        toast.show({ message, intent: "error" });
        setActiveNotebook(null);
        setShares([]);
      } finally {
        setDetailLoading(false);
      }
    },
    [],
  );

  const loadList = useCallback(
    async (preferredId?: string | null) => {
      setListLoading(true);
      try {
        const list = await fetchNotebookList();
        setNotebooks(list.items);
        let nextId = preferredId ?? activeId;
        if (nextId && !list.items.some((item) => item.id === nextId)) {
          nextId = list.items[0]?.id ?? null;
        }
        if (!nextId) {
          setActiveId(null);
          setActiveNotebook(null);
          setShares([]);
        } else {
          setActiveId(nextId);
          await loadDetail(nextId);
        }
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "Notebook 데이터를 불러오지 못했습니다.";
        setError(message);
      } finally {
        setListLoading(false);
      }
    },
    [activeId, loadDetail],
  );

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleSelectNotebook = async (notebookId: string) => {
    setActiveId(notebookId);
    await loadDetail(notebookId);
  };

  const handleCreateNotebook = async (payload: NotebookCreatePayload) => {
    try {
      const detail = await createNotebook(payload);
      toast.show({ message: "노트북을 생성했습니다.", intent: "success" });
      setActiveId(detail.notebook.id);
      setActiveNotebook(detail);
      setShares([]);
      await loadList(detail.notebook.id);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "노트북 생성에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleUpdateNotebook = async (payload: NotebookUpdatePayload) => {
    if (!activeId) {
      return;
    }
    try {
      await updateNotebook(activeId, payload);
      toast.show({ message: "노트북 정보를 업데이트했습니다.", intent: "success" });
      await loadList(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "노트북 업데이트에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleDeleteNotebook = async () => {
    if (!activeId) {
      return;
    }
    try {
      await deleteNotebook(activeId);
      toast.show({ message: "노트북을 삭제했습니다.", intent: "success" });
      await loadList(null);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "노트북 삭제에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleCreateEntry = async (payload: NotebookEntryCreatePayload) => {
    if (!activeId) {
      toast.show({ message: "먼저 노트북을 선택하세요.", intent: "warning" });
      return;
    }
    try {
      await createNotebookEntry(activeId, payload);
      toast.show({ message: "하이라이트를 추가했습니다.", intent: "success" });
      await loadDetail(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "하이라이트 추가에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleUpdateEntry = async (entryId: string, payload: NotebookEntryUpdatePayload) => {
    if (!activeId) {
      return;
    }
    try {
      await updateNotebookEntry(activeId, entryId, payload);
      toast.show({ message: "하이라이트를 수정했습니다.", intent: "success" });
      await loadDetail(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "하이라이트 수정에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleDeleteEntry = async (entryId: string) => {
    if (!activeId) {
      return;
    }
    try {
      await deleteNotebookEntry(activeId, entryId);
      toast.show({ message: "하이라이트를 삭제했습니다.", intent: "success" });
      await loadDetail(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "삭제에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleCreateShare = async (payload: NotebookShareCreatePayload) => {
    if (!activeId) {
      return;
    }
    try {
      await createNotebookShare(activeId, payload);
      toast.show({ message: "공유 링크를 생성했습니다.", intent: "success" });
      await loadDetail(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "공유 링크 생성에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  const handleRevokeShare = async (shareId: string) => {
    if (!activeId) {
      return;
    }
    try {
      await revokeNotebookShare(activeId, shareId);
      toast.show({ message: "공유 링크를 폐기했습니다.", intent: "success" });
      await loadDetail(activeId);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "공유 링크 폐기에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-primary">Labs · Research</p>
          <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">Research Notebook</h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            하이라이트, 주석, 태그, 공유 링크를 한 곳에서 관리해 협업 노트북을 구성하세요.
          </p>
        </header>
        {error ? (
          <ErrorState
            title="노트북을 불러오지 못했습니다."
            description={error}
            action={
              <button
                type="button"
                onClick={() => loadList()}
                className="rounded-lg border border-primary px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/10"
              >
                다시 시도
              </button>
            }
          />
        ) : notebooks.length === 0 && listLoading ? (
          <SkeletonBlock lines={6} />
        ) : (
          <NotebookWorkspace
            notebooks={notebooks}
            activeNotebook={activeNotebook}
            shares={shares}
            loadingNotebooks={listLoading}
            loadingDetail={detailLoading}
            onSelectNotebook={handleSelectNotebook}
            onCreateNotebook={handleCreateNotebook}
            onUpdateNotebook={handleUpdateNotebook}
            onDeleteNotebook={handleDeleteNotebook}
            onCreateEntry={handleCreateEntry}
            onUpdateEntry={handleUpdateEntry}
            onDeleteEntry={handleDeleteEntry}
            onCreateShare={handleCreateShare}
            onRevokeShare={handleRevokeShare}
          />
        )}
      </div>
    </AppShell>
  );
}
