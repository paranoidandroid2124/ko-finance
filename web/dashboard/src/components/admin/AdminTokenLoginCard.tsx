"use client";

import clsx from "classnames";
import { useEffect, useState, type FormEvent } from "react";

import { useAdminSession } from "@/hooks/useAdminSession";
import { resolveApiBase } from "@/lib/apiBase";
import { ADMIN_SESSION_STORAGE_KEY } from "@/lib/adminApi";
import { useToastStore } from "@/store/toastStore";

const COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

export function AdminTokenLoginCard() {
  const { isUnauthorized, refetch } = useAdminSession();
  const pushToast = useToastStore((state) => state.show);

  const [token, setToken] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasStoredToken, setHasStoredToken] = useState(false);
  const [autoRetryAttempted, setAutoRetryAttempted] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(ADMIN_SESSION_STORAGE_KEY);
    setHasStoredToken(Boolean(stored));
  }, [isUnauthorized]);

  useEffect(() => {
    if (!isUnauthorized || !hasStoredToken || autoRetryAttempted) {
      return;
    }
    setAutoRetryAttempted(true);
    refetch({ throwOnError: false }).catch(() => undefined);
  }, [isUnauthorized, hasStoredToken, autoRetryAttempted, refetch]);

  if (!isUnauthorized) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    const trimmedToken = token.trim();
    if (!trimmedToken) {
      setErrorMessage("운영 토큰을 입력해 주세요. 받은 값이 없다면 운영 채널에 요청해 주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const baseUrl = resolveApiBase();
      const response = await fetch(`${baseUrl}/api/v1/admin/session`, {
        method: "GET",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${trimmedToken}`,
        },
        credentials: "include",
        cache: "no-store",
      });

      if (!response.ok) {
        const friendly =
          response.status === 403
            ? "토큰이 맞는지 다시 확인해볼까요? 필요하면 운영 Slack 채널로 새 토큰을 요청해 주세요."
            : "운영 세션을 확인하는 중에 문제가 있었어요. 잠시 후 다시 시도해 주세요.";
        setErrorMessage(friendly);
        pushToast({
          id: `admin/token-login/error/${Date.now()}`,
          title: "토큰 확인이 필요해요",
          message: friendly,
          intent: "warning",
        });
        return;
      }

      await response.json();

      if (typeof window !== "undefined") {
        window.localStorage.setItem(ADMIN_SESSION_STORAGE_KEY, trimmedToken);
      }

      const cookieParts = [
        `admin_session_token=${encodeURIComponent(trimmedToken)}`,
        "Path=/",
        "SameSite=Lax",
        `Max-Age=${COOKIE_MAX_AGE_SECONDS}`,
      ];
      if (typeof window !== "undefined" && window.location.protocol === "https:") {
        cookieParts.push("Secure");
      }
      document.cookie = cookieParts.join("; ");

      pushToast({
        id: `admin/token-login/success/${Date.now()}`,
        title: "운영 세션이 준비됐어요",
        message: "감사 로그와 플랜 조정 도구를 바로 열어둘게요.",
        intent: "success",
      });

      setToken("");
      setHasStoredToken(true);
      setAutoRetryAttempted(false);
      await refetch({ throwOnError: false });
    } catch (error) {
      const message =
        error instanceof Error
          ? `세션을 확인하지 못했어요: ${error.message}`
          : "세션 확인 중 알 수 없는 오류가 발생했어요.";
      setErrorMessage(message);
      pushToast({
        id: `admin/token-login/unexpected/${Date.now()}`,
        title: "세션 확인에 실패했어요",
        message,
        intent: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClearStoredToken = () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
      document.cookie = "admin_session_token=; Path=/; Max-Age=0; SameSite=Lax";
    }
    setHasStoredToken(false);
    setAutoRetryAttempted(false);
    pushToast({
      id: `admin/token-login/cleared/${Date.now()}`,
      title: "저장된 토큰을 지웠어요",
      message: "새 토큰으로 다시 로그인하면 쿠키가 갱신돼요.",
      intent: "info",
    });
  };

  return (
    <section className="mb-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-2">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">운영 전용 로그인</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          안녕하세요 운영팀 여러분, 받고 계신 관리자 토큰을 입력하면 감사 로그와 플랜 도구가 바로 열립니다.
        </p>
        {hasStoredToken ? (
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            저장된 토큰으로 자동 인증을 시도했어요. 문제가 계속되면 아래에서 토큰을 초기화하고 새 값을 입력해 주세요.
          </p>
        ) : null}
      </header>

      <form className="mt-4 space-y-4" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark" htmlFor="admin-token">
            관리자 토큰
          </label>
          <input
            id="admin-token"
            name="admin-token"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="예: ops_live_xxx"
            autoComplete="off"
            aria-invalid={errorMessage ? "true" : "false"}
            aria-describedby={errorMessage ? "admin-token-error" : undefined}
            className={clsx(
              "w-full rounded-lg border bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:bg-background-cardDark",
              errorMessage
                ? "border-amber-400 text-amber-900 placeholder:text-amber-400 dark:border-amber-500 dark:text-amber-200"
                : "border-border-light text-text-primaryLight placeholder:text-text-tertiaryLight dark:border-border-dark dark:text-text-primaryDark dark:placeholder:text-text-tertiaryDark",
            )}
          />
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
            입력하신 토큰은 이 브라우저의 쿠키로만 저장되고, 세션 만료 전까지 다시 묻지 않아요.
          </p>
        </div>

        {errorMessage ? (
          <div
            id="admin-token-error"
            role="alert"
            className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-500/60 dark:bg-amber-500/10 dark:text-amber-200"
          >
            {errorMessage}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-end gap-3">
          {hasStoredToken ? (
            <button
              type="button"
              onClick={handleClearStoredToken}
              className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40"
            >
              저장된 토큰 초기화
            </button>
          ) : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className={clsx(
              "inline-flex items-center rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              isSubmitting ? "cursor-not-allowed opacity-60" : "hover:bg-primary-hover",
            )}
          >
            {isSubmitting ? "세션 확인 중…" : "운영 세션 열기"}
          </button>
        </div>
      </form>
    </section>
  );
}
