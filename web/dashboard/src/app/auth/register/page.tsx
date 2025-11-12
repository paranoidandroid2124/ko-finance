"use client";

import Link from "next/link";
import type { Route } from "next";
import { FormEvent, useState } from "react";

import AuthPageShell from "@/components/auth/AuthPageShell";
import OAuthButtonGroup from "@/components/auth/OAuthButtonGroup";
import { formatAuthError } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

const TERMS_ROUTE = "/docs/policy" as Route;

export default function RegisterPage() {
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSuccess(null);
    setError(null);
    const form = new FormData(event.currentTarget);
    const payload = {
      email: String(form.get("email") || "").trim(),
      password: String(form.get("password") || ""),
      name: String(form.get("name") || "").trim() || null,
      acceptTerms: form.get("terms") === "on",
      signupChannel: "email",
    };
    try {
      await postAuth("/api/v1/auth/register", payload);
      setSuccess("가입이 완료되었습니다. 이메일로 전송된 확인 메일을 확인해 주세요.");
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(formatAuthError(err.detail, "가입에 실패했습니다."));
      } else {
        setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthPageShell
      title="이메일로 가입"
      subtitle="비밀번호를 설정하고 이메일을 검증하면 바로 시작할 수 있어요."
      backLink={{ href: "/auth/login", label: "로그인으로 돌아가기" }}
    >
      {success ? (
        <div className="rounded-lg border border-emerald-500/60 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">{success}</div>
      ) : null}
      {error ? (
        <div className="rounded-lg border border-red-500/60 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          이름
          <input
            name="name"
            type="text"
            placeholder="홍길동"
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            disabled={submitting}
          />
        </label>
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
            minLength={8}
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-base text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            placeholder="8자 이상 영문·숫자·특수문자 조합"
            autoComplete="new-password"
            disabled={submitting}
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            name="terms"
            type="checkbox"
            required
            className="h-4 w-4 rounded border-slate-700 bg-slate-900"
            disabled={submitting}
          />
          <span>
            <Link href={TERMS_ROUTE} className="text-blue-300 hover:text-blue-200">
              이용약관
            </Link>
            과 개인정보 처리방침에 동의합니다.
          </span>
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-blue-500 py-2 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "가입 중..." : "가입하기"}
        </button>
      </form>
      <div className="space-y-3">
        <p className="text-center text-sm text-slate-400">소셜 계정을 사용할 수도 있어요.</p>
        <OAuthButtonGroup disabled={submitting} />
      </div>
      <p className="text-center text-sm text-slate-400">
        이미 계정이 있다면{" "}
        <Link href="/auth/login" className="text-blue-300 hover:text-blue-200">
          로그인
        </Link>
      </p>
    </AuthPageShell>
  );
}
