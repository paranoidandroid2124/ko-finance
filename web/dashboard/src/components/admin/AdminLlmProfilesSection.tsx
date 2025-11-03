"use client";

import clsx from "classnames";
import { useEffect, useMemo, useState } from "react";

import { useLlmProfiles, useUpsertLlmProfile } from "@/hooks/useAdminConfig";
import type { ToastInput } from "@/store/toastStore";

type AdminLlmProfilesSectionProps = {
  adminActor?: string | null;
  actorPlaceholder?: string;
  toast: (toast: ToastInput) => string;
};

type ProfileFormState = {
  name: string;
  model: string;
  settingsText: string;
  actor: string;
  note: string;
  error?: string | null;
};

type ProfileSnapshot = {
  name: string;
  model: string;
  settingsText: string;
};

const DEFAULT_SETTINGS_TEXT = "{}";

const prettifyJson = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return DEFAULT_SETTINGS_TEXT;
  }
};

const buildDefaultForm = (actor: string): ProfileFormState => ({
  name: "",
  model: "",
  settingsText: DEFAULT_SETTINGS_TEXT,
  actor,
  note: "",
  error: undefined,
});

const buildDefaultSnapshot = (): ProfileSnapshot => ({
  name: "",
  model: "",
  settingsText: DEFAULT_SETTINGS_TEXT,
});

