"use client";

import clsx from "classnames";
import { useEffect, useMemo, useState } from "react";

import { useUiUxSettings, useUpdateUiUxSettings } from "@/hooks/useAdminConfig";
import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { useToastStore } from "@/store/toastStore";

const COLOR_REGEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const DATE_RANGE_OPTIONS = ["1D", "1W", "1M", "3M", "6M", "1Y"];
const LANDING_VIEW_OPTIONS = [
  { value: "overview", label: "개요" },
  { value: "alerts", label: "알림" },
  { value: "evidence", label: "근거 패널" },
  { value: "operations", label: "운영 설정" },
];

type UiUxFormState = {
  theme: {
    primaryColor: string;
    accentColor: string;
  };
  defaults: {
    dateRange: string;
    landingView: string;
  };
  copy: {
    welcomeHeadline: string;
    welcomeSubcopy: string;
    quickCta: string;
  };
  banner: {
    enabled: boolean;
    message: string;
    linkLabel: string;
    linkUrl: string;
  };
  actor: string;
  note: string;
  error?: string | null;
};

const buildInitialFormState = (): UiUxFormState => ({
  theme: {
    primaryColor: "#1F6FEB",
    accentColor: "#22C55E",
  },
  defaults: {
    dateRange: "1M",
    landingView: "overview",
  },
  copy: {
    welcomeHeadline: "",
    welcomeSubcopy: "",
    quickCta: "",
  },
  banner: {
    enabled: false,
    message: "",
    linkLabel: "",
    linkUrl: "",
  },
  actor: "",
  note: "",
  error: undefined,
});

