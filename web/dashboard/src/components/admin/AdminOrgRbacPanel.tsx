"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, ShieldCheck, Users } from "lucide-react";

import { resolveApiBase } from "@/lib/apiBase";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { useOnboardingWizardStore } from "@/store/onboardingWizardStore";
import { useToastStore } from "@/store/toastStore";

type AdminOrgRbacPanelProps = {
  compact?: boolean;
};

const ROLE_OPTIONS = [
  { value: "viewer", label: "Viewer" },
  { value: "editor", label: "Editor" },
  { value: "admin", label: "Admin" },
];

export function AdminOrgRbacPanel({ compact = false }: AdminOrgRbacPanelProps) {
  const wizard = useOnboardingWizardStore();
  const toast = useToastStore((state) => state.show);
  const [updatingMember, setUpdatingMember] = useState<string | null>(null);

  useEffect(() => {
    if (!wizard.state && !wizard.loading) {
      void wizard.fetchState().catch(() => undefined);
    }
  }, [wizard]);

  const members = wizard.state?.members ?? [];
  const org = wizard.state?.org;

  const handleRoleChange = async (memberId: string, nextRole: string) => {
    if (!org) {
      return;
    }
    setUpdatingMember(memberId);
    try {
      const response = await fetchWithAuth(`${resolveApiBase()}/api/v1/orgs/${org.id}/members/${memberId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Org-Id": org.id,
        },
        body: JSON.stringify({ role: nextRole }),
      });
      if (!response.ok) {
        throw new Error("멤버 역할을 업데이트하지 못했습니다.");
      }
      await wizard.fetchState();
      toast({
        id: `admin/org/role/${memberId}`,
        title: "구성원 역할이 변경되었습니다.",
        intent: "success",
      });
    } catch (error) {
      toast({
        id: `admin/org/role/${memberId}/error`,
        title: "역할 변경 실패",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    } finally {
      setUpdatingMember(null);
    }
  };

  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
            Org &amp; RBAC
          </p>
          <h3 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">
            {org?.name ?? "워크스페이스"}
          </h3>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            구성원 역할을 빠르게 변경하고 대시보드에서 바로 초대 흐름을 열 수 있습니다.
          </p>
        </div>
        <Users className="h-8 w-8 text-primary" aria-hidden />
      </div>
      <div className="mt-4 space-y-2 text-sm">
        {members.slice(0, compact ? 3 : 6).map((member) => (
          <div
            key={member.userId}
            className="flex flex-col gap-2 rounded-lg border border-border-light/70 px-3 py-2 dark:border-border-dark lg:flex-row lg:items-center lg:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate font-semibold text-text-primaryLight dark:text-text-primaryDark">
                {member.email ?? member.userId}
              </p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {member.status === "active" ? "Active" : "Pending"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {member.status === "active" ? (
                <ShieldCheck className="h-4 w-4 text-emerald-400" aria-hidden />
              ) : (
                <span className="text-xs text-amber-400">pending</span>
              )}
              <select
                className="rounded-md border border-border-light px-2 py-1 text-xs focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark"
                value={member.role}
                onChange={(event) => handleRoleChange(member.userId, event.target.value)}
                disabled={member.status !== "active" || updatingMember === member.userId}
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {updatingMember === member.userId ? <Loader2 className="h-3 w-3 animate-spin text-primary" /> : null}
            </div>
          </div>
        ))}
        {members.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border-light px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 초대한 구성원이 없습니다.
          </div>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Link
          href="/onboarding"
          className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark"
        >
          온보딩 페이지 열기
        </Link>
      </div>
    </div>
  );
}
