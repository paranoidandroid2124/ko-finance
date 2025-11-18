"use client";

import { useQuery } from "@tanstack/react-query";

import { resolveApiBase } from "@/lib/apiBase";

export type WorkspaceMember = {
  userId: string;
  email?: string | null;
  name?: string | null;
  role: string;
  status: string;
  joinedAt?: string | null;
  acceptedAt?: string | null;
};

export type WorkspaceNotebook = {
  id: string;
  title: string;
  summary?: string | null;
  tags: string[];
  entryCount: number;
  lastActivityAt?: string | null;
};

export type WorkspaceWatchlist = {
  ruleId: string;
  name: string;
  type: string;
  tickers: string[];
  eventCount: number;
  updatedAt?: string | null;
};

export type WorkspaceOverview = {
  orgId: string;
  orgName?: string | null;
  memberCount: number;
  members: WorkspaceMember[];
  notebooks: WorkspaceNotebook[];
  watchlists: WorkspaceWatchlist[];
};

const fetchWorkspaceOverview = async (): Promise<WorkspaceOverview> => {
  const baseUrl = resolveApiBase();
  const response = await fetch(`${baseUrl}/api/v1/workspaces/current`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("워크스페이스 정보를 불러오지 못했습니다.");
  }
  return (await response.json()) as WorkspaceOverview;
};

export function useWorkspaceOverview(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["workspace", "overview"],
    queryFn: fetchWorkspaceOverview,
    enabled: options?.enabled ?? true,
  });
}

