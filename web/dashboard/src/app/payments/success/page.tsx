"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { resolveApiBase } from "@/lib/apiBase";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import { logEvent } from "@/lib/telemetry";
import { usePlanStore, type PlanTier } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";
import { planTierLabel } from "@/constants/planPricing";
import { PaymentResultCard } from "@/components/payments/PaymentResultCard";

type Status = "confirming" | "success" | "error";

const isPlanTier = (value: string | null): value is PlanTier =>
  value === "free" || value === "starter" || value === "pro" || value === "enterprise";

const safeRedirectPath = (value?: string | null) => {
  if (!value || !value.startsWith("/")) {
    return "/dashboard";
  }
  return value;
};

const REDIRECT_DELAY_MS = 10_000;

export default function TossPaymentSuccessPage() {
  return (
    <Suspense fallback={<PaymentStatusFallback />}>
      <TossPaymentSuccessPageInner />
    </Suspense>
  );
}

function PaymentStatusFallback() {
  return (
    <AppShell>
      <div className="flex h-[50vh] items-center justify-center">
        <div className="flex items-center gap-2 text-slate-300">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
          <span>결제를 확인하는 중입니다. 잠시만 기다려 주세요!</span>
        </div>
      </div>
    </AppShell>
  );
}

function TossPaymentSuccessPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const fetchPlan = usePlanStore((state) => state.fetchPlan);
  const pushToast = useToastStore((state) => state.show);

  const paymentKey = searchParams?.get("paymentKey") ?? null;
  const orderId = searchParams?.get("orderId") ?? null;
  const amountParam = searchParams?.get("amount") ?? null;
  const tierParam = searchParams?.get("tier") ?? null;
  const redirectParam = searchParams?.get("redirectPath") ?? null;

  const targetTier = isPlanTier(tierParam) ? tierParam : null;
  const amount = amountParam ? Number.parseInt(amountParam, 10) : NaN;
  const redirectPath = safeRedirectPath(redirectParam);

  const initialStatus: Status =
    paymentKey && orderId && Number.isFinite(amount) && !Number.isNaN(amount) ? "confirming" : "error";

  const [status, setStatus] = useState<Status>(initialStatus);
  const [errorMessage, setErrorMessage] = useState<string | null>(
    initialStatus === "error" ? "결제 검증에 필요한 정보가 누락됐어요." : null,
  );

  const toastShownRef = useRef(false);
  const redirectStartedRef = useRef(false);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(Math.ceil(REDIRECT_DELAY_MS / 1000));

  const amountLabel = useMemo(() => {
    if (!Number.isFinite(amount) || Number.isNaN(amount)) {
      return "확인 불가";
    }
    return `${amount.toLocaleString("ko-KR")}원`;
  }, [amount]);

  useEffect(() => {
    if (status !== "confirming" || !paymentKey || !orderId || !Number.isFinite(amount)) {
      return;
    }

    let cancelled = false;

    const confirmPayment = async () => {
      try {
        const baseUrl = resolveApiBase();
        const response = await fetchWithAuth(`${baseUrl}/api/v1/payments/toss/confirm`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            paymentKey,
            orderId,
            amount,
            planTier: targetTier ?? undefined,
          }),
        });

        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          const message =
            typeof detail?.detail?.message === "string"
              ? detail.detail.message
              : "토스 결제 정보를 확인하지 못했어요.";
          throw new Error(message);
        }

        if (cancelled) {
          return;
        }

        setStatus("success");
        logEvent("payments.confirm.success", {
          orderId,
          paymentKey,
          amount,
          tier: targetTier,
        });

        void fetchPlan().catch(() => undefined);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "결제 승인 중 알 수 없는 오류가 발생했어요.";
        setErrorMessage(message);
        setStatus("error");
        logEvent("payments.confirm.error", {
          orderId,
          paymentKey,
          amount,
          tier: targetTier,
          message,
        });
      }
    };

    void confirmPayment();

    return () => {
      cancelled = true;
    };
  }, [amount, fetchPlan, orderId, paymentKey, status, targetTier]);

  useEffect(() => {
    if (status === "success" && !toastShownRef.current) {
      toastShownRef.current = true;
      pushToast({
        id: `payments/success/${orderId}`,
        title: "결제가 완료됐어요",
        message: targetTier
          ? `${planTierLabel(targetTier)} 플랜 결제가 정상 처리됐어요.`
          : "토스 결제가 정상 처리됐어요.",
        intent: "success",
      });
    }

    if (status === "error" && !toastShownRef.current && errorMessage) {
      toastShownRef.current = true;
      pushToast({
        id: `payments/error/${orderId ?? "unknown"}`,
        title: "결제 확인에 실패했어요",
        message: errorMessage,
        intent: "error",
      });
    }
  }, [errorMessage, orderId, pushToast, status, targetTier]);

  const handleRetry = useCallback(() => {
    toastShownRef.current = false;
    setErrorMessage(null);
    setStatus("confirming");
  }, []);

  const supportAction = useMemo(
    () => ({
      label: "도움이 필요하신가요?",
      href: "mailto:support@kfinance.ai?subject=Toss%20결제%20확인%20도움%20요청",
      external: true,
    }),
    [],
  );

  const startRedirectCountdown = useCallback(() => {
    if (redirectStartedRef.current) return;
    redirectStartedRef.current = true;
    const startedAt = Date.now();
    countdownTimerRef.current = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const remainingMs = Math.max(0, REDIRECT_DELAY_MS - elapsed);
      setRemainingSeconds(Math.ceil(remainingMs / 1000));
    }, 250);
    redirectTimerRef.current = setTimeout(() => {
      router.replace(redirectPath as Route);
    }, REDIRECT_DELAY_MS);
  }, [redirectPath, router]);

  const handleImmediateRedirect = useCallback(() => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
    if (redirectTimerRef.current) {
      clearTimeout(redirectTimerRef.current);
      redirectTimerRef.current = null;
    }
    redirectStartedRef.current = true;
    router.replace(redirectPath as Route);
  }, [redirectPath, router]);

  const title =
    status === "success"
      ? "결제가 완료됐어요"
      : status === "confirming"
      ? "결제 상태를 확인하는 중이에요"
      : "결제를 확인하지 못했어요";

  const description =
    status === "success"
      ? "플랜이 곧 적용돼요. 잠시 후 대시보드에서 혜택을 바로 확인하실 수 있어요."
      : status === "confirming"
      ? "토스 결제 응답을 확인 중입니다. 잠시만 기다려 주세요."
      : errorMessage ?? "원인을 알 수 없는 오류가 발생했어요. 다시 시도하거나 지원팀에 문의해 주세요.";
  const planLabel = targetTier ? planTierLabel(targetTier) : "미지정";
  const detailItems = [
    { label: "주문 번호", value: orderId ?? "확인 중" },
    { label: "결제 금액", value: amountLabel, emphasize: true },
    { label: "적용 플랜", value: planLabel, emphasize: true },
  ];

  const secondaryAction = status === "error" ? supportAction : undefined;
  const actionLabel =
    status === "error"
      ? "다시 결제 확인하기"
      : status === "success"
      ? "지금 대시보드로 이동"
      : "지금 대시보드로 이동";
  const actionHref = status === "error" ? undefined : redirectPath;
  const actionOnClick = status === "error" ? handleRetry : handleImmediateRedirect;

  useEffect(() => {
    if (status === "success" || status === "error") {
      startRedirectCountdown();
      return () => {
        if (countdownTimerRef.current) {
          clearInterval(countdownTimerRef.current);
        }
        if (redirectTimerRef.current) {
          clearTimeout(redirectTimerRef.current);
        }
      };
    }
    return undefined;
  }, [startRedirectCountdown, status]);

  return (
    <AppShell>
      <div className="mx-auto max-w-xl space-y-6 py-10">
        <PaymentResultCard
          status={status}
          title={title}
          description={description}
          details={detailItems}
          actionHref={actionHref}
          actionLabel={actionLabel}
          actionOnClick={actionOnClick}
          secondaryAction={secondaryAction}
        />
        {(status === "success" || status === "error") && (
          <p className="text-center text-xs text-slate-400">
            {remainingSeconds}초 후 자동으로 대시보드로 이동해요. 지금 바로 이동하려면 아래 버튼을 눌러주세요.
          </p>
        )}
      </div>
    </AppShell>
  );
}
