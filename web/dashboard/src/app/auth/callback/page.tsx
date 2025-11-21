"use client";

export const dynamic = "force-dynamic";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

import { supabase } from "@/lib/supabase";

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#050A18] p-6 text-center text-white">
          <div className="rounded-3xl border border-white/10 bg-white/5 px-8 py-10 shadow-2xl backdrop-blur">
            <p className="text-xs uppercase tracking-[0.4em] text-blue-300">Nuvien</p>
            <h1 className="mt-4 text-2xl font-semibold">계정을 확인하는 중입니다…</h1>
            <p className="mt-2 text-sm text-slate-400">잠시만 기다려 주세요. 인증이 완료되면 자동으로 이동합니다.</p>
          </div>
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams?.get("code");
    const nextPath = searchParams?.get("next") || "/chat";
    if (!code) {
      setErrorMessage("인증 코드가 없습니다. 다시 로그인해 주세요.");
      const timer = setTimeout(() => router.replace("/auth/login"), 1500);
      return () => clearTimeout(timer);
    }

    const run = async () => {
      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (error) {
        setErrorMessage(error.message || "인증에 실패했습니다. 다시 시도해 주세요.");
        setTimeout(() => router.replace("/auth/login"), 1500);
        return;
      }
      router.replace(nextPath as Route);
    };
    void run();
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#050A18] p-6 text-center text-white">
      <div className="rounded-3xl border border-white/10 bg-white/5 px-8 py-10 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.4em] text-blue-300">Nuvien</p>
        <h1 className="mt-4 text-2xl font-semibold">
          {errorMessage ? "인증에 실패했습니다" : "계정을 확인하는 중입니다…"}
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          {errorMessage ?? "잠시만 기다려 주세요. 인증이 완료되면 자동으로 이동합니다."}
        </p>
      </div>
    </div>
  );
}
