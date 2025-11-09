"use client";

import { FormEvent, useState } from "react";

import AuthPageShell from "@/components/auth/AuthPageShell";
import { formatAuthError } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

export default function ForgotPasswordPage() {
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    setError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim();
    try {
      await postAuth("/api/v1/auth/password-reset/request", { email });
      setMessage("재설정 링크를 이메일로 전송했습니다. 받은 편지함을 확인해 주세요.");
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(formatAuthError(err.detail, "요청을 처리할 수 없습니다."));
      } else {
        setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthPageShell
      title="비밀번호 재설정"
      subtitle="가입에 사용한 이메일 주소로 재설정 안내를 전송합니다."
      backLink={{ href: "/auth/login", label: "로그인으로 돌아가기" }}
    >
      {message ? (
        <div className="rounded-lg border border-emerald-500/60 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">{message}</div>
      ) : null}
      {error ? (
        <div className="rounded-lg border border-red-500/60 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
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
            disabled={submitting}
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-500 py-2 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "전송 중..." : "재설정 링크 보내기"}
        </button>
      </form>
      <p className="text-center text-sm text-slate-400">
        이메일을 받지 못했다면 <span className="text-slate-200">support@kfinance.ai</span> 로 연락해 주세요.
      </p>
    </AuthPageShell>
  );
}
