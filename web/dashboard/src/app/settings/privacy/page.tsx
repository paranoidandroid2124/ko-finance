"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import type { Route } from "next";
import clsx from "clsx";
import { AlertTriangle, DownloadCloud, Loader2, RefreshCw, ShieldCheck, X } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { SettingsSectionNav } from "@/components/settings/SettingsSectionNav";
import { SettingsDataRetentionList } from "@/components/legal";
import { EmptyState } from "@/components/ui/EmptyState";
import { useDsarRequests, useCreateDsarRequest } from "@/hooks/useDsarRequests";
import type { DsarRequest, DsarRequestType } from "@/lib/accountApi";
import { formatDateTime } from "@/lib/date";
import { DSAR_STATUS_META, DSAR_REQUEST_TYPE_META, DSAR_REQUEST_TYPE_OPTIONS } from "@/lib/dsarMeta";
import { useToastStore } from "@/store/toastStore";

const PENDING_NOTICE =
  "현재 처리 중인 DSAR 요청이 있습니다. 새로운 요청은 기존 요청이 완료된 이후 다시 시도해 주세요.";

function formatOrDash(value?: string | null) {
  return value ? formatDateTime(value, { fallback: "-" }) : "-";
}

export default function PrivacySettingsPage() {
  const showToast = useToastStore((state) => state.show);
  const dismissToast = useToastStore((state) => state.dismiss);
  const { data, isLoading, isFetching, error, refetch } = useDsarRequests();
  const createRequest = useCreateDsarRequest();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [fetchErrorToastId, setFetchErrorToastId] = useState<string | null>(null);

  const pendingCount = data?.pendingCount ?? 0;
  const hasActiveRequest = data?.hasActiveRequest ?? false;
  const isSubmitDisabled = hasActiveRequest || pendingCount > 0 || createRequest.isPending;

  const requests = useMemo<DsarRequest[]>(() => {
    const base = data?.requests ?? [];
    return [...base].sort((a, b) => {
      const aTime = Number(new Date(a.requestedAt));
      const bTime = Number(new Date(b.requestedAt));
      if (Number.isNaN(aTime) || Number.isNaN(bTime)) {
        return b.requestedAt.localeCompare(a.requestedAt);
      }
      return bTime - aTime;
    });
  }, [data?.requests]);

  const lastCompletedAt = useMemo(() => {
    const completed = requests.find((request) => request.status === "completed" && request.completedAt);
    return completed?.completedAt ?? null;
  }, [requests]);

  useEffect(() => {
    if (error && !fetchErrorToastId) {
      const id = showToast({
        title: "DSAR 요청 정보를 불러오지 못했습니다.",
        description: error.message,
        intent: "error",
      });
      setFetchErrorToastId(id);
    } else if (!error && fetchErrorToastId) {
      dismissToast(fetchErrorToastId);
      setFetchErrorToastId(null);
    }
  }, [dismissToast, error, fetchErrorToastId, showToast]);

  const handleCreateRequest = async (payload: { requestType: DsarRequestType; note?: string }) => {
    try {
      await createRequest.mutateAsync(payload);
      showToast({
        intent: "success",
        title: "요청이 접수되었습니다.",
        description: "새로운 DSAR 요청이 compliance 큐에 추가되었습니다.",
      });
      setDialogOpen(false);
    } catch (mutationError) {
      const message =
        mutationError instanceof Error ? mutationError.message : "실행 중 문제가 발생했습니다. 다시 시도해 주세요.";
      showToast({
        intent: "error",
        title: "요청 처리에 실패했습니다.",
        description: message,
      });
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <SettingsSectionNav />

        <section className="space-y-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition dark:border-border-dark dark:bg-background-cardDark">
          <header className="flex flex-col gap-4 border-b border-dashed border-border-light pb-4 dark:border-border-dark">
            <div className="flex flex-col gap-2">
              <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                <ShieldCheck className="h-4 w-4 text-primary dark:text-primary.dark" aria-hidden />
                Privacy & Data
              </div>
              <div>
                <h1 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  개인정보·데이터 관리
                </h1>
                <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  내 데이터 내보내기/삭제 요청을 제출하고 진행 상태를 확인합니다. 처리 이력은 감사 로그에 자동으로 남습니다.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {/* TODO: Pro/Team 플랜 이상에서만 노출할지 결정되면 plan/entitlement 가드를 추가합니다. */}
              <button
                type="button"
                onClick={() => setDialogOpen(true)}
                disabled={isSubmitDisabled}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
              >
                <DownloadCloud className="h-4 w-4" aria-hidden />
                새 DSAR 요청
              </button>
              <button
                type="button"
                onClick={() => refetch()}
                disabled={isFetching}
                className="inline-flex items-center gap-2 rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
              >
                {isFetching ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RefreshCw className="h-4 w-4" aria-hidden />}
                새로고침
              </button>
            </div>
            {isSubmitDisabled ? (
              <div className="flex items-center gap-2 rounded-lg bg-accent-warning/15 px-3 py-2 text-xs text-accent-warning">
                <AlertTriangle className="h-4 w-4" aria-hidden />
                {PENDING_NOTICE}
              </div>
            ) : null}
          </header>

          <div className="grid gap-3 md:grid-cols-3">
            <QueueStatCard label="처리 대기 중" value={`${pendingCount}건`} helper="접수 후 순차적으로 실행됩니다." />
            <QueueStatCard label="총 제출 건수" value={`${requests.length}건`} helper="계정 기준 DSAR 누적" />
            <QueueStatCard label="마지막 완료" value={formatOrDash(lastCompletedAt)} helper="완료 일시 기준" />
          </div>

          <RequestsPanel
            requests={requests}
            loading={isLoading}
            error={error ?? null}
            onRetry={() => refetch()}
            isFetching={isFetching}
          />

          <section className="rounded-xl border border-border-light bg-white/90 p-5 text-sm leading-relaxed text-text-secondaryLight dark:border-border-dark dark:bg-background-base dark:text-text-secondaryDark">
            <h2 className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">보존 정책 & 참고</h2>
            <SettingsDataRetentionList className="mt-3" />
            <p className="mt-4">
              개인정보 처리방침과 데이터 & 라이선스 정책은 각각{" "}
              <Link
                href={"/legal/privacy" as Route}
                className="text-primary underline-offset-2 hover:underline dark:text-primary.dark"
              >
                /legal/privacy
              </Link>{" "}
              ,{" "}
              <Link
                href={"/legal/data" as Route}
                className="text-primary underline-offset-2 hover:underline dark:text-primary.dark"
              >
                /legal/data
              </Link>{" "}
              페이지에서 자세히 확인할 수 있습니다.
            </p>
          </section>
        </section>
      </div>

      <NewDsarRequestDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleCreateRequest}
        isSubmitting={createRequest.isPending}
      />
    </AppShell>
  );
}

