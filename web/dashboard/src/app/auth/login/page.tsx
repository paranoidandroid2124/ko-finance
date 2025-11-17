"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { FormEvent, useState } from "react";
import type { Route } from "next";

import OAuthButtonGroup from "@/components/auth/OAuthButtonGroup";
import AuthPageShell from "@/components/auth/AuthPageShell";
import { formatAuthError, toApiDetail, type ApiDetail } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

const DEFAULT_REDIRECT = "/app" as Route;
const DEFAULT_ERROR_MESSAGE = "로그인에 실패했습니다. 다시 시도해 주세요.";

const resolveRedirectTarget = (target: string | null | undefined): Route => {
  if (!target) {
    return DEFAULT_REDIRECT;
  }
  if (target.startsWith("/")) {
    return target as Route;
  }
  try {
    if (typeof window !== "undefined") {
      const url = new URL(target, window.location.origin);
      if (url.origin === window.location.origin) {
        return `${url.pathname}${url.search}${url.hash}` as Route;
      }
    }
  } catch {
    // fall back below
  }
  return DEFAULT_REDIRECT;
};

export default function LoginPage() {
  const params = useSearchParams();
  const router = useRouter();
  const callbackUrl = params?.get("redirect") ?? params?.get("callbackUrl") ?? DEFAULT_REDIRECT;
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<ApiDetail | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [sendingVerify, setSendingVerify] = useState(false);
  const [sendingUnlock, setSendingUnlock] = useState(false);
  const [ssoProvider, setSsoProvider] = useState("");
  const [lastEmail, setLastEmail] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setActionMessage(null);
    setActionError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    const password = String(form.get("password") || "");
    const rememberMe = form.get("remember") === "on";
    setLastEmail(email);
    const result = await signIn("credentials", {
      redirect: false,
      email,
      password,
      remember: rememberMe ? "true" : "false",
      callbackUrl,
    });
    setSubmitting(false);
    if (result?.error) {
      const detail = toApiDetail(result.error ?? null);
      setErrorDetail(detail);
      setError(formatAuthError(detail, DEFAULT_ERROR_MESSAGE));
      return;
    }
    setErrorDetail(null);
    setError(null);
    const resolvedRedirect = resolveRedirectTarget(result?.url ?? callbackUrl);
    router.push(resolvedRedirect);
  };

  const startOidcSso = () => {
    const slug = ssoProvider.trim();
    if (!slug) {
      setActionError("SSO provider slug를 입력한 뒤 시도해주세요.");
      return;
    }
    const target = `/api/v1/auth/oidc/${encodeURIComponent(slug)}/authorize?callbackUrl=${encodeURIComponent(
      callbackUrl,
    )}`;
    window.location.href = target;
  };

  const openSamlMetadata = () => {
    const slug = ssoProvider.trim();
    if (!slug) {
      setActionError("SSO provider slug를 입력한 뒤 메타데이터를 확인해주세요.");
      return;
    }
    const metadataUrl = `/api/v1/auth/saml/${encodeURIComponent(slug)}/metadata`;
    window.open(metadataUrl, "_blank", "noopener,noreferrer");
  };

  const ensureEmail = (): string | null => {
    if (!lastEmail.trim()) {
      setActionError("이메일을 입력하고 로그인을 시도한 뒤 다시 눌러 주세요.");
      return null;
    }
    return lastEmail;
  };

  const handleResendVerification = async () => {
    const targetEmail = ensureEmail();
    if (!targetEmail) {
      return;
    }
    setSendingVerify(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await postAuth("/api/v1/auth/email/verify/resend", { email: targetEmail });
      setActionMessage("인증 메일을 다시 보냈습니다. 메일함을 확인해 주세요.");
    } catch (err) {
      if (err instanceof AuthApiError) {
        setActionError(formatAuthError(err.detail, "인증 메일을 다시 보내지 못했습니다."));
      } else {
        setActionError(err instanceof Error ? err.message : "네트워크 오류가 발생했습니다.");
      }
    } finally {
      setSendingVerify(false);
    }
  };

  const handleUnlockRequest = async () => {
    const targetEmail = ensureEmail();
    if (!targetEmail) {
      return;
    }
    setSendingUnlock(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await postAuth("/api/v1/auth/account/unlock/request", { email: targetEmail });
      setActionMessage("잠금 해제 링크를 이메일로 보냈습니다. 메일함을 확인해 주세요.");
    } catch (err) {
      if (err instanceof AuthApiError) {
        setActionError(formatAuthError(err.detail, "잠금 해제 링크를 보낼 수 없습니다."));
      } else {
        setActionError(err instanceof Error ? err.message : "네트워크 오류가 발생했습니다.");
      }
    } finally {
      setSendingUnlock(false);
    }
  };

  return (
    <AuthPageShell title="이메일로 로그인">
      {error ? (
        <div className="rounded-lg border border-red-500/60 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}
      {errorDetail?.code === "auth.needs_verification" ? (
        <div className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
          인증 메일을 받지 못했다면 아래 버튼으로 다시 받아볼 수 있습니다.
          <button
            type="button"
            onClick={handleResendVerification}
            disabled={sendingVerify || submitting}
            className="mt-2 rounded-lg border border-blue-400 px-3 py-1 text-xs font-semibold text-blue-100 hover:border-blue-200 disabled:opacity-50"
          >
            {sendingVerify ? "재전송 중..." : "인증 메일 다시 보내기"}
          </button>
        </div>
      ) : null}
      {errorDetail?.code === "auth.account_locked" ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          연속 실패로 계정이 잠겼습니다. 잠금 해제 링크를 받아 바로 풀 수 있습니다.
          <button
            type="button"
            onClick={handleUnlockRequest}
            disabled={sendingUnlock || submitting}
            className="mt-2 rounded-lg border border-amber-400 px-3 py-1 text-xs font-semibold text-amber-100 hover:border-amber-200 disabled:opacity-50"
          >
            {sendingUnlock ? "요청 중..." : "잠금 해제 링크 보내기"}
          </button>
        </div>
      ) : null}
      {actionMessage ? (
        <div className="rounded-lg border border-emerald-500/60 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100">
          {actionMessage}
        </div>
      ) : null}
      {actionError ? (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">{actionError}</div>
      ) : null}
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          이메일
          <input
            name="email"
            type="email"
            required
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            placeholder="name@example.com"
            autoComplete="email"
            disabled={submitting}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          비밀번호
          <input
            name="password"
            type="password"
            required
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            placeholder="********"
            autoComplete="current-password"
            disabled={submitting}
          />
        </label>
        <label className="flex items-center justify-between text-sm text-slate-300">
          <span>로그인 상태 유지</span>
          <div className="relative">
            <input
              name="remember"
              type="checkbox"
              className="peer sr-only"
              disabled={submitting}
              aria-label="로그인 상태 유지"
            />
            <div className="h-5 w-10 rounded-full bg-slate-700 transition peer-checked:bg-blue-500 peer-disabled:bg-slate-700/60"></div>
            <div className="pointer-events-none absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition peer-checked:translate-x-5 peer-disabled:bg-white/70"></div>
          </div>
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-500 py-2 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "로그인 중..." : "로그인"}
        </button>
      </form>
      <div className="space-y-3">
        <p className="text-center text-sm text-slate-400">또는 소셜 계정으로 계속하기</p>
        <OAuthButtonGroup callbackUrl={callbackUrl} disabled={submitting} />
      </div>
      <div className="space-y-3 rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
        <p className="text-sm font-semibold text-slate-100">SSO (SAML/OIDC)로 로그인</p>
        <p className="text-sm text-slate-400">
          조직에서 발급한 provider slug를 입력하면 전용 OIDC/SAML 엔드포인트로 이동할 수 있습니다.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="text"
            value={ssoProvider}
            onChange={(event) => setSsoProvider(event.target.value)}
            placeholder="예: acme-saml"
            disabled={submitting}
            className="flex-1 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
          <div className="flex flex-1 gap-2">
            <button
              type="button"
              onClick={startOidcSso}
              disabled={submitting}
              className="flex-1 rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100 transition hover:border-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              OIDC 시작
            </button>
            <button
              type="button"
              onClick={openSamlMetadata}
              disabled={submitting}
              className="flex-1 rounded-lg border border-slate-600/60 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              SAML 메타데이터
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500">
          IdP가 SAML만 지원하는 경우 위 메타데이터 URL과 ACS 경로(`/api/v1/auth/saml/[slug]/acs`)를 등록한 뒤 IdP
          Initiated 로그인을 사용하세요.
        </p>
      </div>
      <div className="flex flex-col gap-2 text-center text-sm text-slate-400">
        <Link href="/auth/forgot-password" className="text-blue-300 hover:text-blue-200">
          비밀번호를 잊으셨나요?
        </Link>
        <span>
          아직 계정이 없다면{" "}
          <Link href="/auth/register" className="text-blue-300 hover:text-blue-200">
            가입하기
          </Link>
        </span>
        <span>
          <Link href="/public" className="text-blue-300 hover:text-blue-200">
            로그인 없이 미리보기 체험하기
          </Link>
        </span>
      </div>
    </AuthPageShell>
  );
}
