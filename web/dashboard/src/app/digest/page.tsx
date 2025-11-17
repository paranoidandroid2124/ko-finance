"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { RefreshCw, Send, Mail, Slack } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { DigestCard, type DigestPayload } from "@/components/digest/DigestCard";
import { sampleDigest } from "@/components/digest/sampleData";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { PlanLock } from "@/components/ui/PlanLock";
import { useDigestPreview } from "@/hooks/useDigestPreview";
import {
  useDispatchWatchlistDigest,
  useWatchlistSchedules,
  useCreateWatchlistSchedule,
  useUpdateWatchlistSchedule,
  useDeleteWatchlistSchedule,
} from "@/hooks/useAlerts";
import { formatDateTime } from "@/lib/date";
import { logEvent } from "@/lib/telemetry";
import type { WatchlistDigestSchedule, WatchlistDigestSchedulePayload } from "@/lib/alertsApi";
import { useToastStore } from "@/store/toastStore";
import { usePlanStore } from "@/store/planStore";

const TIMEFRAME_OPTIONS: Array<{ value: "daily" | "weekly"; label: string }> = [
  { value: "daily", label: "Daily Digest" },
  { value: "weekly", label: "Weekly Highlight" },
];

const WINDOW_OPTIONS = [
  { label: "최근 24시간", value: 1440 },
  { label: "최근 12시간", value: 720 },
  { label: "최근 6시간", value: 360 },
];

const SCHEDULE_TIMEZONES = ["Asia/Seoul", "UTC", "America/New_York", "Europe/London", "Asia/Tokyo"];

type ScheduleDialogState = {
  mode: "create" | "edit";
  schedule?: WatchlistDigestSchedule;
};

