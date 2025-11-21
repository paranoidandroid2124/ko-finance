"use client";

import Link from "next/link";
import useSWR from "swr";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";

import fetchWithAuth from "@/lib/fetchWithAuth";
import { useToastStore } from "@/store/toastStore";

type AdminKpiResponse = {
  totalUsers: number;
  reportsToday: number;
  heavyUsers: number;
};

type AdminUser = {
  id: string;
  email: string;
  plan: string;
  isActive: boolean;
  reportCount: number;
  lastReportAt?: string | null;
  lastLoginAt?: string | null;
};

type AdminUserListResponse = {
  users: AdminUser[];
};

const fetcher = async (url: string) => {
  const res = await fetchWithAuth(url);
  if (!res.ok) {
    let message = "데이터를 불러오지 못했습니다.";
    try {
      const payload = await res.json();
      if (typeof payload?.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json();
};

export default function AdminPage() {
  const showToast = useToastStore((state) => state.show);
  const { data: kpi, isLoading: kpiLoading, error: kpiError } = useSWR<AdminKpiResponse>("/api/v1/admin/kpi", fetcher);
  const {
    data: users,
    isLoading: usersLoading,
    error: usersError,
  } = useSWR<AdminUserListResponse>("/api/v1/admin/users", fetcher);

  useEffect(() => {
    if (kpiError) {
      showToast({ intent: "error", title: "KPI 조회 실패", message: kpiError.message });
    }
  }, [kpiError, showToast]);

  useEffect(() => {
    if (usersError) {
      showToast({ intent: "error", title: "사용자 목록 조회 실패", message: usersError.message });
    }
  }, [usersError, showToast]);

  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ value: string }>).detail;
      if (detail?.value) {
        window.location.href = `/dashboard?prefill=${encodeURIComponent(detail.value)}`;
      }
    };
    window.addEventListener("onboarding:prefill", listener as EventListener);
    return () => window.removeEventListener("onboarding:prefill", listener as EventListener);
  }, []);

  return (
    <div className="min-h-screen bg-background-dark text-slate-100">
      <div className="mx-auto w-full max-w-6xl px-6 py-12">
        <header className="mb-10 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Admin Dashboard</p>
            <h1 className="text-3xl font-semibold text-white">Nuvien 운영 현황</h1>
          </div>
          <Link
            href="/dashboard"
            className="rounded-full border border-white/20 px-5 py-2 text-sm font-semibold text-white"
          >
            User Mode로 이동
          </Link>
        </header>

        <section className="grid gap-6 sm:grid-cols-3">
          {[
            { label: "총 사용자 수", value: kpi?.totalUsers ?? "-", loading: kpiLoading },
            { label: "금일 생성된 리포트", value: kpi?.reportsToday ?? "-", loading: kpiLoading },
            { label: "Heavy Users (주 5건↑)", value: kpi?.heavyUsers ?? "-", loading: kpiLoading },
          ].map((card) => (
            <div key={card.label} className="rounded-2xl border border-border-dark bg-surface p-6 shadow-lg shadow-black/20">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{card.label}</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {card.loading ? <Loader2 className="h-6 w-6 animate-spin text-slate-500" /> : card.value}
              </p>
            </div>
          ))}
        </section>
        <section className="mt-10 rounded-2xl border border-border-dark bg-surface p-6 shadow-lg shadow-black/10">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Heavy Users</p>
              <h2 className="text-xl font-semibold text-white">활성 사용자 목록</h2>
            </div>
            {usersLoading && (
              <span className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading...
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-500">
                  <th className="border-b border-border-dark/60 py-2">사용자</th>
                  <th className="border-b border-border-dark/60 py-2">플랜</th>
                  <th className="border-b border-border-dark/60 py-2">리포트 생성 수</th>
                  <th className="border-b border-border-dark/60 py-2">최근 생성일</th>
                  <th className="border-b border-border-dark/60 py-2">최근 접속</th>
                </tr>
              </thead>
              <tbody>
                {users?.users?.map((user) => (
                  <tr key={user.id} className="border-b border-border-dark/50">
                    <td className="py-3">
                      <p className="font-semibold text-white">{user.email}</p>
                      <p className="text-xs text-slate-500">{user.id}</p>
                    </td>
                    <td className="py-3">
                      <span className="rounded-full border border-border-dark/70 px-3 py-1 text-xs font-semibold text-slate-200">
                        {user.plan}
                      </span>
                    </td>
                    <td className="py-3 text-white">{user.reportCount}</td>
                    <td className="py-3 text-slate-400">{user.lastReportAt ? new Date(user.lastReportAt).toLocaleString() : "-"}</td>
                    <td className="py-3 text-slate-400">{user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString() : "-"}</td>
                  </tr>
                ))}
                {!users?.users?.length && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500">
                      데이터가 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
