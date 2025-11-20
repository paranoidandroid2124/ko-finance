"use client";

import { useEffect, useRef, useState } from "react";

import clsx from "classnames";

import {
  AdminButtonSpinner,
  AdminSuccessIcon,
  formatJsonValue,
  parseJsonRecord,
} from "@/components/admin/adminFormUtils";
import {
  useCreateOpsAlertChannel,
  useOpsAlertChannels,
  usePreviewOpsAlertChannel,
  useUpdateOpsAlertChannelStatus,
  useUpdateOpsAlertChannels,
} from "@/hooks/useAdminConfig";
import type { AdminOpsAlertChannel, AdminOpsAlertChannelPreviewResult } from "@/lib/adminApi";
import { formatDateTime } from "@/lib/date";
import type { ToastInput } from "@/store/toastStore";

type AlertChannelDraft = {
  key: string;
  label: string;
  channelType: string;
  enabled: boolean;
  targetsText: string;
  metadataJson: string;
  template: string;
  messageTemplate: string;
  description: string;
};

const ALERT_CHANNEL_TEMPLATE_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  email: [
    { value: "default", label: "표준 본문" },
  ],
  telegram: [
    { value: "default", label: "표준" },
    { value: "compact", label: "컴팩트" },
  ],
  slack: [
    { value: "default", label: "텍스트 카드" },
    { value: "blocks", label: "리치 블록" },
  ],
  webhook: [{ value: "default", label: "표준 JSON" }],
  pagerduty: [{ value: "default", label: "표준" }],
};

const ALERT_SECTION_ORDER: Array<{ value: string; label: string }> = [
  { value: "telegram", label: "텔레그램" },
  { value: "email", label: "이메일" },
  { value: "slack", label: "슬랙" },
  { value: "webhook", label: "Webhook" },
  { value: "pagerduty", label: "PagerDuty" },
];

const parseTargetsInput = (value: string): string[] => {
  if (!value) {
    return [];
  }
  const seen = new Set<string>();
  return value
    .split(/[\r\n,;]+/)
    .map((entry) => entry.trim())
    .filter((entry) => {
      if (!entry || seen.has(entry)) {
        return false;
      }
      seen.add(entry);
      return true;
    });
};

const stringifyTargets = (targets?: string[] | null): string => {
  if (!targets || targets.length === 0) {
    return "";
  }
  return targets.join("\n");
};

const slugify = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const generateChannelKey = (label: string, fallback: string) => {
  const slug = slugify(label);
  if (slug) {
    return slug;
  }
  return `${fallback}-${Math.random().toString(36).slice(2, 8)}`;
};

interface AdminAlertChannelsPanelProps {
  adminActor?: string | null;
  toast: (toast: ToastInput) => string;
}

