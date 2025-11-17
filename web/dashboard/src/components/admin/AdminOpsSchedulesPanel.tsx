"use client";

import { useEffect, useRef, useState } from "react";

import clsx from "classnames";

import {
  AdminButtonSpinner,
  AdminSuccessIcon,
} from "@/components/admin/adminFormUtils";
import {
  useOpsRunHistory,
  useOpsSchedules,
  useTriggerOpsSchedule,
} from "@/hooks/useAdminConfig";
import { formatDateTime } from "@/lib/date";
import type { ToastInput } from "@/store/toastStore";

type BadgePreset = {
  label: string;
  className: string;
};

const SCHEDULE_STATUS_BADGES: Record<string, BadgePreset> = {
  active: {
    label: "활성",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
  },
  paused: {
    label: "일시 중지",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200",
  },
};

const RUN_STATUS_BADGES: Record<string, BadgePreset> = {
  completed: {
    label: "완료",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
  },
  running: {
    label: "진행 중",
    className: "bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-200",
  },
  queued: {
    label: "대기",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200",
  },
  failed: {
    label: "실패",
    className: "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
  },
};

const NEUTRAL_BADGE: BadgePreset = {
  label: "확인 필요",
  className: "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark",
};

const resolveBadge = (status: string | undefined, presets: Record<string, BadgePreset>): BadgePreset => {
  if (!status) {
    return NEUTRAL_BADGE;
  }
  const normalized = status.toLowerCase();
  return presets[normalized] ?? { ...NEUTRAL_BADGE, label: status };
};

interface AdminOpsSchedulesPanelProps {
  adminActor?: string | null;
  toast: (toast: ToastInput) => string;
}

export function AdminOpsSchedulesPanel({ adminActor, toast }: AdminOpsSchedulesPanelProps) {
  const { data: schedulesData, isLoading: isSchedulesLoading, refetch: refetchSchedules } = useOpsSchedules(true);
  const { data: runHistoryData, refetch: refetchRunHistory } = useOpsRunHistory(true);
  const triggerSchedule = useTriggerOpsSchedule();

  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [recentJobSuccessId, setRecentJobSuccessId] = useState<string | null>(null);
  const scheduleSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (scheduleSuccessTimer.current) {
        clearTimeout(scheduleSuccessTimer.current);
      }
    };
  }, []);

  const handleTriggerSchedule = async (jobId: string) => {
    try {
      setPendingJobId(jobId);
      await triggerSchedule.mutateAsync({
        jobId,
        payload: {
          actor: adminActor ?? "unknown-admin",
          note: "수동 트리거",
        },
      });
      toast({
        id: `admin/ops/schedule/${jobId}`,
        title: "스케줄이 큐에 등록됐어요",
        message: `${jobId} 작업이 곧 실행돼요.`,
        intent: "success",
      });
      setRecentJobSuccessId(jobId);
      if (scheduleSuccessTimer.current) {
        clearTimeout(scheduleSuccessTimer.current);
      }
      scheduleSuccessTimer.current = setTimeout(() => {
        setRecentJobSuccessId((current) => (current === jobId ? null : current));
      }, 1800);
      await Promise.all([refetchSchedules(), refetchRunHistory()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "스케줄 실행 요청에 실패했어요.";
      toast({
        id: `admin/ops/schedule/${jobId}/error`,
        title: "스케줄 실행 실패",
        message,
        intent: "error",
      });
    } finally {
      setPendingJobId((current) => (current === jobId ? null : current));
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          Celery 스케줄
        </h3>
        <button
          type="button"
          onClick={() => refetchSchedules()}
          className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition duration-150 hover:bg-border-light/30 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isSchedulesLoading}
        >
          새로고침
        </button>
      </div>

      <div className="space-y-2">
        {schedulesData?.jobs?.length ? (
          schedulesData.jobs.map((job) => {
            const statusBadge = resolveBadge(job.status, SCHEDULE_STATUS_BADGES);
            const nextRunLabel = job.nextRunAt ? `다음 실행: ${formatDateTime(job.nextRunAt, { fallback: "시간 정보 없음" })}` : "다음 실행: 미정";
            const isJobPending = triggerSchedule.isPending && pendingJobId === job.id;
            return (
              <div
                key={job.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-light bg-background-cardLight px-3 py-2 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold">{job.id}</p>
                    <span
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                        statusBadge.className,
                      )}
                    >
                      {statusBadge.label}
                    </span>
                  </div>
                  <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                    {job.task} · {job.interval} · {nextRunLabel}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleTriggerSchedule(job.id)}
                  disabled={isJobPending}
                  className={clsx(
                    "inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white transition duration-150 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                    isJobPending && "cursor-not-allowed opacity-60",
                  )}
                >
                  {isJobPending ? (
                    <>
                      <AdminButtonSpinner className="border-white/40 border-t-white" />
                      <span>요청 중…</span>
                    </>
                  ) : recentJobSuccessId === job.id ? (
                    <>
                      <AdminSuccessIcon className="text-white" />
                      <span>등록 완료</span>
                    </>
                  ) : (
                    "수동 실행"
                  )}
                </button>
              </div>
            );
          })
        ) : (
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">등록된 스케줄이 아직 없어요.</p>
        )}
      </div>

      <div>
        <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">
          최근 실행 기록
        </h4>
        <div className="mt-2 space-y-2">
          {runHistoryData?.runs?.length ? (
            runHistoryData.runs.slice(0, 6).map((run) => {
              const runBadge = resolveBadge(run.status, RUN_STATUS_BADGES);
              return (
                <div
                  key={run.id}
                  className="rounded-lg border border-border-light bg-background-cardLight px-3 py-2 text-xs dark:border-border-dark dark:bg-background-cardDark"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{run.task}</span>
                    <span
                      className={clsx(
                        "rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                        runBadge.className,
                      )}
                    >
                      {runBadge.label}
                    </span>
                  </div>
                  <p className="text-text-secondaryLight dark:text-text-secondaryDark">
                    {formatDateTime(run.startedAt, { fallback: "시간 정보 없음" })} · 요청자: {run.actor ?? "—"}
                  </p>
                  {run.note ? (
                    <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">메모: {run.note}</p>
                  ) : null}
                </div>
              );
            })
          ) : (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">실행 기록이 아직 없어요.</p>
          )}
        </div>
      </div>
    </section>
  );
}
