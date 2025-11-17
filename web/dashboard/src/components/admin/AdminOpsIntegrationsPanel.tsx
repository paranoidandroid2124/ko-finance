"use client";

import { useEffect, useRef, useState } from "react";

import clsx from "classnames";

import {
  AdminButtonSpinner,
  AdminSuccessIcon,
  formatJsonValue,
  parseJsonRecord,
} from "@/components/admin/adminFormUtils";
import { useOpsApiKeys, useUpdateOpsApiKeys, useRotateLangfuseKeys } from "@/hooks/useAdminConfig";
import type {
  AdminOpsApiKey,
  AdminOpsApiKeyRotation,
  AdminOpsLangfuseConfig,
  AdminOpsLangfuseEnvironment,
} from "@/lib/adminApi";
import { formatDateTime } from "@/lib/date";
import type { ToastInput } from "@/store/toastStore";

type ExternalApiDraft = {
  name: string;
  maskedKey: string;
  enabled: boolean;
  metadataJson: string;
  expiresAt: string;
  warningDays: string;
  lastRotatedAt?: string | null;
  rotationHistory: AdminOpsApiKeyRotation[];
};

type LangfuseDraft = {
  enabled: boolean;
  environment: string;
  host: string;
  publicKey: string;
  secretKey: string;
  maskedPublicKey?: string | null;
  maskedSecretKey?: string | null;
  expiresAt: string;
  warningDays: string;
  lastRotatedAt?: string | null;
  rotationHistory: AdminOpsApiKeyRotation[];
};

const extractLangfuseSnapshot = (config?: AdminOpsLangfuseConfig | null) => {
  const environments = Array.isArray(config?.environments) ? config!.environments : [];
  const defaultEnvironment =
    (typeof config?.defaultEnvironment === "string" && config.defaultEnvironment.trim()) ||
    environments[0]?.name ||
    "production";
  const selectedEnv =
    environments.find((env) => env.name === defaultEnvironment) ?? (environments[0] as AdminOpsLangfuseEnvironment | null) ?? null;
  return { defaultEnvironment, environments, selectedEnv };
};

const maskSecret = (value: unknown): string => {
  if (typeof value !== "string") {
    return "";
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.length <= 4) {
    return "*".repeat(trimmed.length);
  }
  const visible = trimmed.slice(-4);
  return `${"*".repeat(trimmed.length - 4)}${visible}`;
};

  const normalizeMaskedValue = (value: unknown): string => {
    if (typeof value !== "string") {
      return "";
    }
    const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return trimmed.includes("*") ? trimmed : maskSecret(trimmed);
};

  const formatDateInputValue = (value?: string | null): string => {
    if (!value) {
      return "";
    }
    const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString().slice(0, 10);
};

const toIsoStringOrNull = (value: string): string | null => {
  if (!value) {
    return null;
  }
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toISOString();
};

interface AdminOpsIntegrationsPanelProps {
  adminActor?: string | null;
  toast: (toast: ToastInput) => string;
}