export default function DigestPage() {
  const [timeframe, setTimeframe] = useState<"daily" | "weekly">("daily");
  const [windowMinutes, setWindowMinutes] = useState(1440);
  const [emailTargets, setEmailTargets] = useState("");
  const [slackTargets, setSlackTargets] = useState("");

  const { data, isLoading, isFetching, isError, refetch } = useDigestPreview({ timeframe });
  const dispatchDigest = useDispatchWatchlistDigest();
  const showToast = useToastStore((state) => state.show);
  const planMemoryFlags = usePlanStore((state) => state.memoryFlags);
  const {
    data: scheduleData,
    isLoading: isScheduleLoading,
    error: scheduleError,
  } = useWatchlistSchedules(Boolean(planMemoryFlags.digest));
  const createSchedule = useCreateWatchlistSchedule();
  const updateSchedule = useUpdateWatchlistSchedule();
  const deleteSchedule = useDeleteWatchlistSchedule();
  const [scheduleDialog, setScheduleDialog] = useState<ScheduleDialogState | null>(null);

  const payload: DigestPayload & { emailHtml?: string } = useMemo(() => {
    if (!data) {
      return sampleDigest;
    }
    return data;
  }, [data]);

  const isEmpty = Boolean(data) && payload.news.length === 0 && payload.watchlist.length === 0;
  const digestAllowed = Boolean(planMemoryFlags.digest);
  const schedules = scheduleData ?? [];
  const scheduleMutationPending = createSchedule.isPending || updateSchedule.isPending || deleteSchedule.isPending;
  const scheduleToPayload = (
    schedule: WatchlistDigestSchedule,
    overrides: Partial<WatchlistDigestSchedulePayload> = {},
  ): WatchlistDigestSchedulePayload => ({
    label: schedule.label,
    timeOfDay: schedule.timeOfDay,
    timezone: schedule.timezone,
    weekdaysOnly: schedule.weekdaysOnly,
    windowMinutes: schedule.windowMinutes,
    limit: schedule.limit,
    slackTargets: schedule.slackTargets,
    emailTargets: schedule.emailTargets,
    enabled: schedule.enabled,
    ...overrides,
  });

  const handleDispatch = async () => {
    const normalizeList = (value: string) =>
      value
        .split(/[,\\s]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    try {
      const result = await dispatchDigest.mutateAsync({
        windowMinutes,
        slackTargets: normalizeList(slackTargets),
        emailTargets: normalizeList(emailTargets),
      });
      const emailDelivered = result.results.find((entry) => entry.channel === "email")?.delivered ?? 0;
      const slackDelivered = result.results.find((entry) => entry.channel === "slack")?.delivered ?? 0;
      showToast({
        id: "digest-dispatch-success",
        title: "Digest를 전송했어요",
        message: `이메일 ${emailDelivered}건 · Slack ${slackDelivered}건 전송을 요청했습니다.`,
        intent: "success",
      });
    } catch (error) {
      showToast({
        id: "digest-dispatch-error",
        title: "Digest 전송 실패",
        message: error instanceof Error ? error.message : "잠시 후 다시 시도해 주세요.",
        intent: "error",
      });
    }
  };

  const handleScheduleSubmit = async (input: WatchlistDigestSchedulePayload, scheduleId?: string) => {
    try {
      if (scheduleId) {
        await updateSchedule.mutateAsync({ id: scheduleId, payload: input });
        showToast({
          id: `digest-schedule-${scheduleId}`,
          title: "Digest 스케줄이 업데이트됐어요",
          message: "설정이 저장되었습니다.",
          intent: "success",
        });
      } else {
        await createSchedule.mutateAsync(input);
        showToast({
          id: "digest-schedule-created",
          title: "새 Digest 스케줄을 만들었어요",
          message: "첫 자동 발송을 기다려 주세요.",
          intent: "success",
        });
      }
      setScheduleDialog(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "스케줄을 저장하지 못했어요.";
      showToast({
        id: "digest-schedule-error",
        title: "스케줄 저장 실패",
        message,
        intent: "error",
      });
    }
  };

  const handleToggleSchedule = async (schedule: WatchlistDigestSchedule, enabled: boolean) => {
    try {
      await updateSchedule.mutateAsync({ id: schedule.id, payload: scheduleToPayload(schedule, { enabled }) });
      showToast({
        id: `digest-schedule-toggle-${schedule.id}`,
        title: enabled ? "스케줄을 다시 활성화했어요" : "스케줄을 일시 중지했어요",
        message: enabled ? "다음 스케줄부터 자동 발송이 재개됩니다." : "자동 발송이 중지되었습니다.",
        intent: "info",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "스케줄 상태를 변경하지 못했어요.";
      showToast({
        id: `digest-schedule-toggle-${schedule.id}-error`,
        title: "상태 변경 실패",
        message,
        intent: "error",
      });
    }
  };

  const handleDeleteSchedule = async (schedule: WatchlistDigestSchedule) => {
    try {
      await deleteSchedule.mutateAsync(schedule.id);
      showToast({
        id: `digest-schedule-delete-${schedule.id}`,
        title: "스케줄을 삭제했어요",
        message: "자동 발송 목록에서 제거되었습니다.",
        intent: "info",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "스케줄을 삭제하지 못했어요.";
      showToast({
        id: `digest-schedule-delete-${schedule.id}-error`,
        title: "스케줄 삭제 실패",
        message,
        intent: "error",
      });
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <section className="rounded-3xl border border-border-light bg-gradient-to-r from-background-cardLight via-white to-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:from-background-cardDark dark:via-background-baseDark dark:to-background-cardDark">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
                Digest Studio
              </p>
              <h1 className="mt-1 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
                공시·뉴스 Digest를 한 번에
              </h1>
              <p className="mt-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                Preview와 HTML 템플릿을 확인하고, 워치리스트 Digest를 이메일/Slack으로 바로 보낼 수 있어요.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {TIMEFRAME_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTimeframe(option.value)}
                  className={clsx(
                    "rounded-full border px-4 py-1.5 text-sm font-semibold transition",
                    timeframe === option.value
                      ? "border-primary bg-primary text-white"
                      : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark",
                  )}
                >
                  {option.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex items-center gap-2 rounded-full border border-border-light px-4 py-1.5 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                disabled={isFetching}
              >
                <RefreshCw className={clsx("h-4 w-4", isFetching ? "animate-spin" : "")} />
                새로고침
              </button>
            </div>
          </div>
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionTitle
            title="Digest Preview"
            description="Daily/Weekly Digest의 카드 미리보기입니다."
          />
          {isError ? (
            <ErrorState
              title="다이제스트 데이터를 불러오지 못했어요"
              description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
            />
          ) : isLoading && !data ? (
            <div className="mt-4 flex justify-center">
              <SkeletonBlock className="h-[640px] w-full max-w-4xl rounded-3xl" />
            </div>
          ) : (
            <div className="mt-4 flex justify-center">
              <DigestCard data={payload} isEmpty={isEmpty} />
            </div>
          )}
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionTitle
            title="Email Template"
            description="LLM Insight/뉴스/워치리스트 블록으로 구성된 HTML 템플릿입니다."
          />
          {payload.emailHtml ? (
            <div className="mt-4 rounded-2xl border border-border-light bg-background-base dark:border-border-dark dark:bg-background-baseDark">
              <iframe
                title="Digest Email Preview"
                srcDoc={payload.emailHtml}
                className="h-[600px] w-full rounded-2xl"
              />
            </div>
          ) : (
            <p className="mt-4 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              해당 프리뷰에는 이메일 템플릿 정보가 아직 포함되지 않았습니다.
            </p>
          )}
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionTitle
            title="Watchlist Digest 전송"
            description="워치리스트 알림을 하루 기준으로 묶어 Slack/Email로 발송합니다."
          />
          {!digestAllowed ? (
            <PlanLock
              requiredTier="pro"
              title="Digest 기능은 Pro 이상 플랜에서 제공됩니다"
              description="Digest 메모리 기능을 활성화하려면 플랜을 업그레이드하세요."
            />
          ) : (
            <>
              <div className="mt-4 flex flex-wrap gap-2">
                {WINDOW_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setWindowMinutes(option.value)}
                    className={clsx(
                      "rounded-full border px-3 py-1 text-xs font-semibold transition",
                      windowMinutes === option.value
                        ? "border-primary bg-primary text-white"
                        : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <DigestTargetField
                  icon={<Mail className="h-4 w-4" />}
                  label="Email Targets"
                  placeholder="alerts@company.com, research@company.com"
                  value={emailTargets}
                  onChange={setEmailTargets}
                />
                <DigestTargetField
                  icon={<Slack className="h-4 w-4" />}
                  label="Slack Channels"
                  placeholder="#invest-alerts, #digest"
                  value={slackTargets}
                  onChange={setSlackTargets}
                />
              </div>
              <button
                type="button"
                onClick={handleDispatch}
                disabled={dispatchDigest.isPending}
                className="mt-4 inline-flex items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:opacity-70"
              >
                <Send className="h-4 w-4" />
                {dispatchDigest.isPending ? "전송 중…" : "Digest 전송"}
              </button>
              <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                대상은 공백/쉼표로 구분해 입력하세요. Slack은 Incoming Webhook 채널 혹은 채널명을 입력하면 됩니다.
              </p>
            </>
          )}
        </section>

        <section className="rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <SectionTitle
            title="자동 Digest 스케줄"
            description="원하는 시간대에 Slack/Email로 Digest를 자동 발송해 보세요."
          />
          {!digestAllowed ? (
            <PlanLock
              requiredTier="pro"
              title="Digest 기능은 Pro 이상 플랜에서 제공됩니다"
              description="스케줄 기능을 사용하려면 Digest 메모리 기능을 활성화해 주세요."
            />
          ) : scheduleError ? (
            <ErrorState
              title="스케줄 정보를 불러오지 못했어요"
              description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
            />
          ) : isScheduleLoading ? (
            <div className="mt-4">
              <SkeletonBlock lines={4} />
            </div>
          ) : schedules.length === 0 ? (
            <EmptyState
              title="등록된 Digest 스케줄이 없어요"
              description="매일 아침 자동으로 Digest를 받고 싶다면 스케줄을 만들어 보세요."
              action={
                <button
                  type="button"
                  onClick={() => setScheduleDialog({ mode: "create" })}
                  className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                  disabled={scheduleMutationPending}
                >
                  새 스케줄 추가
                </button>
              }
            />
          ) : (
            <div className="mt-4 space-y-3">
              {schedules.map((schedule) => (
                <DigestScheduleCard
                  key={schedule.id}
                  schedule={schedule}
                  onEdit={() => setScheduleDialog({ mode: "edit", schedule })}
                  onToggle={(nextEnabled) => void handleToggleSchedule(schedule, nextEnabled)}
                  onDelete={() => void handleDeleteSchedule(schedule)}
                />
              ))}
            </div>
          )}
          {digestAllowed && schedules.length > 0 ? (
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setScheduleDialog({ mode: "create" })}
                className="inline-flex items-center gap-2 rounded-full border border-border-light px-4 py-1.5 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                disabled={scheduleMutationPending}
              >
                새 스케줄 추가
              </button>
            </div>
          ) : null}
        </section>
      </div>
      {scheduleDialog ? (
        <DigestScheduleDialog
          state={scheduleDialog}
          isSubmitting={scheduleMutationPending}
          onClose={() => setScheduleDialog(null)}
          onSubmit={handleScheduleSubmit}
        />
      ) : null}
    </AppShell>
  );
}

function SectionTitle({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h2>
      <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
    </div>
  );
}

function DigestTargetField({
  icon,
  label,
  placeholder,
  value,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 rounded-2xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-baseDark">
      <span className="flex items-center gap-2 text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
        {icon}
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={2}
        className="resize-none rounded-xl border border-border-light bg-background-cardLight px-3 py-2 text-sm text-text-primaryLight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
      />
    </label>
  );
}

type DigestScheduleCardProps = {
  schedule: WatchlistDigestSchedule;
  onEdit: () => void;
  onToggle: (enabled: boolean) => void;
  onDelete: () => void;
};

function DigestScheduleCard({ schedule, onEdit, onToggle, onDelete }: DigestScheduleCardProps) {
  const nextRunLabel = formatDateTime(schedule.nextDispatchAt, { includeSeconds: false, fallback: "예정 없음" });
  const lastRunLabel = formatDateTime(schedule.lastDispatchedAt, { includeSeconds: false, fallback: "기록 없음" });
  const statusLabel =
    schedule.lastStatus === "failed" ? "전송 실패" : schedule.lastStatus === "success" ? "전송 완료" : "대기 중";

  return (
    <div className="rounded-2xl border border-border-light bg-background-base p-4 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">{schedule.label}</p>
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {schedule.timeOfDay} · {schedule.timezone} · {schedule.weekdaysOnly ? "평일" : "매일"}
          </p>
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">다음 실행: {nextRunLabel}</p>
        </div>
        <span
          className={clsx(
            "rounded-full px-3 py-1 text-xs font-semibold",
            schedule.enabled
              ? "bg-primary/10 text-primary"
              : "bg-border-light text-text-secondaryLight dark:bg-border-dark dark:text-text-secondaryDark",
          )}
        >
          {schedule.enabled ? "활성" : "일시 중지"}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        {schedule.emailTargets.map((target) => (
          <span key={`email-${schedule.id}-${target}`} className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">
            Email · {target}
          </span>
        ))}
        {schedule.slackTargets.map((target) => (
          <span key={`slack-${schedule.id}-${target}`} className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">
            Slack · {target}
          </span>
        ))}
      </div>
      <div className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        최근 실행: {lastRunLabel} · 상태: {statusLabel}
        {schedule.lastError ? ` (${schedule.lastError})` : ""}
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <button
          type="button"
          onClick={onEdit}
          className="rounded-full border border-border-light px-4 py-1 text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
        >
          편집
        </button>
        <button
          type="button"
          onClick={() => onToggle(!schedule.enabled)}
          className="rounded-full border border-border-light px-4 py-1 text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
        >
          {schedule.enabled ? "일시 중지" : "다시 활성화"}
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="rounded-full border border-rose-200 px-4 py-1 text-rose-600 transition hover:border-rose-400 hover:text-rose-700 dark:border-rose-400 dark:text-rose-300"
        >
          삭제
        </button>
      </div>
    </div>
  );
}

type DigestScheduleDialogProps = {
  state: ScheduleDialogState;
  onClose: () => void;
  onSubmit: (payload: WatchlistDigestSchedulePayload, scheduleId?: string) => Promise<void>;
  isSubmitting: boolean;
};

function DigestScheduleDialog({ state, onClose, onSubmit, isSubmitting }: DigestScheduleDialogProps) {
  const isEdit = state.mode === "edit" && state.schedule;
  const [form, setForm] = useState({
    label: state.schedule?.label ?? "아침 Digest",
    timeOfDay: state.schedule?.timeOfDay ?? "08:30",
    timezone: state.schedule?.timezone ?? SCHEDULE_TIMEZONES[0],
    weekdaysOnly: state.schedule?.weekdaysOnly ?? true,
    windowMinutes: state.schedule?.windowMinutes ?? 1440,
    limit: state.schedule?.limit ?? 20,
    slackTargets: (state.schedule?.slackTargets ?? []).join(", "),
    emailTargets: (state.schedule?.emailTargets ?? []).join(", "),
    enabled: state.schedule?.enabled ?? true,
  });

  const handleChange = (key: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    const normalizeList = (value: string) =>
      value
        .split(/[\s,;]+/)
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
    await onSubmit(
      {
        label: form.label,
        timeOfDay: form.timeOfDay,
        timezone: form.timezone,
        weekdaysOnly: form.weekdaysOnly,
        windowMinutes: Number(form.windowMinutes),
        limit: Number(form.limit),
        slackTargets: normalizeList(form.slackTargets),
        emailTargets: normalizeList(form.emailTargets),
        enabled: form.enabled,
      },
      state.schedule?.id,
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-xl rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              {isEdit ? "스케줄 편집" : "새 스케줄"}
            </p>
            <h3 className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark">
              {isEdit ? state.schedule?.label : "워치리스트 Digest"}
            </h3>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              매일 특정 시간에 자동으로 Digest를 보내도록 예약합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border-light p-1 text-text-secondaryLight transition hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">라벨</span>
            <input
              value={form.label}
              onChange={(event) => handleChange("label", event.target.value)}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">시간</span>
            <input
              type="time"
              value={form.timeOfDay}
              onChange={(event) => handleChange("timeOfDay", event.target.value)}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">시간대</span>
            <select
              value={form.timezone}
              onChange={(event) => handleChange("timezone", event.target.value)}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            >
              {SCHEDULE_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.weekdaysOnly}
              onChange={(event) => handleChange("weekdaysOnly", event.target.checked)}
              className="h-4 w-4 rounded border border-border-light text-primary focus:ring-primary dark:border-border-dark"
            />
            <span className="text-text-secondaryLight dark:text-text-secondaryDark">평일에만 실행</span>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">윈도우</span>
            <select
              value={form.windowMinutes}
              onChange={(event) => handleChange("windowMinutes", Number(event.target.value))}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            >
              {WINDOW_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-semibold text-text-secondaryLight dark:text-text-secondaryDark">알림 제한</span>
            <input
              type="number"
              min={1}
              max={200}
              value={form.limit}
              onChange={(event) => handleChange("limit", Number(event.target.value))}
              className="rounded-xl border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <DigestTargetField
            icon={<Mail className="h-4 w-4" />}
            label="Email Targets"
            placeholder="alerts@company.com"
            value={form.emailTargets}
            onChange={(value) => handleChange("emailTargets", value)}
          />
          <DigestTargetField
            icon={<Slack className="h-4 w-4" />}
            label="Slack Channels"
            placeholder="#watchlist-alerts"
            value={form.slackTargets}
            onChange={(value) => handleChange("slackTargets", value)}
          />
        </div>

        <label className="mt-4 flex items-center gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => handleChange("enabled", event.target.checked)}
            className="h-4 w-4 rounded border border-border-light text-primary focus:ring-primary dark:border-border-dark"
          />
          스케줄 활성화
        </label>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-2xl border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary dark:border-border-dark dark:text-text-secondaryDark"
            disabled={isSubmitting}
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="w-full rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:opacity-70"
          >
            {isSubmitting ? "저장 중…" : isEdit ? "스케줄 업데이트" : "스케줄 생성"}
          </button>
        </div>
      </div>
    </div>
  );
}
