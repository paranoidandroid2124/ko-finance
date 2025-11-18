"use client";

import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { NotebookWorkspace } from "@/components/notebook/NotebookWorkspace";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useNotebookController } from "@/hooks/useNotebookController";

export default function NotebookLabPage() {
  if (process.env.NEXT_PUBLIC_ENABLE_LABS !== "true") {
    notFound();
  }

  const {
    state: { notebooks, activeNotebook, shares, listLoading, detailLoading, error },
    handlers: {
      refresh,
      selectNotebook,
      createNotebook,
      updateNotebook,
      deleteNotebook,
      createEntry,
      updateEntry,
      deleteEntry,
      createShare,
      revokeShare,
    },
  } = useNotebookController();

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-primary">Labs · Research</p>
          <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">Research Notebook</h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            하이라이트, 주석, 태그, 공유 링크를 한 곳에서 관리해 협업 노트북을 구성해 보세요.
          </p>
        </header>
        {error ? (
          <ErrorState
            title="노트북을 불러오지 못했습니다."
            description={error}
            action={
              <button
                type="button"
                onClick={() => refresh()}
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
            onSelectNotebook={selectNotebook}
            onCreateNotebook={createNotebook}
            onUpdateNotebook={updateNotebook}
            onDeleteNotebook={deleteNotebook}
            onCreateEntry={createEntry}
            onUpdateEntry={updateEntry}
            onDeleteEntry={deleteEntry}
            onCreateShare={createShare}
            onRevokeShare={revokeShare}
          />
        )}
      </div>
    </AppShell>
  );
}

