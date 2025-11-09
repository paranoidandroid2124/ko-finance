import { useEffect } from "react";
import { useRouter } from "next/navigation";

import AuthPageShell from "@/components/auth/AuthPageShell";
import { formatAuthError } from "@/lib/authError";
import { AuthApiError, postAuth } from "@/lib/authClient";

type VerifyResult = { ok: boolean; message: string };
const AUTO_REDIRECT_SECONDS = 3;

async function verifyToken(token: string): Promise<VerifyResult> {
  try {
    await postAuth(
      "/api/v1/auth/email/verify",
      { token },
      { cache: "no-store", credentials: "omit" },
    );
    return { ok: true, message: "이메일 인증이 완료되었습니다. 이제 로그인할 수 있습니다." };
  } catch (error) {
    if (error instanceof AuthApiError) {
      return {
        ok: false,
        message: formatAuthError(error.detail, "인증에 실패했습니다. 링크가 만료되었을 수 있습니다."),
      };
    }
    return {
      ok: false,
      message: error instanceof Error ? error.message : "인증 요청 중 오류가 발생했습니다.",
    };
  }
}

type Props = { params: { token: string } };

export default async function VerifyEmailPage({ params }: Props) {
  const result = await verifyToken(params.token);
  return (
    <AuthPageShell title="이메일 인증" subtitle="링크 검증 결과를 확인하세요." backLink={{ href: "/auth/login", label: "로그인으로 돌아가기" }}>
      <VerifyStatusMessage result={result} />
    </AuthPageShell>
  );
}

function VerifyStatusMessage({ result }: { result: VerifyResult }) {
  "use client";
  const router = useRouter();
  useEffect(() => {
    if (!result.ok) {
      return undefined;
    }
    const timer = setTimeout(() => {
      router.push("/auth/login");
    }, AUTO_REDIRECT_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [result.ok, router]);

  return (
    <>
      <div
        className={`rounded-lg border px-4 py-3 text-sm ${
          result.ok
            ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-100"
            : "border-red-500/60 bg-red-500/10 text-red-200"
        }`}
      >
        {result.message}
      </div>
      <div className="text-center text-sm text-slate-400">
        {result.ok ? (
          <p>
            {AUTO_REDIRECT_SECONDS}초 후 로그인 페이지로 이동합니다.{" "}
            <button
              type="button"
              onClick={() => router.push("/auth/login")}
              className="font-semibold text-blue-300 underline-offset-2 hover:text-blue-200 hover:underline"
            >
              지금 이동
            </button>
          </p>
        ) : (
          <p>
            토큰이 만료되었다면{" "}
            <button
              type="button"
              onClick={() => router.push("/auth/forgot-password")}
              className="font-semibold text-blue-300 underline-offset-2 hover:text-blue-200 hover:underline"
            >
              새 링크 요청
            </button>{" "}
            후 다시 시도해 주세요.
          </p>
        )}
      </div>
    </>
  );
}
