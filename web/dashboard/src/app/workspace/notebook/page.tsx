"use client";

import { AppShell } from "@/components/layout/AppShell";
import { NotebookWorkspace } from "@/components/notebook/NotebookWorkspace";
import { PlanLock } from "@/components/ui/PlanLock";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useNotebookController } from "@/hooks/useNotebookController";
import { usePlanContext } from "@/store/planStore";

export default function WorkspaceNotebookPage() {
  const { entitlements } = usePlanContext();
  const hasNotebookEntitlement = (entitlements ?? []).includes("collab.notebook");

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
  } = useNotebookController({ autoLoad: hasNotebookEntitlement });

  if (!hasNotebookEntitlement) {
    return (
      <AppShell>
        <PlanLock
          requiredTier="pro"
          title="Notebook은 Research 플랜에서 제공됩니다."
          description="팀 노트, Evidence 하이라이트, 공유 링크 기능은 Pro 이상의 플랜을 구독하면 사용할 수 있습니다."
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <header className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">Workspace · Notebook</p>
          <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">Research Notebook</h1>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            질문과 Evidence, 주석을 한 곳에 모아 팀이 공유할 수 있는 연구 노트를 작성하세요.
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

