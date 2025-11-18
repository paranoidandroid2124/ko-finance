"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  NotebookApiError,
  type NotebookCreatePayload,
  type NotebookDetailResponse,
  type NotebookEntryCreatePayload,
  type NotebookEntryUpdatePayload,
  type NotebookShare,
  type NotebookShareCreatePayload,
  type NotebookSummary,
  type NotebookUpdatePayload,
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

export type NotebookControllerState = {
  notebooks: NotebookSummary[];
  activeNotebook: NotebookDetailResponse | null;
  shares: NotebookShare[];
  listLoading: boolean;
  detailLoading: boolean;
  activeNotebookId: string | null;
  error: string | null;
};

export type NotebookControllerHandlers = {
  refresh: (preferredId?: string | null) => Promise<void>;
  selectNotebook: (notebookId: string) => Promise<void>;
  createNotebook: (payload: NotebookCreatePayload) => Promise<void>;
  updateNotebook: (payload: NotebookUpdatePayload) => Promise<void>;
  deleteNotebook: () => Promise<void>;
  createEntry: (payload: NotebookEntryCreatePayload) => Promise<void>;
  updateEntry: (entryId: string, payload: NotebookEntryUpdatePayload) => Promise<void>;
  deleteEntry: (entryId: string) => Promise<void>;
  createShare: (payload: NotebookShareCreatePayload) => Promise<void>;
  revokeShare: (shareId: string) => Promise<void>;
};

type NotebookControllerOptions = {
  autoLoad?: boolean;
};

const GENERIC_FETCH_ERROR = "Notebook 데이터를 불러오지 못했습니다.";