export function AdminLlmProfilesSection({ adminActor, actorPlaceholder = "", toast }: AdminLlmProfilesSectionProps) {
  const {
    data: profilesData,
    isLoading: isProfilesLoading,
    isError: isProfilesError,
    refetch: refetchProfiles,
  } = useLlmProfiles(true);
  const upsertProfile = useUpsertLlmProfile();

  const profiles = useMemo(() => profilesData?.profiles ?? [], [profilesData]);

  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileFormState>(buildDefaultForm(actorPlaceholder));
  const [profileSnapshot, setProfileSnapshot] = useState<ProfileSnapshot>(buildDefaultSnapshot());

  useEffect(() => {
    if (profiles.length === 0) {
      setSelectedProfile(null);
      setProfileSnapshot(buildDefaultSnapshot());
      setProfileForm(buildDefaultForm(actorPlaceholder));
      return;
    }
    if (!selectedProfile || !profiles.some((profile) => profile.name === selectedProfile)) {
      setSelectedProfile(profiles[0].name);
    }
  }, [profiles, selectedProfile, actorPlaceholder]);

  useEffect(() => {
    if (!selectedProfile) {
      setProfileForm(buildDefaultForm(actorPlaceholder));
      setProfileSnapshot(buildDefaultSnapshot());
      return;
    }
    const current = profiles.find((profile) => profile.name === selectedProfile);
    if (!current) {
      return;
    }
    setProfileForm({
      name: current.name,
      model: current.model ?? "",
      settingsText: prettifyJson(current.settings ?? {}),
      actor: actorPlaceholder,
      note: "",
      error: undefined,
    });
    setProfileSnapshot({
      name: current.name,
      model: current.model ?? "",
      settingsText: prettifyJson(current.settings ?? {}),
    });
  }, [selectedProfile, profiles, actorPlaceholder]);

  const handleProfileFieldChange = (field: keyof ProfileFormState, value: string) => {
    setProfileForm((prev) => ({ ...prev, [field]: value, error: field === "error" ? prev.error : undefined }));
  };

  const handleAddProfile = () => {
    setSelectedProfile(null);
    setProfileForm(buildDefaultForm(actorPlaceholder));
    setProfileSnapshot(buildDefaultSnapshot());
  };

  const handleCopyValue = async (label: string, value: string) => {
    if (!value) {
      toast({
        id: `admin/llm/profile/copy-empty-${Date.now()}`,
        title: `${label}을(를) 복사할 수 없어요`,
        message: "먼저 내용을 입력하거나 프로필을 선택해 주세요.",
        intent: "warning",
      });
      return;
    }

    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("clipboard_unavailable");
      }
      await navigator.clipboard.writeText(value);
      toast({
        id: `admin/llm/profile/copy-${Date.now()}`,
        title: `${label}을(를) 복사했어요`,
        message: "클립보드로 복사되었습니다.",
        intent: "success",
      });
    } catch (error) {
      toast({
        id: `admin/llm/profile/copy-error-${Date.now()}`,
        title: `${label} 복사에 실패했어요`,
        message:
          error instanceof Error && error.message !== "clipboard_unavailable"
            ? error.message
            : "브라우저에서 클립보드를 사용할 수 없어요.",
        intent: "error",
      });
    }
  };

  const handleProfileSubmit = async () => {
    const trimmedName = profileForm.name.trim();
    const trimmedModel = profileForm.model.trim();

    if (!trimmedName) {
      setProfileForm((prev) => ({ ...prev, error: "프로필 이름을 입력해 주세요." }));
      return;
    }
    if (!trimmedModel) {
      setProfileForm((prev) => ({ ...prev, error: "모델 ID를 입력해 주세요." }));
      return;
    }

    let settings: Record<string, unknown> = {};
    try {
      const trimmedSettings = profileForm.settingsText.trim();
      settings = trimmedSettings ? JSON.parse(trimmedSettings) : {};
      if (settings === null || typeof settings !== "object" || Array.isArray(settings)) {
        throw new Error();
      }
    } catch {
      setProfileForm((prev) => ({ ...prev, error: "세부 설정 JSON 형식이 올바르지 않아요." }));
      return;
    }

    try {
      await upsertProfile.mutateAsync({
        name: trimmedName,
        payload: {
          model: trimmedModel,
          settings,
          actor: profileForm.actor.trim() || adminActor || "unknown-admin",
          note: profileForm.note.trim() || null,
        },
      });
      toast({
        id: `admin/llm/profile/${trimmedName}-${Date.now()}`,
        title: "LLM 프로필이 저장됐어요",
        message: `${trimmedName} 프로필이 최신 상태예요.`,
        intent: "success",
      });
      setProfileSnapshot({
        name: trimmedName,
        model: trimmedModel,
        settingsText: JSON.stringify(settings, null, 2),
      });
      setProfileForm({
        name: trimmedName,
        model: trimmedModel,
        settingsText: JSON.stringify(settings, null, 2),
        actor: actorPlaceholder,
        note: "",
        error: undefined,
      });
      setSelectedProfile(trimmedName);
      await refetchProfiles();
    } catch (error) {
      const message = error instanceof Error ? error.message : "프로필 저장에 실패했어요.";
      toast({
        id: `admin/llm/profile/error-${Date.now()}`,
        title: "프로필 저장 실패",
        message,
        intent: "error",
      });
    }
  };

  const trimmedFormModel = profileForm.model.trim();
  const plannedSettingsPretty = useMemo(() => {
    try {
      const trimmed = profileForm.settingsText.trim();
      if (!trimmed) {
        return DEFAULT_SETTINGS_TEXT;
      }
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return profileForm.settingsText;
    }
  }, [profileForm.settingsText]);
  const baselineSettingsPretty = profileSnapshot.settingsText;
  const hasBaseline = Boolean(selectedProfile && profileSnapshot.name === selectedProfile);
  const nameChanged = hasBaseline && profileSnapshot.name !== profileForm.name.trim();
  const modelChanged = hasBaseline ? profileSnapshot.model !== trimmedFormModel : Boolean(trimmedFormModel);
  const settingsChanged = hasBaseline ? baselineSettingsPretty !== plannedSettingsPretty : Boolean(profileForm.settingsText.trim());
  const hasMeaningfulChanges = nameChanged || modelChanged || settingsChanged;
  const changeSummary = hasBaseline
    ? [
        nameChanged
          ? `프로필 이름이 ${profileSnapshot.name} → ${profileForm.name.trim() || "(미입력)"} 로 변경돼요.`
          : "프로필 이름은 그대로 유지돼요.",
        modelChanged
          ? `기본 모델이 ${profileSnapshot.model || "미지정"} → ${trimmedFormModel || "미지정"} 로 변경돼요.`
          : "기본 모델은 그대로 유지돼요.",
        settingsChanged ? "세부 설정 JSON이 업데이트됩니다." : "세부 설정은 변경되지 않아요.",
      ]
    : [
        "새 프로필이 추가되며 기존 프로필은 그대로 유지돼요.",
        "저장 전에 모델과 세부 설정을 한 번 더 확인해 주세요.",
      ];

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          LiteLLM 프로필
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => refetchProfiles()}
            className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
            disabled={isProfilesLoading}
          >
            최신 상태로 다시 불러오기
          </button>
          <button
            type="button"
            onClick={handleAddProfile}
            className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-primaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          >
            새 프로필 추가
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px,1fr]">
        <aside className="rounded-lg border border-border-light bg-background-cardLight p-3 dark:border-border-dark dark:bg-background-cardDark">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">프로필 목록</p>
          <div className="mt-2 space-y-2">
            {isProfilesLoading ? (
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">불러오는 중이에요…</p>
            ) : profiles.length ? (
              profiles.map((profile) => {
                const isActive = profile.name === selectedProfile;
                return (
                  <button
                    key={profile.name}
                    type="button"
                    onClick={() => setSelectedProfile(profile.name)}
                    className={clsx(
                      "w-full rounded-lg border px-3 py-2 text-left text-sm transition",
                      isActive
                        ? "border-primary bg-primary/10 text-primary dark:border-primary.dark dark:bg-primary.dark/20 dark:text-primary.dark"
                        : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
                    )}
                  >
                    <span className="font-semibold">{profile.name}</span>
                    <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">{profile.model}</p>
                  </button>
                );
              })
            ) : (
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                저장된 프로필이 없어요. 새 프로필을 추가해 보세요.
              </p>
            )}
          </div>
        </aside>

        <div className="rounded-xl border border-border-light bg-background-cardLight p-4 dark:border-border-dark dark:bg-background-cardDark">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">프로필 이름</span>
              <input
                type="text"
                value={profileForm.name}
                onChange={(event) => handleProfileFieldChange("name", event.target.value)}
                placeholder="예: default-chat"
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">기본 모델</span>
              <input
                type="text"
                value={profileForm.model}
                onChange={(event) => handleProfileFieldChange("model", event.target.value)}
                placeholder="예: gpt-4o-mini"
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
          </div>

          <label className="mt-4 flex flex-col gap-2 text-sm">
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">세부 설정 (JSON)</span>
            <textarea
              value={profileForm.settingsText}
              onChange={(event) => handleProfileFieldChange("settingsText", event.target.value)}
              className="min-h-[160px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            />
            <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">temperature, top_p, context_window 등의 값을 JSON 형태로 입력해 주세요.</span>
          </label>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              실행자(Actor)
              <input
                type="text"
                value={profileForm.actor}
                onChange={(event) => handleProfileFieldChange("actor", event.target.value)}
                placeholder={actorPlaceholder || "운영자 이름"}
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
              변경 메모
              <input
                type="text"
                value={profileForm.note}
                onChange={(event) => handleProfileFieldChange("note", event.target.value)}
                placeholder="예: Slack 안내 톤 보완"
                className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
              />
            </label>
          </div>

          {profileForm.error ? (
            <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
              {profileForm.error}
            </p>
          ) : null}

          {isProfilesError ? (
            <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
              프로필 정보를 불러올 수 없어요. 새로고침 후 다시 시도해 주세요.
            </p>
          ) : null}

          <div className="mt-6 space-y-3 rounded-lg border border-dashed border-border-light bg-background-cardLight/40 p-4 dark:border-border-dark dark:bg-background-cardDark/40">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">프로필 비교</span>
              {hasBaseline ? (
                <span
                  className={clsx(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    hasMeaningfulChanges
                      ? "bg-primary/10 text-primary dark:bg-primary.dark/20 dark:text-primary.dark"
                      : "bg-border-light text-text-tertiaryLight dark:bg-border-dark dark:text-text-tertiaryDark",
                  )}
                >
                  {hasMeaningfulChanges ? "변경 있음" : "변경 없음"}
                </span>
              ) : null}
            </div>
            <ul className="list-disc space-y-1 pl-5 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {changeSummary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-border-light bg-background-base p-3 dark:border-border-dark dark:bg-background-cardDark">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">현재 저장된 값</span>
                  {hasBaseline ? (
                    <button
                      type="button"
                      onClick={() => handleCopyValue("현재 저장된 설정", baselineSettingsPretty)}
                      className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                    >
                      복사
                    </button>
                  ) : null}
                </div>
                {hasBaseline ? (
                  <>
                    <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">모델: {profileSnapshot.model || "미지정"}</p>
                    <pre className="mt-2 max-h-48 overflow-auto rounded bg-background-cardLight/60 p-2 font-mono text-[11px] text-text-secondaryLight dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                      {baselineSettingsPretty}
                    </pre>
                  </>
                ) : (
                  <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">저장된 기준이 없어요. 새 프로필을 저장하면 바로 생성돼요.</p>
                )}
              </div>
              <div className="rounded-lg border border-primary/30 bg-background-base p-3 dark:border-primary.dark/40 dark:bg-background-cardDark">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-text-tertiaryLight dark:text-text-tertiaryDark">저장 예정 값</span>
                  <button
                    type="button"
                    onClick={() => handleCopyValue("저장 예정 설정", plannedSettingsPretty)}
                    className="inline-flex items-center rounded border border-border-light px-2 py-0.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                  >
                    복사
                  </button>
                </div>
                <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">모델: {trimmedFormModel || "미지정"}</p>
                <pre className="mt-2 max-h-48 overflow-auto rounded bg-background-cardLight/60 p-2 font-mono text-[11px] text-text-secondaryLight dark:bg-background-cardDark/60 dark:text-text-secondaryDark">
                  {plannedSettingsPretty}
                </pre>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              onClick={handleProfileSubmit}
              disabled={upsertProfile.isPending}
              className={clsx(
                "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                upsertProfile.isPending && "cursor-not-allowed opacity-60",
              )}
            >
              {upsertProfile.isPending ? "저장 중…" : "프로필 저장"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

