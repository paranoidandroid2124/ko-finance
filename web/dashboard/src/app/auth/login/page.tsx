"use client";

import Link from "next/link";
import { LogIn } from "lucide-react";
import { useState } from "react";

import { supabase } from "@/lib/supabase";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);

  const handleGoogleLogin = async () => {
    setLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) {
      console.error("[Supabase] Google login failed", error.message);
      alert("Google 로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-[#0f172a] p-4 text-white">
      <div className="absolute -bottom-[20%] right-[-10%] h-[55%] w-[55%] rounded-full bg-cyan-500/15 blur-[130px]" />
      <div className="relative z-10 w-full max-w-md rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-xl">
        <div className="mb-8 text-center">
          <h1 className="mb-2 text-3xl font-bold">다시 돌아오셨네요!</h1>
          <p className="text-slate-400">Nuvien Copilot에 로그인하고 분석을 이어가세요.</p>
        </div>

        <button
          type="button"
          onClick={handleGoogleLogin}
          disabled={loading}
          className="mb-6 flex w-full items-center justify-center gap-2 rounded-xl bg-white py-3 font-bold text-slate-900 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-70"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          {loading ? "연결 중..." : "Google 계정으로 계속하기"}
        </button>

        <form className="space-y-4" onSubmit={(event) => event.preventDefault()}>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">이메일</label>
            <input
              type="email"
              required
              className="w-full rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-3 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors"
              placeholder="name@company.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">비밀번호</label>
            <input
              type="password"
              required
              className="w-full rounded-xl border border-slate-700 bg-slate-800/50 px-4 py-3 text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-3 font-bold text-slate-900 transition hover:bg-gray-100"
          >
            로그인
            <LogIn className="h-4 w-4" />
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-500">
          아직 계정이 없나요?{" "}
          <Link href="/auth/signup" className="font-medium text-blue-400 hover:text-blue-300">
            회원가입
          </Link>
        </div>
      </div>
    </div>
  );
}