export function AdminAlertChannelsPanel({ adminActor, toast }: AdminAlertChannelsPanelProps) {
  const { data: alertChannelsData, isLoading: isAlertChannelsLoading, refetch: refetchAlertChannels } =
    useOpsAlertChannels(true);
  const updateAlertChannels = useUpdateOpsAlertChannels();
  const createAlertChannel = useCreateOpsAlertChannel();
  const updateAlertChannelStatus = useUpdateOpsAlertChannelStatus();
  const previewAlertChannel = usePreviewOpsAlertChannel();

  const [alertDraft, setAlertDraft] = useState<{
    channels: AlertChannelDraft[];
    actor: string;
    note: string;
    error?: string | null;
  }>({
    channels: [],
    actor: "",
    note: "",
  });
  const [alertSaveSuccess, setAlertSaveSuccess] = useState(false);
  const alertSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState<AlertChannelDraft>({
    key: "",
    label: "",
    channelType: "telegram",
    enabled: true,
    targetsText: "",
    metadataJson: "{}",
    template: "default",
    messageTemplate: "",
    description: "",
  });
  const [createNote, setCreateNote] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [previewSampleMessage, setPreviewSampleMessage] = useState("새로운 안내 메시지를 여기에 입력해 주세요.");
  const [previewState, setPreviewState] = useState<{
    targetKey: string | null;
    result?: AdminOpsAlertChannelPreviewResult;
    isOpen: boolean;
    isLoading: boolean;
    error?: string | null;
  }>({
    targetKey: null,
    isOpen: false,
    isLoading: false,
  });
  const previewRenderedJson = previewState.result ? JSON.stringify(previewState.result.rendered, null, 2) : "";

  useEffect(() => {
    if (!alertChannelsData) {
      return;
    }
    setAlertDraft((prev) => ({
      channels:
        alertChannelsData.channels?.map((channel) => ({
          key: channel.key,
          label: channel.label,
          channelType: channel.channelType,
          enabled: channel.enabled,
          targetsText: stringifyTargets(channel.targets),
          metadataJson: formatJsonValue(channel.metadata, "{}"),
          template: channel.template ?? "default",
          messageTemplate: channel.messageTemplate ?? "",
          description: channel.description ?? "",
        })) ?? [],
      actor: adminActor ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [alertChannelsData, adminActor]);

  useEffect(() => {
    return () => {
      if (alertSuccessTimer.current) {
        clearTimeout(alertSuccessTimer.current);
      }
    };
  }, []);

  const handleAddAlertChannel = () => {
    setCreateDraft({
      key: "",
      label: "",
      channelType: "telegram",
      enabled: true,
      targetsText: "",
      metadataJson: "{}",
      template: "default",
      messageTemplate: "",
      description: "",
    });
    setCreateNote("");
    setCreateError(null);
    setIsCreateOpen(true);
  };

  const handleCreateChannelTypeChange = (channelType: string) => {
    setCreateDraft((prev) => {
      const templateOptions = ALERT_CHANNEL_TEMPLATE_OPTIONS[channelType] ?? [{ value: "default", label: "표준" }];
      const nextTemplate = templateOptions.some((option) => option.value === prev.template)
        ? prev.template
        : templateOptions[0]?.value ?? "default";
      return {
        ...prev,
        channelType,
        template: nextTemplate,
      };
    });
  };

  const handleCreateFieldChange = (field: keyof AlertChannelDraft, value: string | boolean) => {
    if (field === "channelType") {
      handleCreateChannelTypeChange(String(value));
      return;
    }
    setCreateDraft((prev) => ({
      ...prev,
      [field]: field === "enabled" ? Boolean(value) : String(value),
    }));
  };

  const handleAlertChannelField = (index: number, field: keyof AlertChannelDraft, value: string | boolean) => {
    setAlertDraft((prev) => {
      const next = [...prev.channels];
      const current = { ...next[index] };
      if (field === "enabled") {
        current.enabled = Boolean(value);
      } else {
        current[field] = String(value);
      }
      next[index] = current;
      return { ...prev, channels: next };
    });
  };

  const handleCreateChannelSubmit = async () => {
    setCreateError(null);
    try {
      const metadata = parseJsonRecord(
        createDraft.metadataJson,
        `${createDraft.label || createDraft.channelType} metadata`,
      );
      const targets = parseTargetsInput(createDraft.targetsText);
      const actorValue = alertDraft.actor.trim() || adminActor || "unknown-admin";
      const label = createDraft.label.trim() || `알림 채널 ${alertDraft.channels.length + 1}`;

      await createAlertChannel.mutateAsync({
        channelType: createDraft.channelType,
        label,
        targets,
        metadata,
        template: createDraft.template.trim() || null,
        messageTemplate: createDraft.messageTemplate.trim() || null,
        description: createDraft.description.trim() || null,
        actor: actorValue,
        note: createNote.trim() || null,
      });

      toast({
        id: `admin/ops/alert-channel/create-${Date.now()}`,
        intent: "success",
        title: "새로운 채널이 준비됐어요",
        message: "방금 등록한 채널로 우리 소식이 잘 전달될 거예요.",
      });
      setIsCreateOpen(false);
      setCreateNote("");
      await refetchAlertChannels();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "새 채널을 만드는 중에 잠깐 문제가 생겼어요. 다시 시도해 주세요.";
      setCreateError(message);
      toast({
        id: `admin/ops/alert-channel/create-error-${Date.now()}`,
        intent: "error",
        title: "채널 만들기 실패",
        message,
      });
    }
  };

  const handleAlertChannelTypeChange = (index: number, channelType: string) => {
    setAlertDraft((prev) => {
      const next = [...prev.channels];
      const current = { ...next[index], channelType };
      const templateOptions = ALERT_CHANNEL_TEMPLATE_OPTIONS[channelType] ?? [{ value: "default", label: "표준" }];
      if (!templateOptions.some((option) => option.value === current.template)) {
        current.template = templateOptions[0]?.value ?? "default";
      }
      next[index] = current;
      return { ...prev, channels: next };
    });
  };

  const handleRemoveAlertChannel = (index: number) => {
    setAlertDraft((prev) => ({
      ...prev,
      channels: prev.channels.filter((_, idx) => idx !== index),
    }));
  };

  const handlePreviewChannel = async (index: number) => {
    const draft = alertDraft.channels[index];
    if (!draft) {
      return;
    }
    try {
      const metadata = parseJsonRecord(
        draft.metadataJson,
        `${draft.label || draft.key || `channel_${index + 1}`} metadata`,
      );
      const targets = parseTargetsInput(draft.targetsText);
      const baseChannel = alertChannelsData?.channels?.find((item) => item.key === draft.key);
      const payloadChannel: AdminOpsAlertChannel = {
        key: draft.key,
        label: draft.label.trim() || draft.key || `채널 ${index + 1}`,
        channelType: draft.channelType,
        enabled: draft.enabled,
        targets,
        metadata,
        template: draft.template.trim() || null,
        messageTemplate: draft.messageTemplate.trim() || null,
        description: draft.description.trim() || baseChannel?.description || null,
        createdAt: baseChannel?.createdAt ?? null,
        updatedAt: baseChannel?.updatedAt ?? null,
        disabledAt: baseChannel?.disabledAt ?? null,
        disabledBy: baseChannel?.disabledBy ?? null,
        disabledNote: baseChannel?.disabledNote ?? null,
      };
      setPreviewState({
        targetKey: draft.key,
        isOpen: true,
        isLoading: true,
        result: undefined,
        error: null,
      });
      const actorValue = alertDraft.actor.trim() || adminActor || "unknown-admin";
      const result = await previewAlertChannel.mutateAsync({
        channel: payloadChannel,
        sampleMessage: previewSampleMessage,
        sampleMetadata: metadata,
        actor: actorValue,
      });
      setPreviewState({
        targetKey: draft.key,
        isOpen: true,
        isLoading: false,
        result,
        error: null,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "미리보기 생성 중 문제가 생겼어요.";
      setPreviewState({
        targetKey: draft.key,
        isOpen: true,
        isLoading: false,
        result: undefined,
        error: message,
      });
      toast({
        id: `admin/ops/alert-channel/preview-error-${draft.key}-${Date.now()}`,
        intent: "error",
        title: "미리보기를 불러오지 못했어요",
        message,
      });
    }
  };

  const handleCopyPreviewValue = async (label: string, value: string) => {
    if (!value) {
      toast({
        id: `admin/ops/alert-channel/preview-copy-missing-${Date.now()}`,
        title: `${label} 내용을 찾지 못했어요`,
        message: "미리보기를 먼저 생성해 주세요.",
        intent: "warning",
      });
      return;
    }

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        toast({
          id: `admin/ops/alert-channel/preview-copy-${Date.now()}`,
          title: `${label}를 복사했어요`,
          message: "클립보드로 복사되었습니다.",
          intent: "success",
        });
      } else {
        throw new Error("clipboard_unavailable");
      }
    } catch (error) {
      toast({
        id: `admin/ops/alert-channel/preview-copy-error-${Date.now()}`,
        title: `${label} 복사에 실패했어요`,
        message:
          error instanceof Error && error.message !== "clipboard_unavailable"
            ? error.message
            : "브라우저에서 클립보드를 사용할 수 없어요.",
        intent: "error",
      });
    }
  };

  const handleToggleChannelStatus = async (channelKey: string, enabled: boolean) => {
    try {
      const actorValue = alertDraft.actor.trim() || adminActor || "unknown-admin";
      await updateAlertChannelStatus.mutateAsync({
        key: channelKey,
        enabled,
        actor: actorValue,
        note: alertDraft.note.trim() || null,
      });
      toast({
        id: `admin/ops/alert-channel/status-${channelKey}-${Date.now()}`,
        intent: "success",
        title: enabled ? "채널을 다시 열었어요" : "채널을 잠시 쉬게 했어요",
        message: enabled
          ? "이 채널로 안내가 다시 나갈 준비가 됐어요."
          : "필요할 때 언제든 다시 활성화할 수 있어요.",
      });
      await refetchAlertChannels();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "채널 상태를 바꾸는 중 오류가 발생했어요.";
      toast({
        id: `admin/ops/alert-channel/status-error-${channelKey}-${Date.now()}`,
        intent: "error",
        title: "상태 변경 실패",
        message,
      });
    }
  };

  const handleAlertSubmit = async () => {
    if (alertSuccessTimer.current) {
      clearTimeout(alertSuccessTimer.current);
      alertSuccessTimer.current = null;
    }
    setAlertSaveSuccess(false);
    try {
      const payloadChannels = alertDraft.channels.map((channel, index) => {
        const metadata = parseJsonRecord(
          channel.metadataJson,
          `${channel.label || channel.key || `channel_${index + 1}`} metadata`,
        );
        const targets = parseTargetsInput(channel.targetsText);
        const resolvedKey = channel.key.trim()
          ? slugify(channel.key.trim())
          : generateChannelKey(`${channel.channelType}-${index + 1}`, "channel");
        const resolvedLabel = channel.label.trim() || `알림 채널 ${index + 1}`;
        return {
          key: resolvedKey,
          label: resolvedLabel,
          channelType: channel.channelType,
          enabled: channel.enabled,
          targets,
          metadata,
          template: channel.template.trim() || null,
          messageTemplate: channel.messageTemplate.trim() || null,
          description: channel.description.trim() || null,
        } satisfies AdminOpsAlertChannel;
      });

      await updateAlertChannels.mutateAsync({
        channels: payloadChannels,
        actor: alertDraft.actor.trim() || adminActor || "unknown-admin",
        note: alertDraft.note.trim() || null,
      });

      toast({
        id: "admin/ops/alerts/success",
        title: "알림 채널이 저장됐어요",
        message: "운영 알림 채널이 최신 상태입니다.",
        intent: "success",
      });

      setAlertSaveSuccess(true);
      alertSuccessTimer.current = setTimeout(() => setAlertSaveSuccess(false), 1800);
      setAlertDraft((prev) => ({
        ...prev,
        actor: adminActor ?? prev.actor,
        note: "",
        error: undefined,
      }));
      await refetchAlertChannels();
    } catch (error) {
      const message = error instanceof Error ? error.message : "알림 채널 저장에 실패했어요.";
      toast({
        id: "admin/ops/alerts/error",
        title: "알림 채널 저장 실패",
        message,
        intent: "error",
      });
      setAlertDraft((prev) => ({ ...prev, error: message }));
      setAlertSaveSuccess(false);
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            알림 채널
          </h3>
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            텔레그램, 이메일, 웹훅 채널을 살펴보고 업데이트해요.
          </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => refetchAlertChannels()}
            disabled={isAlertChannelsLoading}
            className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          >
            새로고침
          </button>
          <button
            type="button"
            onClick={handleAddAlertChannel}
            className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-primaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          >
          채널 추가
        </button>
      </div>
    </div>

    <div className="rounded-lg bg-background-cardLight p-3 text-xs text-text-secondaryLight dark:bg-background-cardDark dark:text-text-secondaryDark">
      <label className="flex flex-col gap-1">
        <span className="font-medium text-text-primaryLight dark:text-text-primaryDark">미리보기 메시지 샘플</span>
        <textarea
          value={previewSampleMessage}
          onChange={(event) => setPreviewSampleMessage(event.target.value)}
          rows={2}
          placeholder="우리 고객님께 전하고 싶은 메시지를 적어 주세요."
          className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <p className="mt-1 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
        미리보기 버튼을 누르면 위 문장이 템플릿에 적용돼요. 필요하면 언제든 수정할 수 있어요.
      </p>
    </div>

      {isCreateOpen && (
        <div className="space-y-3 rounded-lg border border-dashed border-primary/40 bg-background-cardLight/60 p-4 text-xs text-text-secondaryLight dark:border-primary/30 dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">새 채널 만들기</h4>
              <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                채널 정보를 입력하고 저장을 누르면 바로 목록에 추가돼요.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsCreateOpen(false);
                setCreateError(null);
              }}
              className="rounded-lg border border-border-light px-2 py-1 text-[11px] font-semibold text-text-secondaryLight hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            >
              닫기
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">채널 이름</span>
              <input
                type="text"
                value={createDraft.label}
                onChange={(event) => handleCreateFieldChange("label", event.target.value)}
                placeholder="예: Slack 알림 채널"
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">채널 타입</span>
              <select
                value={createDraft.channelType}
                onChange={(event) => handleCreateFieldChange("channelType", event.target.value)}
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              >
                {ALERT_SECTION_ORDER.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">발송 대상</span>
              <textarea
                value={createDraft.targetsText}
                onChange={(event) => handleCreateFieldChange("targetsText", event.target.value)}
                rows={2}
                placeholder="콤마 또는 줄바꿈으로 여러 대상을 입력할 수 있어요."
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">메타데이터(JSON)</span>
              <textarea
                value={createDraft.metadataJson}
                onChange={(event) => handleCreateFieldChange("metadataJson", event.target.value)}
                rows={3}
                className="font-mono text-[12px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">템플릿</span>
              <select
                value={createDraft.template}
                onChange={(event) => handleCreateFieldChange("template", event.target.value)}
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              >
                {(ALERT_CHANNEL_TEMPLATE_OPTIONS[createDraft.channelType] ?? [{ value: "default", label: "표준" }]).map(
                  (option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">메시지 템플릿</span>
              <input
                type="text"
                value={createDraft.messageTemplate}
                onChange={(event) => handleCreateFieldChange("messageTemplate", event.target.value)}
                placeholder="{message} 같은 플레이스홀더를 사용할 수 있어요."
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">설명</span>
              <textarea
                value={createDraft.description}
                onChange={(event) => handleCreateFieldChange("description", event.target.value)}
                rows={2}
                placeholder="채널 용도나 비고를 적어 두면 좋아요."
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="text-text-secondaryLight dark:text-text-secondaryDark">변경 메모</span>
              <textarea
                value={createNote}
                onChange={(event) => setCreateNote(event.target.value)}
                rows={2}
                placeholder="어떤 이유로 채널을 만들었는지 남겨 두면 운영에 도움이 돼요."
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
          </div>
          {createError ? <p className="text-[11px] text-support-error">{createError}</p> : null}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCreateChannelSubmit}
              className="inline-flex items-center rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              채널 저장
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreateOpen(false);
                setCreateError(null);
              }}
              className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            >
              취소
            </button>
          </div>
        </div>
      )}

      {isAlertChannelsLoading && !alertDraft.channels.length ? (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">알림 채널을 불러오는 중이에요…</p>
      ) : alertDraft.channels.length ? (
        alertDraft.channels.map((channel, index) => {
          const templateOptions =
            ALERT_CHANNEL_TEMPLATE_OPTIONS[channel.channelType] ?? ALERT_CHANNEL_TEMPLATE_OPTIONS.telegram;
          const original = alertChannelsData?.channels?.find((item) => item.key === channel.key);
          return (
            <div
              key={`alert-channel-${channel.key}-${index}`}
              className="space-y-3 rounded-lg border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  표시 이름
                  <input
                    type="text"
                    value={channel.label}
                    onChange={(event) => handleAlertChannelField(index, "label", event.target.value)}
                    placeholder="예: 텔레그램 운영 채널"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  채널 키
                  <input
                    type="text"
                    value={channel.key}
                    onChange={(event) => handleAlertChannelField(index, "key", event.target.value)}
                    placeholder="예: telegram-primary"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  채널 유형
                  <select
                    value={channel.channelType}
                    onChange={(event) => handleAlertChannelTypeChange(index, event.target.value)}
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  >
                    {ALERT_SECTION_ORDER.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  <span
                    className={clsx(
                      "inline-flex items-center rounded-full px-2 py-0.5 font-semibold",
                      channel.enabled
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200"
                        : "bg-rose-100 text-rose-700 dark:bg-rose-400/20 dark:text-rose-200",
                    )}
                  >
                    {channel.enabled ? "활성" : "비활성"}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleToggleChannelStatus(channel.key, !channel.enabled)}
                    className="inline-flex items-center rounded-lg border border-border-light px-2 py-1 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                  >
                    {channel.enabled ? "일시중지" : "다시 활성화"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePreviewChannel(index)}
                    className="inline-flex items-center rounded-lg border border-border-light px-2 py-1 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                  >
                    미리보기
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveAlertChannel(index)}
                  className="ml-auto inline-flex items-center rounded-lg border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                >
                  삭제
                </button>
              </div>

              <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                기본 대상 (쉼표 또는 줄바꿈으로 구분)
                <textarea
                  value={channel.targetsText}
                  onChange={(event) => handleAlertChannelField(index, "targetsText", event.target.value)}
                  placeholder="예: @finance_ops, @alerts_backup"
                  className="min-h-[100px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
              </label>

              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  템플릿
                  <select
                    value={channel.template}
                    onChange={(event) => handleAlertChannelField(index, "template", event.target.value)}
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  >
                    {templateOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  채널 설명 (선택)
                  <input
                    type="text"
                    value={channel.description}
                    onChange={(event) => handleAlertChannelField(index, "description", event.target.value)}
                    placeholder="예: 주간 공시 요약 전용 채널"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
              </div>

              <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                기본 메시지 템플릿 (선택)
                <textarea
                  value={channel.messageTemplate}
                  onChange={(event) => handleAlertChannelField(index, "messageTemplate", event.target.value)}
                  placeholder="예: [{channel}] {message}"
                  className="min-h-[100px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
              </label>

              <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                Metadata (JSON)
                <textarea
                  value={channel.metadataJson}
                  onChange={(event) => handleAlertChannelField(index, "metadataJson", event.target.value)}
                  className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
              </label>

              <div className="rounded-lg bg-background-base/60 p-3 text-[11px] text-text-secondaryLight dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <span>등록: {formatDateTime(original?.createdAt, { fallback: "기록 없음" })}</span>
                  <span>최근 수정: {formatDateTime(original?.updatedAt, { fallback: "기록 없음" })}</span>
                  <span>비활성화: {formatDateTime(original?.disabledAt, { fallback: "기록 없음" })}</span>
                </div>
                {original?.disabledNote ? (
                  <p className="mt-1 text-text-tertiaryLight dark:text-text-tertiaryDark">
                    비활성 메모: {original.disabledNote}
                  </p>
                ) : null}
              </div>

              {previewState.isOpen && previewState.targetKey === channel.key ? (
                <div className="rounded-lg border border-primary/30 bg-background-base/70 p-3 text-xs text-text-secondaryLight dark:border-primary/40 dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                      미리보기
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setPreviewState({
                          targetKey: null,
                          isOpen: false,
                          isLoading: false,
                          result: undefined,
                          error: null,
                        })
                      }
                      className="rounded-lg border border-border-light px-2 py-1 text-[11px] font-semibold text-text-secondaryLight hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                    >
                      닫기
                    </button>
                  </div>
                  {previewState.isLoading ? (
                    <p className="mt-2 text-text-tertiaryLight dark:text-text-tertiaryDark">
                      따뜻한 메시지를 준비하는 중이에요…
                    </p>
                  ) : previewState.error ? (
                    <p className="mt-2 text-support-error">{previewState.error}</p>
                  ) : previewState.result ? (
                    <div className="mt-2 space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">본문</span>
                        <button
                          type="button"
                          onClick={() => handleCopyPreviewValue("미리보기 본문", previewState.result?.message ?? "")}
                          className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                        >
                          복사
                        </button>
                      </div>
                      <p className="whitespace-pre-line text-text-secondaryLight dark:text-text-secondaryDark">
                        {previewState.result.message}
                      </p>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">렌더링 결과</span>
                        <button
                          type="button"
                          onClick={() => handleCopyPreviewValue("렌더링 결과", previewRenderedJson)}
                          className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                        >
                          복사
                        </button>
                      </div>
                      <pre className="overflow-x-auto rounded-lg bg-background-cardLight/60 p-2 font-mono text-[11px] text-text-secondaryLight dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                        {previewRenderedJson}
                      </pre>
                      {previewState.result.templateUsed ? (
                        <p className="text-text-tertiaryLight dark:text-text-tertiaryDark">
                          사용된 템플릿: {previewState.result.templateUsed}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })
      ) : (
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">등록된 알림 채널이 아직 없어요.</p>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          실행자(Actor)
          <input
            type="text"
            value={alertDraft.actor}
            onChange={(event) => setAlertDraft((prev) => ({ ...prev, actor: event.target.value }))}
            placeholder={adminActor ?? "운영자 이름"}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          변경 메모
          <input
            type="text"
            value={alertDraft.note}
            onChange={(event) => setAlertDraft((prev) => ({ ...prev, note: event.target.value }))}
            placeholder="예: 텔레그램 운영 채널 추가"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      {alertDraft.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {alertDraft.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={handleAlertSubmit}
          disabled={updateAlertChannels.isPending}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition duration-150 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updateAlertChannels.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updateAlertChannels.isPending ? (
            <>
              <AdminButtonSpinner className="border-white/40 border-t-white" />
              <span>저장 중…</span>
            </>
          ) : alertSaveSuccess ? (
            <>
              <AdminSuccessIcon className="text-white" />
              <span>저장 완료!</span>
            </>
          ) : (
            "알림 채널 저장"
          )}
        </button>
      </div>
    </section>
  );
}