type RequestsPanelProps = {
  requests: DsarRequest[];
  loading: boolean;
  isFetching: boolean;
  error: Error | null;
  onRetry: () => void;
};

function RequestsPanel({ requests, loading, error, onRetry, isFetching }: RequestsPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border-light bg-white/70 px-4 py-8 text-sm text-text-secondaryLight dark:border-border-dark dark:bg-background-base dark:text-text-secondaryDark">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        DSAR 요청 내역을 불러오는 중입니다...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-accent-negative/40 bg-accent-negative/10 px-4 py-6 text-center text-sm text-accent-negative dark:border-accent-negative/30 dark:bg-accent-negative/15">
        <p className="font-semibold">요청 내역을 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs opacity-80">잠시 후 다시 시도하거나 새로고침을 눌러 주세요.</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={isFetching}
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary disabled:opacity-60 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <RefreshCw className="h-3.5 w-3.5" aria-hidden />}
          다시 시도
        </button>
      </div>
    );
  }

  if (requests.length === 0) {
    return (
      <EmptyState
        title="아직 제출된 DSAR 요청이 없습니다."
        description="서비스 이용 중 개인정보 관련 질문이 있다면 언제든지 support@ko.finance 로 문의해 주세요."
        className="rounded-xl border border-dashed border-border-light bg-white/70 px-4 py-8 dark:border-border-dark dark:bg-background-base"
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border-light bg-white/90 dark:border-border-dark dark:bg-background-base">
      <table className="min-w-full divide-y divide-border-light text-sm dark:divide-border-dark">
        <thead className="bg-border-light/40 text-xs font-semibold uppercase text-text-tertiaryLight dark:bg-border-dark/30 dark:text-text-tertiaryDark">
          <tr>
            <th scope="col" className="px-4 py-3 text-left">
              요청 일시
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              요청 타입
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              상태
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              처리 결과
            </th>
            <th scope="col" className="px-4 py-3 text-left">
              메모
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-light text-sm dark:divide-border-dark">
          {requests.map((request) => {
            const note =
              typeof request.metadata?.note === "string" && request.metadata.note.trim().length > 0
                ? request.metadata.note
                : undefined;
            const statusInfo = DSAR_STATUS_META[request.status];
            const typeMeta = DSAR_REQUEST_TYPE_META[request.requestType];
            const artifactPath = request.artifactPath ?? undefined;
            const artifactIsLink = typeof artifactPath === "string" && artifactPath.startsWith("http");
            return (
              <tr key={request.id} className="bg-white/30 dark:bg-transparent">
                <td className="whitespace-nowrap px-4 py-3 align-top">
                  <div className="font-medium text-text-primaryLight dark:text-text-primaryDark">
                    {formatDateTime(request.requestedAt, { fallback: "-" })}
                  </div>
                  <div className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                    채널: {request.channel || "compliance.queue"}
                  </div>
                </td>
                <td className="px-4 py-3 align-top">
                  <div className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{typeMeta.label}</div>
                  <div className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{typeMeta.description}</div>
                </td>
                <td className="px-4 py-3 align-top">
                  <span className={clsx("inline-flex rounded-full px-3 py-1 text-xs font-semibold", statusInfo.tone)}>
                    {statusInfo.label}
                  </span>
                  <div className="mt-1 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                    완료: {formatOrDash(request.completedAt)}
                  </div>
                </td>
                <td className="px-4 py-3 align-top">
                  {artifactPath ? (
                    artifactIsLink ? (
                      <a
                        href={artifactPath}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-semibold text-primary underline-offset-2 hover:underline dark:text-primary.dark"
                      >
                        결과 다운로드
                      </a>
                    ) : (
                      <code className="rounded bg-border-light/60 px-2 py-1 text-xs text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark">
                        {artifactPath}
                      </code>
                    )
                  ) : (
                    <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">결과 대기</span>
                  )}
                  {request.failureReason ? (
                    <p className="mt-2 inline-flex items-start gap-1 text-xs text-accent-negative">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5" aria-hidden />
                      {request.failureReason}
                    </p>
                  ) : null}
                </td>
                <td className="px-4 py-3 align-top">
                  {note ? (
                    <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{note}</p>
                  ) : (
                    <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">-</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type QueueStatCardProps = {
  label: string;
  value: string;
  helper: string;
};

function QueueStatCard({ label, value, helper }: QueueStatCardProps) {
  return (
    <div className="rounded-xl border border-border-light bg-white/80 p-4 shadow-sm dark:border-border-dark dark:bg-background-base">
      <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">{label}</p>
      <p className="mt-2 text-2xl font-bold text-text-primaryLight dark:text-text-primaryDark">{value}</p>
      <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{helper}</p>
    </div>
  );
}

type NewDsarRequestDialogProps = {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { requestType: DsarRequestType; note?: string }) => void;
  isSubmitting: boolean;
};

function NewDsarRequestDialog({ open, onClose, onSubmit, isSubmitting }: NewDsarRequestDialogProps) {
  const [requestType, setRequestType] = useState<DsarRequestType>("export");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }
    setRequestType("export");
    setNote("");
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedNote = note.trim();
    onSubmit({ requestType, note: trimmedNote.length > 0 ? trimmedNote : undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-8">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative z-10 w-full max-w-xl space-y-5 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark"
        aria-modal="true"
        role="dialog"
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">새 DSAR 요청</h2>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              요청 유형을 고르고 필요한 메모를 남겨 주세요. 처리 완료 시 이메일로 안내됩니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-light p-2 text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            <X className="h-4 w-4" aria-hidden />
            <span className="sr-only">닫기</span>
          </button>
        </div>

        <div className="grid gap-3">
          {DSAR_REQUEST_TYPE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isActive = requestType === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setRequestType(option.value)}
                className={clsx(
                  "flex items-start gap-3 rounded-xl border px-3 py-3 text-left transition",
                  isActive
                    ? "border-primary bg-primary/10 text-text-primaryLight dark:border-primary.dark dark:bg-primary.dark/15"
                    : "border-border-light text-text-secondaryLight hover:border-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark",
                )}
              >
                <span className="rounded-full bg-primary/15 p-2 text-primary dark:bg-primary.dark/20 dark:text-primary.dark">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    {option.label}
                  </span>
                  <span className="mt-1 block text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    {option.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <label className="block text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
          추가 메모 (선택)
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            placeholder="특이 사항이나 참고해야 할 내용을 적어 주세요."
            className="mt-2 w-full rounded-lg border border-border-light bg-white/90 px-3 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-base dark:text-text-primaryDark"
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            취소
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-primary.dark dark:hover:bg-primary.dark/90"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            요청 보내기
          </button>
        </div>
      </form>
    </div>
  );
}