export function AdminUiUxPanel() {
  const toast = useToastStore((state) => state.show);
  const {
    data: adminSession,
    isLoading: isAdminSessionLoading,
    isUnauthorized,
    refetch: refetchAdminSession,
  } = useAdminSession();

  const isSessionReady = Boolean(adminSession) && !isUnauthorized;

  const {
    data: uiSettingsResponse,
    isLoading: isSettingsLoading,
    isError: isSettingsError,
    refetch: refetchUiSettings,
  } = useUiUxSettings(isSessionReady);
  const updateUiSettings = useUpdateUiUxSettings();

  const [formState, setFormState] = useState<UiUxFormState>(buildInitialFormState);

  useEffect(() => {
    if (!uiSettingsResponse?.settings) {
      return;
    }
    setFormState((prev) => ({
      ...prev,
      theme: {
        primaryColor: uiSettingsResponse.settings.theme.primaryColor ?? prev.theme.primaryColor,
        accentColor: uiSettingsResponse.settings.theme.accentColor ?? prev.theme.accentColor,
      },
      defaults: {
        dateRange: uiSettingsResponse.settings.defaults.dateRange ?? prev.defaults.dateRange,
        landingView: uiSettingsResponse.settings.defaults.landingView ?? prev.defaults.landingView,
      },
      copy: {
        welcomeHeadline: uiSettingsResponse.settings.copy.welcomeHeadline ?? "",
        welcomeSubcopy: uiSettingsResponse.settings.copy.welcomeSubcopy ?? "",
        quickCta: uiSettingsResponse.settings.copy.quickCta ?? "",
      },
      banner: {
        enabled: Boolean(uiSettingsResponse.settings.banner.enabled),
        message: uiSettingsResponse.settings.banner.message ?? "",
        linkLabel: uiSettingsResponse.settings.banner.linkLabel ?? "",
        linkUrl: uiSettingsResponse.settings.banner.linkUrl ?? "",
      },
      actor: adminSession?.actor ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [uiSettingsResponse, adminSession?.actor]);

  const lastUpdated = useMemo(() => {
    const timestamp = uiSettingsResponse?.updatedAt;
    if (!timestamp) {
      return null;
    }
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString("ko-KR");
  }, [uiSettingsResponse?.updatedAt]);

  const auditDownloadUrl = `${resolveApiBase()}/api/v1/admin/ui/audit/logs`;
  const actorPlaceholder = adminSession?.actor ?? "";

  const handleThemeChange = (field: "primaryColor" | "accentColor", value: string) => {
    setFormState((prev) => ({
      ...prev,
      theme: { ...prev.theme, [field]: value },
      error: undefined,
    }));
  };

  const handleDefaultChange = (field: "dateRange" | "landingView", value: string) => {
    setFormState((prev) => ({
      ...prev,
      defaults: { ...prev.defaults, [field]: value },
      error: undefined,
    }));
  };

  const handleCopyChange = (field: keyof UiUxFormState["copy"], value: string) => {
    setFormState((prev) => ({
      ...prev,
      copy: { ...prev.copy, [field]: value },
      error: undefined,
    }));
  };

  const handleBannerChange = (field: keyof UiUxFormState["banner"], value: string | boolean) => {
    setFormState((prev) => ({
      ...prev,
      banner: { ...prev.banner, [field]: value },
      error: undefined,
    }));
  };

  const validateForm = () => {
    if (!COLOR_REGEX.test(formState.theme.primaryColor.trim())) {
      return "기본 색상은 #으로 시작하는 3자리 또는 6자리 HEX 값이어야 해요.";
    }
    if (!COLOR_REGEX.test(formState.theme.accentColor.trim())) {
      return "강조 색상은 #으로 시작하는 3자리 또는 6자리 HEX 값이어야 해요.";
    }
    if (!DATE_RANGE_OPTIONS.includes(formState.defaults.dateRange)) {
      return "기본 기간은 제공된 옵션 중 하나를 선택해 주세요.";
    }
    if (!LANDING_VIEW_OPTIONS.some((option) => option.value === formState.defaults.landingView)) {
      return "첫 화면으로 이동할 영역을 선택해 주세요.";
    }
    if (formState.banner.enabled && !formState.banner.message.trim()) {
      return "배너를 켜두려면 안내 문구가 필요해요.";
    }
    if (formState.banner.linkUrl && formState.banner.linkUrl.trim()) {
      const trimmed = formState.banner.linkUrl.trim();
      if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
        return "배너 링크는 http:// 또는 https:// 로 시작해야 해요.";
      }
    }
    return null;
  };

  const handleSubmit = async () => {
    const validationMessage = validateForm();
    if (validationMessage) {
      setFormState((prev) => ({ ...prev, error: validationMessage }));
      return;
    }

    try {
      await updateUiSettings.mutateAsync({
        settings: {
          theme: {
            primaryColor: formState.theme.primaryColor.trim(),
            accentColor: formState.theme.accentColor.trim(),
          },
          defaults: {
            dateRange: formState.defaults.dateRange,
            landingView: formState.defaults.landingView,
          },
          copy: {
            welcomeHeadline: formState.copy.welcomeHeadline.trim(),
            welcomeSubcopy: formState.copy.welcomeSubcopy.trim(),
            quickCta: formState.copy.quickCta.trim(),
          },
          banner: {
            enabled: formState.banner.enabled,
            message: formState.banner.message.trim(),
            linkLabel: formState.banner.linkLabel.trim(),
            linkUrl: formState.banner.linkUrl.trim(),
          },
        },
        actor: formState.actor.trim() || actorPlaceholder || "unknown-admin",
        note: formState.note.trim() || null,
      });
      toast({
        id: `admin/ui/settings/${Date.now()}`,
        title: "UI·UX 설정이 저장됐어요",
        message: "대시보드 사용자 경험이 최신 상태예요.",
        intent: "success",
      });
      setFormState((prev) => ({ ...prev, note: "", error: undefined }));
      await refetchUiSettings();
    } catch (error) {
      const message = error instanceof Error ? error.message : "UI·UX 설정 저장에 실패했어요.";
      toast({
        id: `admin/ui/settings/error-${Date.now()}`,
        title: "설정 저장 실패",
        message,
        intent: "error",
      });
    }
  };

  if (isAdminSessionLoading) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">관리자 세션을 확인하는 중이에요…</p>
      </section>
    );
  }

  if (isUnauthorized) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          UI·UX 설정을 보려면 관리자 토큰 로그인이 필요해요.
        </p>
        <button
          type="button"
          onClick={() => refetchAdminSession()}
          className="mt-4 inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40"
        >
          다시 시도
        </button>
      </section>
    );
  }

  if (!adminSession) {
    return null;
  }

  if (isSettingsLoading && !uiSettingsResponse) {
    return (
      <section className="rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">UI·UX 설정을 불러오는 중이에요…</p>
      </section>
    );
  }

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-1 border-b border-border-light pb-3 dark:border-border-dark">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">UI & UX 기본값</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          대시보드의 색상, 첫 화면, 환영 문구를 다듬어 연구원들에게 따뜻한 경험을 전해 주세요.
        </p>
        <div className="flex flex-wrap items-center gap-4 text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
          <span>최근 수정: {lastUpdated ?? "기록 없음"}</span>
          <span>작성자: {uiSettingsResponse?.updatedBy ?? "—"}</span>
          <a
            href={auditDownloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-primary hover:underline dark:text-primary.dark"
          >
            감사 로그 다운로드 (ui_audit.jsonl)
          </a>
        </div>
      </header>

      {isSettingsError ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          UI·UX 설정을 불러오지 못했어요. 새로고침 후 다시 시도해 주세요.
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          기본 색상
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={formState.theme.primaryColor}
              onChange={(event) => handleThemeChange("primaryColor", event.target.value)}
              placeholder="#1F6FEB"
              className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span
              aria-hidden="true"
              className="h-8 w-8 rounded-full border border-border-light shadow-inner dark:border-border-dark"
              style={{ backgroundColor: formState.theme.primaryColor || "#1F6FEB" }}
            />
          </div>
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          강조 색상
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={formState.theme.accentColor}
              onChange={(event) => handleThemeChange("accentColor", event.target.value)}
              placeholder="#22C55E"
              className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span
              aria-hidden="true"
              className="h-8 w-8 rounded-full border border-border-light shadow-inner dark:border-border-dark"
              style={{ backgroundColor: formState.theme.accentColor || "#22C55E" }}
            />
          </div>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          기본 기간
          <select
            value={formState.defaults.dateRange}
            onChange={(event) => handleDefaultChange("dateRange", event.target.value)}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          >
            {DATE_RANGE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          첫 화면
          <select
            value={formState.defaults.landingView}
            onChange={(event) => handleDefaultChange("landingView", event.target.value)}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          >
            {LANDING_VIEW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          환영 문구
        </h3>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          제목
          <input
            type="text"
            value={formState.copy.welcomeHeadline}
            onChange={(event) => handleCopyChange("welcomeHeadline", event.target.value)}
            placeholder="같이 차분히 데이터를 살펴볼 준비가 됐어요."
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          보조 설명
          <textarea
            value={formState.copy.welcomeSubcopy}
            onChange={(event) => handleCopyChange("welcomeSubcopy", event.target.value)}
            placeholder="근거와 데이터를 이어 안전한 금융 의사결정을 돕고 있어요."
            className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          빠른 실행 버튼 문구
          <input
            type="text"
            value={formState.copy.quickCta}
            onChange={(event) => handleCopyChange("quickCta", event.target.value)}
            placeholder="새 근거 추가하기"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      <div className="space-y-3 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            알림 배너
          </h3>
          <label className="inline-flex items-center gap-2 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            <input
              type="checkbox"
              checked={formState.banner.enabled}
              onChange={(event) => handleBannerChange("enabled", event.target.checked)}
              className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
            />
            배너 사용
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          안내 문구
          <textarea
            value={formState.banner.message}
            onChange={(event) => handleBannerChange("message", event.target.value)}
            disabled={!formState.banner.enabled}
            placeholder="예: 신규 기능 실험이 곧 시작돼요. 참여하고 싶다면 슬랙으로 알려 주세요!"
            className={clsx(
              "min-h-[100px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark",
              !formState.banner.enabled && "cursor-not-allowed opacity-70",
            )}
          />
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            링크 라벨 (선택)
            <input
              type="text"
              value={formState.banner.linkLabel}
              onChange={(event) => handleBannerChange("linkLabel", event.target.value)}
              disabled={!formState.banner.enabled}
              placeholder="예: 일정 확인하기"
              className={clsx(
                "rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark",
                !formState.banner.enabled && "cursor-not-allowed opacity-70",
              )}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            링크 URL (선택)
            <input
              type="url"
              value={formState.banner.linkUrl}
              onChange={(event) => handleBannerChange("linkUrl", event.target.value)}
              disabled={!formState.banner.enabled}
              placeholder="https://kfinance.ai"
              className={clsx(
                "rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark",
                !formState.banner.enabled && "cursor-not-allowed opacity-70",
              )}
            />
          </label>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          실행자(Actor)
          <input
            type="text"
            value={formState.actor}
            onChange={(event) => setFormState((prev) => ({ ...prev, actor: event.target.value, error: undefined }))}
            placeholder={actorPlaceholder || "운영자 이름"}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          변경 메모
          <input
            type="text"
            value={formState.note}
            onChange={(event) => setFormState((prev) => ({ ...prev, note: event.target.value, error: undefined }))}
            placeholder="예: 실험 배너 공지 추가"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      {formState.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {formState.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => refetchUiSettings()}
          className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isSettingsLoading}
        >
          최신 상태 불러오기
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={updateUiSettings.isPending}
          className={clsx(
            "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updateUiSettings.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updateUiSettings.isPending ? "저장 중…" : "설정 저장"}
        </button>
      </div>
    </section>
  );
}

