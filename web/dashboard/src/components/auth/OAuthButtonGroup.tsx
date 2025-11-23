"use client";

import type { Provider } from "@supabase/supabase-js";

import supabase from "@/lib/supabase";

type OAuthProvider = Extract<Provider, "google" | "kakao" | "naver">;

const PROVIDERS: Array<{ id: OAuthProvider; label: string }> = [
  { id: "google", label: "Google" },
  { id: "kakao", label: "Kakao" },
  { id: "naver", label: "Naver" },
];

type Props = {
  callbackUrl?: string;
  disabled?: boolean;
};

export function OAuthButtonGroup({ callbackUrl, disabled }: Props) {
  return (
    <div className="flex flex-col gap-3">
      {PROVIDERS.map((provider) => (
        <button
          key={provider.id}
          type="button"
          disabled={disabled}
          onClick={() =>
            supabase.auth.signInWithOAuth({
              provider: provider.id,
              options: { redirectTo: callbackUrl ?? `${window.location.origin}/auth/callback` },
            })
          }
          className="flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-medium text-white transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {provider.label} 계정으로 계속하기
        </button>
      ))}
    </div>
  );
}

export default OAuthButtonGroup;
