"use client";

import Link from "next/link";
import type { Route } from "next";
import { ShieldCheck } from "lucide-react";

import { SettingsDataRetentionList } from "@/components/legal";
import { useDsarRequests, useCreateDsarRequest } from "@/hooks/useDsarRequests";
import type { DsarRequest, DsarRequestType } from "@/lib/accountApi";
import { DSAR_STATUS_META, DSAR_REQUEST_TYPE_META } from "@/lib/dsarMeta";
import { useToastStore } from "@/store/toastStore";

const ACTION_TYPES: DsarRequestType[] = ["export", "delete"];

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function LegalDataCard() {
  const toast = useToastStore((state) => state.show);
  const { data, isLoading, error } = useDsarRequests();
  const { mutateAsync, isPending } = useCreateDsarRequest();

  const hasActiveRequest = Boolean(data?.hasActiveRequest);

  const handleSubmit = async (requestType: DsarRequestType) => {
    try {
      await mutateAsync({ requestType });
      toast({ title: "요청 접수", description: "DSAR 요청이 접수되었습니다.", intent: "success" });
    } catch (err) {
      toast({
        title: "요청 실패",
        description: err instanceof Error ? err.message : "요청 처리 중 문제가 발생했습니다.",
        intent: "error",
      });
    }
  };

  const currentRequests = data?.requests ?? [];

  return (
    <section className="rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
          <ShieldCheck className="h-4 w-4 text-primary dark:text-primary.dark" />
          법무 & 데이터 관리
        </div>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          보존 정책과 DSAR 요청 현황을 확인하고, 개인정보 내보내기·삭제 요청을 직접 제출할 수 있습니다.
        </p>
      </header>

      <div className="mt-4 rounded-lg border border-border-light bg-white/70 p-4 text-xs leading-relaxed text-text-secondaryLight dark:border-border-dark dark:bg-background-base dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">기본 보존 정책</p>
        <SettingsDataRetentionList className="mt-2" />
        <p className="mt-4">
          세부 정책과 DSAR 절차는{" "}
          <Link
            href={"/legal/privacy" as Route}
            className="text-primary underline-offset-2 hover:underline dark:text-primary.dark"
          >
            개인정보 처리방침
          </Link>{" "}
          및{" "}
          <Link
            href={"/legal/data" as Route}
            className="text-primary underline-offset-2 hover:underline dark:text-primary.dark"
          >
            데이터 & 라이선스 정책
          </Link>{" "}
          페이지에서 확인할 수 있습니다.
        </p>
        <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          상세 이력과 처리 현황은{" "}
          <Link
            href={"/settings/privacy" as Route}
            className="text-primary underline-offset-2 hover:underline dark:text-primary.dark"
          >
            개인정보·데이터 관리 화면
          </Link>{" "}
          에서 언제든지 확인할 수 있습니다.
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {ACTION_TYPES.map((type) => {
          const meta = DSAR_REQUEST_TYPE_META[type];
          const Icon = meta.icon;
          const disabled = hasActiveRequest || isPending;
          return (
            <button
              key={type}
              type="button"
              disabled={disabled}
              onClick={() => handleSubmit(type)}
              className="inline-flex min-w-[180px] flex-1 items-center justify-center gap-2 rounded-lg border border-border-light px-4 py-2 text-xs font-semibold text-text-primaryLight transition hover:border-primary hover:text-primary disabled:opacity-60 dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
            >
              <Icon className="h-4 w-4" aria-hidden />
              {`${meta.label} 요청`}
            </button>
          );
        })}
      </div>

      {hasActiveRequest ? (
        <p className="mt-2 rounded-lg bg-accent-warning/15 px-3 py-2 text-xs text-accent-warning">
          처리 중인 요청이 있어 새로운 DSAR 요청은 잠시 후 다시 시도해 주세요.
        </p>
      ) : null}

      <div className="mt-6">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 요청</h3>
          {error ? (
            <span className="text-xs text-accent-negative">요청 내역을 불러오지 못했습니다.</span>
          ) : null}
        </div>

        {isLoading ? (
          <p className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">불러오는 중...</p>
        ) : currentRequests.length === 0 ? (
          <p className="mt-3 rounded-lg border border-dashed border-border-light px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            아직 접수된 DSAR 요청이 없습니다.
          </p>
        ) : (
          <div className="mt-3 space-y-2">
            {currentRequests.map((request) => {
              const statusInfo = DSAR_STATUS_META[request.status];
              const meta = DSAR_REQUEST_TYPE_META[request.requestType];
              return (
                <div
                  key={request.id}
                  className="rounded-lg border border-border-light bg-white/80 px-3 py-2 text-xs dark:border-border-dark dark:bg-background-base"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      {meta.label} 요청
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] ${statusInfo.tone}`}>
                      {statusInfo.label}
                    </span>
                  </div>
                  <div className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">
                    접수: {formatDate(request.requestedAt)} · 완료: {formatDate(request.completedAt)}
                  </div>
                  {request.artifactPath ? (
                    <div className="mt-1 text-text-tertiaryLight dark:text-text-tertiaryDark">
                      결과 파일: <code className="font-mono text-[11px]">{request.artifactPath}</code>
                    </div>
                  ) : null}
                  {request.failureReason ? (
                    <div className="mt-1 text-accent-negative">{request.failureReason}</div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
