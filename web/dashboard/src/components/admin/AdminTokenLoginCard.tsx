"use client";

import clsx from "classnames";
import { useState, type FormEvent } from "react";

import { useAdminSession } from "@/hooks/useAdminSession";
import { AdminApiError, AdminUnauthorizedError, loginAdminWithCredentials } from "@/lib/adminApi";
import { useToastStore } from "@/store/toastStore";

export function AdminTokenLoginCard() {
  const { isUnauthorized, refetch } = useAdminSession();
  const pushToast = useToastStore((state) => state.show);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isUnauthorized) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    if (!email || !password) {
      setErrorMessage("이메일과 비밀번호를 모두 입력해 주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await loginAdminWithCredentials({
        email: email.trim(),
        password,
        otp: otp ? otp.trim() : undefined,
      });
      pushToast({
        id: `admin/token-login/success/${Date.now()}`,
        title: "운영 세션이 준비됐어요",
        message: "감사 로그와 플랜 조정 도구를 바로 열어둘게요.",
        intent: "success",
      });
      setPassword("");
      setOtp("");
      await refetch({ throwOnError: false });
    } catch (error) {
      let message = "세션을 확인하지 못했어요.";
      if (error instanceof AdminApiError || error instanceof AdminUnauthorizedError) {
        message = error.message;
      } else if (error instanceof Error) {
        try {
          const parsed = JSON.parse(error.message);
          const detailMessage =
            typeof parsed?.detail?.message === "string"
              ? parsed.detail.message
              : typeof parsed?.message === "string"
                ? parsed.message
                : null;
          message = detailMessage ?? `세션을 확인하지 못했어요: ${error.message}`;
        } catch {
          message = `세션을 확인하지 못했어요: ${error.message}`;
        }
      }
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

  return (
    <section className="mb-6 rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <header className="space-y-2">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">운영 전용 로그인</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          운영자 이메일·비밀번호와 MFA 코드를 입력하면 서버가 HttpOnly 쿠키로 세션을 개설합니다.
        </p>
      </header>

      <form className="mt-4 space-y-4" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark" htmlFor="admin-email">
            운영자 이메일
          </label>
          <input
            id="admin-email"
            name="admin-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="ops@your-company.com"
            autoComplete="email"
            aria-invalid={errorMessage ? "true" : "false"}
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark" htmlFor="admin-password">
            비밀번호
          </label>
          <input
            id="admin-password"
            name="admin-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••"
            autoComplete="current-password"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark" htmlFor="admin-otp">
            MFA 코드(6자리)
          </label>
          <input
            id="admin-otp"
            name="admin-otp"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={otp}
            onChange={(event) => setOtp(event.target.value)}
            placeholder="123456"
            className="w-full rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
          <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">TOTP 앱(예: Google Authenticator)에서 발급받은 코드를 입력하세요.</p>
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
