"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { FormEvent, useState } from "react";

import AuthPageShell from "@/components/auth/AuthPageShell";
import { formatAuthError } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

export default function ResetPasswordPage({ params }: { params: { token: string } }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") || "");
    const confirm = String(form.get("confirm") || "");
    if (password !== confirm) {
      setError("비밀번호와 확인 값이 일치해야 합니다.");
      setSubmitting(false);
      return;
    }
    try {
      await postAuth("/api/v1/auth/password-reset/confirm", { token: params.token, newPassword: password });
      setSuccess(true);
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(formatAuthError(err.detail, "비밀번호 재설정에 실패했습니다."));
      } else {
        setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthPageShell
      title="새 비밀번호 설정"
      subtitle="새 비밀번호를 입력하면 모든 기존 세션에서 로그아웃됩니다."
      backLink={{ href: "/auth/login", label: "로그인으로 돌아가기" }}
    >
      {success ? (
        <div className="rounded-lg border border-emerald-500/60 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
          비밀번호를 변경했습니다.{" "}
          <button type="button" className="underline" onClick={() => router.push("/auth/login")}>
            로그인으로 이동
          </button>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {error ? (
            <div className="rounded-lg border border-red-500/60 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
          ) : null}
          <label className="flex flex-col gap-2 text-sm text-slate-200">
            새 비밀번호
            <input
              name="password"
              type="password"
              required
              minLength={8}
              className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              placeholder="최소 8자 이상"
              disabled={submitting}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm text-slate-200">
            새 비밀번호 확인
            <input
              name="confirm"
              type="password"
              required
              minLength={8}
              className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              placeholder="다시 입력"
              disabled={submitting}
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-blue-500 py-2 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "변경 중..." : "비밀번호 변경"}
          </button>
        </form>
      )}
      {!success ? (
        <p className="text-center text-sm text-slate-400">
          링크가 만료되었다면{" "}
          <Link href="/auth/forgot-password" className="text-blue-300 hover:text-blue-200">
            새 링크 요청하기
          </Link>
        </p>
      ) : null}
    </AuthPageShell>
  );
}
