"use client";

import Link from "next/link";
import type { Route } from "next";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PlanLock } from "@/components/ui/PlanLock";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { useWorkspaceOverview, type WorkspaceMember, type WorkspaceNotebook, type WorkspaceWatchlist } from "@/hooks/useWorkspaceOverview";
import { getPlanLabel } from "@/lib/planTier";
import { usePlanContext } from "@/store/planStore";

const NOTEBOOK_ROUTE = "/workspace/notebook" as Route;
const WATCHLIST_ROUTE = "/alerts" as Route;

export default function WorkspaceHomePage() {
  const { entitlements, planTier } = usePlanContext();
  const hasCollabEntitlement = (entitlements ?? []).includes("collab.notebook");
  const { data, isLoading, isError } = useWorkspaceOverview({ enabled: hasCollabEntitlement });

  if (!hasCollabEntitlement) {
    return (
      <AppShell>
        <PlanLock
          requiredTier="pro"
          title="워크스페이스는 Research Notebook 플랜에서 제공됩니다."
          description="팀 노트, 공유 워치리스트, Alert 요약은 Pro 이상의 플랜에서만 이용할 수 있습니다."
        />
      </AppShell>
    );
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <SkeletonBlock lines={3} />
          <SkeletonBlock lines={6} />
          <SkeletonBlock lines={6} />
        </div>
      </AppShell>
    );
  }

  if (isError || !data) {
    return (
      <AppShell>
        <ErrorState
          title="워크스페이스 정보를 불러올 수 없습니다"
          description="조직 정보를 조회하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <WorkspaceHeader orgName={data.orgName} memberCount={data.memberCount} planTier={planTier} />
        <div className="grid gap-6 lg:grid-cols-2">
          <NotebookSummaryCard notebooks={data.notebooks} />
          <WatchlistSummaryCard watchlists={data.watchlists} />
        </div>
        <MembersCard members={data.members} totalCount={data.memberCount} />
      </div>
    </AppShell>
  );
}

type WorkspaceHeaderProps = {
  orgName?: string | null;
  memberCount: number;
  planTier: string;
};

function WorkspaceHeader({ orgName, memberCount, planTier }: WorkspaceHeaderProps) {
  return (
    <section className="flex flex-col justify-between gap-4 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark md:flex-row md:items-center">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">Workspace</p>
        <h1 className="mt-1 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{orgName ?? "이름 없는 조직"}</h1>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">멤버 {memberCount}명</p>
      </div>
      <div className="text-right">
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">현재 플랜</p>
        <p className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{getPlanLabel(planTier as never)}</p>
        <Link
          href={"/settings" as Route}
          className="mt-2 inline-flex items-center justify-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition-colors hover:bg-background-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-background-dark"
        >
          조직 설정 열기
        </Link>
      </div>
    </section>
  );
}

type NotebookSummaryCardProps = {
  notebooks: WorkspaceNotebook[];
};

function NotebookSummaryCard({ notebooks }: NotebookSummaryCardProps) {
  const preview = notebooks.slice(0, 4);
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">Research Notebook</h2>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">총 {notebooks.length}건의 노트</p>
        </div>
        <Link
          href={NOTEBOOK_ROUTE}
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/10 dark:border-border-dark dark:text-primary.dark dark:hover:bg-primary.dark/20"
        >
          노트 열기
        </Link>
      </div>
      {preview.length === 0 ? (
        <EmptyState
          title="아직 생성된 노트가 없습니다"
          description="중요한 Evidence나 Q&A를 Notebook으로 정리해 팀과 공유해 보세요."
          className="mt-4 border-none"
        />
      ) : (
        <ul className="mt-4 space-y-3">
          {preview.map((notebook) => (
            <li key={notebook.id} className="rounded-xl border border-border-light/70 px-4 py-3 dark:border-border-dark/70">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{notebook.title}</p>
                  {notebook.summary ? (
                    <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{notebook.summary}</p>
                  ) : null}
                  {notebook.tags.length ? (
                    <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">태그: {notebook.tags.join(", ")}</p>
                  ) : null}
                </div>
                <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">{notebook.entryCount}개</span>
              </div>
              <p className="mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                최근 업데이트: {formatDateTime(notebook.lastActivityAt)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type WatchlistSummaryCardProps = {
  watchlists: WorkspaceWatchlist[];
};

function WatchlistSummaryCard({ watchlists }: WatchlistSummaryCardProps) {
  const preview = watchlists.slice(0, 4);
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">Watchlists & Alerts</h2>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">총 {watchlists.length}개 룰</p>
        </div>
        <Link
          href={WATCHLIST_ROUTE}
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/10 dark:border-border-dark dark:text-primary.dark dark:hover:bg-primary.dark/20"
        >
          Alert Center
        </Link>
      </div>
      {preview.length === 0 ? (
        <EmptyState
          title="등록된 Watchlist가 없습니다"
          description="종목/키워드 Watchlist를 만들어 팀 전체 알림을 자동화해 보세요."
          className="mt-4 border-none"
        />
      ) : (
        <ul className="mt-4 space-y-3">
          {preview.map((item) => (
            <li key={item.ruleId} className="rounded-xl border border-border-light/70 px-4 py-3 dark:border-border-dark/70">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.name}</p>
                  <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    감시 종목 {item.tickers.length}개 · 최근 이벤트 {item.eventCount}건
                  </p>
                </div>
                <span className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                  {item.updatedAt ? formatRelativeLabel(item.updatedAt) : "기록 없음"}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type MembersCardProps = {
  members: WorkspaceMember[];
  totalCount: number;
};

function MembersCard({ members, totalCount }: MembersCardProps) {
  const preview = members.slice(0, 8);
  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">멤버 현황</h2>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">총 {totalCount}명 · 최근 초대 {formatRecentInvite(members)}</p>
        </div>
        <Link
          href={"/settings" as Route}
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/10 dark:border-border-dark dark:text-primary.dark dark:hover:bg-primary.dark/20"
        >
          멤버 관리
        </Link>
      </div>
      {preview.length === 0 ? (
        <EmptyState
          title="멤버가 없습니다"
          description="조직 설정에서 팀원을 초대해 협업 워크플로우를 시작하세요."
          className="mt-4 border-none"
        />
      ) : (
        <ul className="mt-4 grid gap-4 md:grid-cols-2">
          {preview.map((member) => (
            <li key={member.userId} className="rounded-xl border border-border-light/70 px-4 py-3 dark:border-border-dark/70">
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {member.name ?? member.email ?? "이름 없음"}
              </p>
              {member.email ? <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{member.email}</p> : null}
              <div className="mt-2 flex items-center justify-between text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                <span>{member.role}</span>
                <span>{member.status}</span>
              </div>
              <p className="mt-1 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                합류: {formatDateTime(member.acceptedAt ?? member.joinedAt)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return "기록 없음";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("ko-KR");
};

const formatRelativeLabel = (value?: string | null) => {
  if (!value) {
    return "기록 없음";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const diffMs = Date.now() - parsed.getTime();
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) {
    const diffMinutes = Math.max(1, Math.round(diffMs / (1000 * 60)));
    return `${diffMinutes}분 전`;
  }
  if (diffHours < 24) {
    return `${diffHours}시간 전`;
  }
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}일 전`;
};

const formatRecentInvite = (members: WorkspaceMember[]) => {
  const accepted = members
    .map((member) => member.acceptedAt ?? member.joinedAt)
    .filter((value): value is string => Boolean(value))
    .sort()
    .reverse();
  if (!accepted.length) {
    return "기록 없음";
  }
  return formatRelativeLabel(accepted[0]);
};