export function AdminOpsIntegrationsPanel({ adminActor, toast }: AdminOpsIntegrationsPanelProps) {
  const { data: apiKeysData, isLoading: isApiKeysLoading, refetch: refetchApiKeys } = useOpsApiKeys(true);
  const updateApiKeys = useUpdateOpsApiKeys();
  const rotateLangfuse = useRotateLangfuseKeys();

  const [apiDraft, setApiDraft] = useState<{
    langfuse: LangfuseDraft;
    externals: ExternalApiDraft[];
    actor: string;
    note: string;
    error?: string | null;
  }>({
    langfuse: {
      enabled: false,
      environment: "production",
      host: "",
      publicKey: "",
      secretKey: "",
      maskedPublicKey: "",
      maskedSecretKey: "",
      expiresAt: "",
      warningDays: "",
      lastRotatedAt: "",
      rotationHistory: [],
    },
    externals: [],
    actor: "",
    note: "",
  });
  const [apiSaveSuccess, setApiSaveSuccess] = useState(false);
  const apiSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!apiKeysData?.secrets) {
      return;
    }
    const langfuseSnapshot = extractLangfuseSnapshot(apiKeysData.secrets.langfuse);
    const selectedLangfuseEnv = langfuseSnapshot.selectedEnv ?? null;
    const maskedPublicKey = normalizeMaskedValue(
      selectedLangfuseEnv?.maskedPublicKey ?? selectedLangfuseEnv?.publicKey ?? undefined,
    );
    const maskedSecretKey = normalizeMaskedValue(
      selectedLangfuseEnv?.maskedSecretKey ??
        selectedLangfuseEnv?.secretKey ??
        (selectedLangfuseEnv as unknown as { apiKey?: string })?.apiKey ??
        undefined,
    );
    setApiDraft((prev) => ({
      ...prev,
      langfuse: {
        enabled: Boolean(selectedLangfuseEnv?.enabled ?? true),
        environment: langfuseSnapshot.defaultEnvironment,
        host: String(selectedLangfuseEnv?.host ?? ""),
        publicKey: "",
        secretKey: "",
        maskedPublicKey,
        maskedSecretKey,
        expiresAt: formatDateInputValue(selectedLangfuseEnv?.expiresAt ?? null),
        warningDays:
          selectedLangfuseEnv?.warningThresholdDays !== undefined &&
          selectedLangfuseEnv?.warningThresholdDays !== null
            ? String(selectedLangfuseEnv.warningThresholdDays)
            : "",
        lastRotatedAt: selectedLangfuseEnv?.lastRotatedAt ?? "",
        rotationHistory: Array.isArray(selectedLangfuseEnv?.rotationHistory)
          ? selectedLangfuseEnv.rotationHistory
          : [],
      },
      externals:
        apiKeysData.secrets.externalApis?.map((item) => ({
          name: item.name,
          maskedKey: item.maskedKey ?? "",
          enabled: item.enabled,
          metadataJson: formatJsonValue(item.metadata, "{}"),
          expiresAt: formatDateInputValue(item.expiresAt ?? null),
          warningDays:
            item.warningThresholdDays !== undefined && item.warningThresholdDays !== null
              ? String(item.warningThresholdDays)
              : "",
          lastRotatedAt: item.lastRotatedAt ?? "",
          rotationHistory: Array.isArray(item.rotationHistory) ? item.rotationHistory : [],
        })) ?? [],
      actor: adminActor ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [apiKeysData, adminActor]);

  useEffect(() => {
    return () => {
      if (apiSuccessTimer.current) {
        clearTimeout(apiSuccessTimer.current);
      }
    };
  }, []);

  const handleAddExternalApi = () => {
    setApiDraft((prev) => ({
      ...prev,
      externals: [...prev.externals, { name: "", maskedKey: "", enabled: true, metadataJson: "{}", expiresAt: "", warningDays: "", lastRotatedAt: "", rotationHistory: [] }],
    }));
  };

  const handleExternalChange = (index: number, field: keyof ExternalApiDraft, value: string | boolean) => {
    setApiDraft((prev) => {
      const next = [...prev.externals];
      const current = { ...next[index] };
      if (!current) {
        return prev;
      }

      switch (field) {
        case "enabled": {
          current.enabled = Boolean(value);
          break;
        }
        case "name":
        case "maskedKey":
        case "metadataJson":
        case "expiresAt":
        case "warningDays": {
          current[field] = String(value);
          break;
        }
        case "lastRotatedAt": {
          current.lastRotatedAt = String(value);
          break;
        }
        default:
          // rotationHistory는 UI에서 수정되지 않으므로 그대로 둡니다.
          break;
      }

      next[index] = current;
      return { ...prev, externals: next };
    });
  };

  const handleRemoveExternal = (index: number) => {
    setApiDraft((prev) => ({
      ...prev,
      externals: prev.externals.filter((_, idx) => idx !== index),
    }));
  };

  const handleLangfuseRotate = async () => {
    const actorValue = apiDraft.actor.trim() || adminActor || "unknown-admin";
    try {
      const response = await rotateLangfuse.mutateAsync({ actor: actorValue, note: apiDraft.note || null });
      const snapshot = extractLangfuseSnapshot(response.secrets?.langfuse);
      const selectedEnv = snapshot.selectedEnv;
      const nextMaskedPublicKey = normalizeMaskedValue(
        selectedEnv?.maskedPublicKey ?? selectedEnv?.publicKey ?? apiDraft.langfuse.maskedPublicKey ?? undefined,
      );
      const nextMaskedSecretKey = normalizeMaskedValue(
        selectedEnv?.maskedSecretKey ?? selectedEnv?.secretKey ?? apiDraft.langfuse.maskedSecretKey ?? undefined,
      );

      setApiDraft((prev) => ({
        ...prev,
        langfuse: {
          ...prev.langfuse,
          enabled: Boolean(selectedEnv?.enabled ?? prev.langfuse.enabled),
          environment: snapshot.defaultEnvironment || prev.langfuse.environment || "production",
          host: String(selectedEnv?.host ?? prev.langfuse.host ?? ""),
          publicKey: "",
          secretKey: "",
          maskedPublicKey: nextMaskedPublicKey,
          maskedSecretKey: nextMaskedSecretKey,
          expiresAt: formatDateInputValue(selectedEnv?.expiresAt ?? prev.langfuse.expiresAt ?? null),
          warningDays:
            selectedEnv?.warningThresholdDays !== undefined && selectedEnv?.warningThresholdDays !== null
              ? String(selectedEnv.warningThresholdDays)
              : prev.langfuse.warningDays,
          lastRotatedAt: selectedEnv?.lastRotatedAt ?? prev.langfuse.lastRotatedAt ?? "",
          rotationHistory: Array.isArray(selectedEnv?.rotationHistory)
            ? selectedEnv.rotationHistory
            : prev.langfuse.rotationHistory,
        },
        actor: actorValue,
      }));
      toast({
        id: `admin/langfuse/rotate/${Date.now()}`,
        intent: "success",
        title: "Langfuse 키를 새로 발급했어요",
        message: "새 토큰을 환경 변수에 반영해 주세요.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "토큰 재발급에 실패했어요.";
      toast({
        id: `admin/langfuse/rotate/error-${Date.now()}`,
        intent: "error",
        title: "재발급 실패",
        message,
      });
    }
  };

  const handleApiSubmit = async () => {
    if (apiSuccessTimer.current) {
      clearTimeout(apiSuccessTimer.current);
      apiSuccessTimer.current = null;
    }
    setApiSaveSuccess(false);

    const externalsPayload: AdminOpsApiKey[] = [];
    for (const draft of apiDraft.externals) {
      try {
        const metadata = parseJsonRecord(draft.metadataJson, `${draft.name || "외부 API"} metadata`);
        const expiresAtIso = draft.expiresAt.trim() ? toIsoStringOrNull(draft.expiresAt.trim()) : null;
        if (draft.expiresAt.trim() && !expiresAtIso) {
          setApiDraft((prev) => ({ ...prev, error: "만료 날짜 형식을 다시 확인해 주세요." }));
          return;
        }
        let warningThreshold: number | null = null;
        if (draft.warningDays.trim()) {
          const parsed = Number(draft.warningDays.trim());
          if (!Number.isFinite(parsed)) {
            setApiDraft((prev) => ({ ...prev, error: "경고 일수는 숫자로 입력해 주세요." }));
            return;
          }
          warningThreshold = parsed;
        }
        externalsPayload.push({
          name: draft.name.trim(),
          maskedKey: draft.maskedKey.trim() || null,
          enabled: draft.enabled,
          metadata,
          expiresAt: expiresAtIso,
          warningThresholdDays: warningThreshold,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "외부 API metadata를 확인해 주세요.";
        setApiDraft((prev) => ({ ...prev, error: message }));
        return;
      }
    }

    try {
      const currentLangfuse = apiKeysData?.secrets.langfuse;
      const { environments: existingEnvironments, defaultEnvironment: existingDefaultEnv } =
        extractLangfuseSnapshot(currentLangfuse);
      const desiredEnvName =
        apiDraft.langfuse.environment.trim() || existingDefaultEnv || existingEnvironments[0]?.name || "production";
      const trimmedEnvName = desiredEnvName || "production";
      const existingEnv =
        existingEnvironments.find((env) => env.name === trimmedEnvName) ??
        (existingEnvironments.length ? existingEnvironments[0] : undefined);

      const langfuseExpires = apiDraft.langfuse.expiresAt.trim()
        ? toIsoStringOrNull(apiDraft.langfuse.expiresAt.trim())
        : null;
      if (apiDraft.langfuse.expiresAt.trim() && !langfuseExpires) {
        setApiDraft((prev) => ({ ...prev, error: "Langfuse 만료 날짜 형식을 확인해 주세요." }));
        return;
      }
      if (langfuseExpires !== null) {
        // handled below when constructing environment payload
      }
      let langfuseWarning: number | null = null;
      if (apiDraft.langfuse.warningDays.trim()) {
        const parsed = Number(apiDraft.langfuse.warningDays.trim());
        if (!Number.isFinite(parsed)) {
          setApiDraft((prev) => ({ ...prev, error: "Langfuse 경고 일수는 숫자로 입력해 주세요." }));
          return;
        }
        langfuseWarning = parsed;
      }

      const updatedEnv: AdminOpsLangfuseEnvironment = {
        name: trimmedEnvName,
        enabled: apiDraft.langfuse.enabled,
        rotationHistory: Array.isArray(existingEnv?.rotationHistory) ? existingEnv!.rotationHistory : [],
      };

      const hostValue = apiDraft.langfuse.host.trim() || existingEnv?.host || "";
      if (hostValue) {
        updatedEnv.host = hostValue;
      }

      const publicKeyValue = apiDraft.langfuse.publicKey.trim();
      if (publicKeyValue) {
        updatedEnv.publicKey = publicKeyValue;
      }

      const secretKeyValue = apiDraft.langfuse.secretKey.trim();
      if (secretKeyValue) {
        updatedEnv.secretKey = secretKeyValue;
      }

      const expiresValue = langfuseExpires ?? existingEnv?.expiresAt ?? null;
      if (expiresValue) {
        updatedEnv.expiresAt = expiresValue;
      }

      if (langfuseWarning !== null) {
        updatedEnv.warningThresholdDays = langfuseWarning;
      } else if (existingEnv?.warningThresholdDays !== undefined) {
        updatedEnv.warningThresholdDays = existingEnv.warningThresholdDays;
      }

      const maskedPublicKeyValue =
        apiDraft.langfuse.maskedPublicKey ?? existingEnv?.maskedPublicKey ?? undefined;
      if (maskedPublicKeyValue) {
        updatedEnv.maskedPublicKey = maskedPublicKeyValue;
      }

      const maskedSecretKeyValue =
        apiDraft.langfuse.maskedSecretKey ?? existingEnv?.maskedSecretKey ?? undefined;
      if (maskedSecretKeyValue) {
        updatedEnv.maskedSecretKey = maskedSecretKeyValue;
      }

      const lastRotatedValue = apiDraft.langfuse.lastRotatedAt || existingEnv?.lastRotatedAt || undefined;
      if (lastRotatedValue) {
        updatedEnv.lastRotatedAt = lastRotatedValue;
      }

      if (existingEnv?.note) {
        updatedEnv.note = existingEnv.note;
      }

      const updatedEnvironments: AdminOpsLangfuseEnvironment[] = existingEnvironments
        .filter((env) => env.name !== trimmedEnvName)
        .map((env) => ({ ...env }));
      updatedEnvironments.push(updatedEnv);

      const langfusePayload: AdminOpsLangfuseConfig = {
        defaultEnvironment: trimmedEnvName,
        environments: updatedEnvironments,
      };

      await updateApiKeys.mutateAsync({
        langfuse: langfusePayload,
        externalApis: externalsPayload,
        actor: apiDraft.actor.trim() || adminActor || "unknown-admin",
        note: apiDraft.note.trim() || null,
      });
      toast({
        id: "admin/ops/api/success",
        title: "운영 API 키가 저장됐어요",
        message: "Langfuse 및 외부 API 설정이 최신 상태입니다.",
        intent: "success",
      });
      setApiSaveSuccess(true);
      apiSuccessTimer.current = setTimeout(() => setApiSaveSuccess(false), 1800);
      setApiDraft((prev) => ({
        ...prev,
        langfuse: {
          ...prev.langfuse,
          publicKey: "",
          secretKey: "",
        },
        error: undefined,
        note: "",
      }));
      await refetchApiKeys();
    } catch (error) {
      const message = error instanceof Error ? error.message : "API 키 저장에 실패했어요.";
      toast({
        id: "admin/ops/api/error",
        title: "운영 API 저장 실패",
        message,
        intent: "error",
      });
      setApiSaveSuccess(false);
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
          운영 & 접근 제어
        </h3>
        <button
          type="button"
          onClick={() => refetchApiKeys()}
          className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition duration-150 hover:bg-border-light/30 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isApiKeysLoading}
        >
          새로고침
        </button>
      </div>

      <div className="rounded-lg border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark">
        <div className="flex items-center justify-between gap-3">
          <h4 className="font-semibold">Langfuse</h4>
          <span
            className={clsx(
              "rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
              apiDraft.langfuse.enabled
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200"
                : "bg-border-light text-text-secondaryLight dark:bg-border-dark/50 dark:text-text-secondaryDark",
            )}
          >
            {apiDraft.langfuse.enabled ? "연결됨" : "비활성"}
          </span>
        </div>
        <label className="mt-2 inline-flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <input
            type="checkbox"
            checked={apiDraft.langfuse.enabled}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, enabled: event.target.checked } }))
            }
            className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
          />
          활성화
        </label>
        <p className="mt-2 text-[11px] text-text-tertiaryLight dark:text-text-ter티aryDark">
          저장된 Public Key:{" "}
          <span className="font-mono text-text-secondaryLight dark:text-text-secondaryDark">
            {apiDraft.langfuse.maskedPublicKey || "없음"}
          </span>
        </p>
        <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
          저장된 Secret Key:{" "}
          <span className="font-mono text-text-secondaryLight dark:text-text-secondaryDark">
            {apiDraft.langfuse.maskedSecretKey || "없음"}
          </span>
        </p>
        <p className="mt-1 text-[11px] text-text-ter티aryLight dark:text-text-ter티aryDark">
          새 키를 입력하지 않으면 기존 키가 유지됩니다.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleLangfuseRotate}
            disabled={rotateLangfuse.isPending}
            className={clsx(
              "inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-[11px] font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark",
              rotateLangfuse.isPending && "cursor-not-allowed opacity-60",
            )}
          >
            {rotateLangfuse.isPending ? "재발급 중..." : "토큰 재발급"}
          </button>
          <span className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">토큰을 재발급하면 기존 값은 즉시 교체돼요.</span>
        </div>
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          Environment
          <input
            type="text"
            value={apiDraft.langfuse.environment}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, environment: event.target.value } }))
            }
            placeholder="예: production"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          Host (선택)
          <input
            type="text"
            value={apiDraft.langfuse.host}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, host: event.target.value } }))
            }
            placeholder="https://cloud.langfuse.com"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          만료 예정일(선택)
          <input
            type="date"
            value={apiDraft.langfuse.expiresAt}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, expiresAt: event.target.value } }))
            }
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          만료 경고 일수(선택)
          <input
            type="number"
            min={0}
            value={apiDraft.langfuse.warningDays}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, warningDays: event.target.value } }))
            }
            placeholder="예: 7"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <p className="mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
          최근 회전 시각: {formatDateTime(apiDraft.langfuse.lastRotatedAt, { fallback: "기록 없음" })}
        </p>
        {apiDraft.langfuse.rotationHistory.length > 0 ? (
          <div className="mt-2 space-y-1 rounded-lg bg-background-base/40 p-2 text-[11px] text-text-secondaryLight dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
            <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">회전 이력</span>
            <ul className="space-y-1">
              {apiDraft.langfuse.rotationHistory.slice(0, 5).map((entry, idx) => (
                <li key={`${entry.rotatedAt}-${idx}`} className="flex flex-wrap items-center gap-2">
                  <span>{formatDateTime(entry.rotatedAt, { fallback: "기록 없음" })}</span>
                  <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">by {entry.actor}</span>
                  {entry.note ? (
                    <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">({entry.note})</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          새 Public Key
          <input
            type="text"
            value={apiDraft.langfuse.publicKey}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, publicKey: event.target.value } }))
            }
            placeholder="lf_pk_..."
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          새 Secret Key
          <input
            type="password"
            value={apiDraft.langfuse.secretKey}
            onChange={(event) =>
              setApiDraft((prev) => ({ ...prev, langfuse: { ...prev.langfuse, secretKey: event.target.value } }))
            }
            placeholder="lf_sk_..."
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">외부 API</h4>
          <button
            type="button"
            onClick={handleAddExternalApi}
            className="inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-primaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          >
            외부 API 추가
          </button>
        </div>

        {apiDraft.externals.length ? (
          apiDraft.externals.map((external, index) => (
            <div
              key={`external-${index}`}
              className="rounded-lg border border-border-light bg-background-cardLight p-4 text-sm text-text-primaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  이름
                  <input
                    type="text"
                    value={external.name}
                    onChange={(event) => handleExternalChange(index, "name", event.target.value)}
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  Masked Key
                  <input
                    type="text"
                    value={external.maskedKey}
                    onChange={(event) => handleExternalChange(index, "maskedKey", event.target.value)}
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
                <label className="inline-flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  <input
                    type="checkbox"
                    checked={external.enabled}
                    onChange={(event) => handleExternalChange(index, "enabled", event.target.checked)}
                    className="h-4 w-4 rounded border-border-light text-primary focus:ring-primary dark:border-border-dark"
                  />
                  활성화
                </label>
              <button
                type="button"
                onClick={() => handleRemoveExternal(index)}
                className="inline-flex items-center rounded-lg border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
              >
                삭제
              </button>
            </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  만료 예정일(선택)
                  <input
                    type="date"
                    value={external.expiresAt}
                    onChange={(event) => handleExternalChange(index, "expiresAt", event.target.value)}
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  경고 일수(선택)
                  <input
                    type="number"
                    min={0}
                    value={external.warningDays}
                    onChange={(event) => handleExternalChange(index, "warningDays", event.target.value)}
                    placeholder="예: 14"
                    className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                  />
                </label>
              </div>
              <p className="mt-2 text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                최근 회전 시각: {formatDateTime(external.lastRotatedAt, { fallback: "기록 없음" })}
              </p>
              {external.rotationHistory.length > 0 ? (
                <div className="mt-2 space-y-1 rounded-lg bg-background-base/40 p-2 text-[11px] text-text-secondaryLight dark:bg-background-cardDark/40 dark:text-text-secondaryDark">
                  <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">?? ??</span>
                  <ul className="space-y-1">
                    {external.rotationHistory.slice(0, 3).map((entry, historyIndex) => (
                      <li key={`${entry.rotatedAt}-${historyIndex}`} className="flex flex-wrap items-center gap-2">
                        <span>{formatDateTime(entry.rotatedAt, { fallback: "기록 없음" })}</span>
                        <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">by {entry.actor}</span>
                        {entry.note ? (
                          <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">({entry.note})</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <label className="mt-3 flex flex-col gap-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                Metadata (JSON)
                <textarea
                  value={external.metadataJson}
                  onChange={(event) => handleExternalChange(index, "metadataJson", event.target.value)}
                  className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                />
              </label>
            </div>
          ))
        ) : (
          <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">외부 API 설정이 아직 없어요.</p>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          실행자(Actor)
          <input
            type="text"
            value={apiDraft.actor}
            onChange={(event) => setApiDraft((prev) => ({ ...prev, actor: event.target.value }))}
            placeholder={adminActor ?? "운영자 이름"}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          변경 메모
          <input
            type="text"
            value={apiDraft.note}
            onChange={(event) => setApiDraft((prev) => ({ ...prev, note: event.target.value }))}
            placeholder="예: Langfuse production 키 교체"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>

      {apiDraft.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {apiDraft.error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={handleApiSubmit}
          disabled={updateApiKeys.isPending}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition duration-150 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updateApiKeys.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updateApiKeys.isPending ? (
            <>
              <AdminButtonSpinner className="border-white/40 border-t-white" />
              <span>저장 중…</span>
            </>
          ) : apiSaveSuccess ? (
            <>
              <AdminSuccessIcon className="text-white" />
              <span>저장 완료!</span>
            </>
          ) : (
            "운영 설정 저장"
          )}
        </button>
      </div>
    </section>
  );
}
