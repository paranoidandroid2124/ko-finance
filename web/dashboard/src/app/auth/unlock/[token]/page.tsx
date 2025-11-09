"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AuthPageShell from "@/components/auth/AuthPageShell";
import { formatAuthError } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

type Props = { params: { token: string } };

export default function AccountUnlockPage({ params }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string>("계정 잠금 해제를 진행하고 있습니다...");

  useEffect(() => {
    const confirmUnlock = async () => {
      setStatus("pending");
      setMessage("계정 잠금 해제를 진행하고 있습니다...");
      try {
        await postAuth("/api/v1/auth/account/unlock/confirm", { token: params.token });
        setStatus("success");
        setMessage("계정 잠금이 해제되었습니다. 이제 로그인할 수 있습니다.");
      } catch (error) {
        setStatus("error");
        if (error instanceof AuthApiError) {
          setMessage(formatAuthError(error.detail, "잠금 해제에 실패했습니다. 다시 시도해 주세요."));
        } else {
          setMessage(error instanceof Error ? error.message : "연결 중 오류가 발생했습니다.");
        }
      }
    };
    void confirmUnlock();
  }, [params.token]);

  return (
    <AuthPageShell
      title="계정 잠금 해제"
      subtitle="잠금 해제 링크를 통해 계정 보안을 확인 중입니다."
      backLink={{ href: "/auth/login", label: "로그인으로 돌아가기" }}
    >
      <div
        className={`rounded-lg border px-4 py-3 text-sm ${
          status === "success"
            ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-100"
            : status === "error"
              ? "border-red-500/60 bg-red-500/10 text-red-200"
              : "border-slate-700 bg-slate-900 text-slate-100"
        }`}
      >
        {message}
      </div>
      {status === "success" ? (
        <button
          type="button"
          className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-400"
          onClick={() => router.push("/auth/login")}
        >
          로그인하기
        </button>
      ) : null}
    </AuthPageShell>
  );
}