export function useNotebookController(options?: NotebookControllerOptions) {
  const autoLoad = options?.autoLoad ?? true;

  const [notebooks, setNotebooks] = useState<NotebookSummary[]>([]);
  const [activeNotebook, setActiveNotebook] = useState<NotebookDetailResponse | null>(null);
  const [shares, setShares] = useState<NotebookShare[]>([]);
  const [listLoading, setListLoading] = useState<boolean>(false);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [activeNotebookId, setActiveNotebookId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async (notebookId: string) => {
    setDetailLoading(true);
    try {
      const [detail, shareList] = await Promise.all([fetchNotebookDetail(notebookId), fetchNotebookShares(notebookId)]);
      setActiveNotebook(detail);
      setShares(shareList.shares);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : GENERIC_FETCH_ERROR;
      toast.show({ message, intent: "error" });
      setActiveNotebook(null);
      setShares([]);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const loadList = useCallback(
    async (preferredId?: string | null) => {
      setListLoading(true);
      setError(null);
      try {
        const list = await fetchNotebookList();
        setNotebooks(list.items);
        let nextId = preferredId ?? activeNotebookId;
        if (nextId && !list.items.some((item) => item.id === nextId)) {
          nextId = list.items[0]?.id ?? null;
        }
        if (!nextId) {
          setActiveNotebookId(null);
          setActiveNotebook(null);
          setShares([]);
        } else {
          setActiveNotebookId(nextId);
          await loadDetail(nextId);
        }
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : GENERIC_FETCH_ERROR;
        setError(message);
      } finally {
        setListLoading(false);
      }
    },
    [activeNotebookId, loadDetail],
  );

  useEffect(() => {
    if (autoLoad) {
      loadList().catch(() => {
        /* errors handled inside loadList */
      });
    }
  }, [autoLoad, loadList]);

  const selectNotebook = useCallback(
    async (notebookId: string) => {
      setActiveNotebookId(notebookId);
      await loadDetail(notebookId);
    },
    [loadDetail],
  );

  const handleCreateNotebook = useCallback(
    async (payload: NotebookCreatePayload) => {
      try {
        const detail = await createNotebook(payload);
        toast.show({ message: "노트북을 생성했습니다.", intent: "success" });
        setActiveNotebookId(detail.notebook.id);
        setActiveNotebook(detail);
        setShares([]);
        await loadList(detail.notebook.id);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "노트북 생성에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [loadList],
  );

  const handleUpdateNotebook = useCallback(
    async (payload: NotebookUpdatePayload) => {
      if (!activeNotebookId) {
        return;
      }
      try {
        await updateNotebook(activeNotebookId, payload);
        toast.show({ message: "노트북 정보를 업데이트했습니다.", intent: "success" });
        await loadList(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "노트북 업데이트에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadList],
  );

  const handleDeleteNotebook = useCallback(async () => {
    if (!activeNotebookId) {
      return;
    }
    try {
      await deleteNotebook(activeNotebookId);
      toast.show({ message: "노트북을 삭제했습니다.", intent: "success" });
      await loadList(null);
    } catch (err) {
      const message = err instanceof NotebookApiError ? err.message : "노트북 삭제에 실패했습니다.";
      toast.show({ message, intent: "error" });
    }
  }, [activeNotebookId, loadList]);

  const handleCreateEntry = useCallback(
    async (payload: NotebookEntryCreatePayload) => {
      if (!activeNotebookId) {
        toast.show({ message: "먼저 노트북을 선택해주세요.", intent: "warning" });
        return;
      }
      try {
        await createNotebookEntry(activeNotebookId, payload);
        toast.show({ message: "하이라이트를 추가했습니다.", intent: "success" });
        await loadDetail(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "하이라이트 추가에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadDetail],
  );

  const handleUpdateEntry = useCallback(
    async (entryId: string, payload: NotebookEntryUpdatePayload) => {
      if (!activeNotebookId) {
        return;
      }
      try {
        await updateNotebookEntry(activeNotebookId, entryId, payload);
        toast.show({ message: "하이라이트를 수정했습니다.", intent: "success" });
        await loadDetail(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "하이라이트 수정에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadDetail],
  );

  const handleDeleteEntry = useCallback(
    async (entryId: string) => {
      if (!activeNotebookId) {
        return;
      }
      try {
        await deleteNotebookEntry(activeNotebookId, entryId);
        toast.show({ message: "하이라이트를 삭제했습니다.", intent: "success" });
        await loadDetail(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "삭제에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadDetail],
  );

  const handleCreateShare = useCallback(
    async (payload: NotebookShareCreatePayload) => {
      if (!activeNotebookId) {
        return;
      }
      try {
        await createNotebookShare(activeNotebookId, payload);
        toast.show({ message: "공유 링크를 생성했습니다.", intent: "success" });
        await loadDetail(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "공유 링크 생성에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadDetail],
  );

  const handleRevokeShare = useCallback(
    async (shareId: string) => {
      if (!activeNotebookId) {
        return;
      }
      try {
        await revokeNotebookShare(activeNotebookId, shareId);
        toast.show({ message: "공유 링크를 회수했습니다.", intent: "success" });
        await loadDetail(activeNotebookId);
      } catch (err) {
        const message = err instanceof NotebookApiError ? err.message : "공유 링크 회수에 실패했습니다.";
        toast.show({ message, intent: "error" });
      }
    },
    [activeNotebookId, loadDetail],
  );

  const state: NotebookControllerState = useMemo(
    () => ({
      notebooks,
      activeNotebook,
      shares,
      listLoading,
      detailLoading,
      activeNotebookId,
      error,
    }),
    [activeNotebook, activeNotebookId, detailLoading, error, listLoading, notebooks, shares],
  );

  const handlers: NotebookControllerHandlers = {
    refresh: loadList,
    selectNotebook,
    createNotebook: handleCreateNotebook,
    updateNotebook: handleUpdateNotebook,
    deleteNotebook: handleDeleteNotebook,
    createEntry: handleCreateEntry,
    updateEntry: handleUpdateEntry,
    deleteEntry: handleDeleteEntry,
    createShare: handleCreateShare,
    revokeShare: handleRevokeShare,
  };

  return { state, handlers };
}

