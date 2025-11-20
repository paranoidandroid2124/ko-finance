"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const timer = setTimeout(() => {
      router.replace("/dashboard");
    }, 2000);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#050A18] p-6 text-center text-white">
      <div className="rounded-3xl border border-white/10 bg-white/5 px-8 py-10 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.4em] text-blue-300">Nuvien</p>
        <h1 className="mt-4 text-2xl font-semibold">계정을 확인하는 중입니다…</h1>
        <p className="mt-2 text-sm text-slate-400">
          잠시만 기다려 주세요. 인증이 완료되면 자동으로 대시보드로 이동합니다.
        </p>
      </div>
    </div>
  );
}
