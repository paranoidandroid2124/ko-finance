"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { resolveApiBase } from "@/lib/apiBase";
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
    return "/settings";
  }
  return value;
};

export default function TossPaymentSuccessPage() {
  const searchParams = useSearchParams();
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
        const response = await fetch(`${baseUrl}/api/v1/payments/toss/confirm`, {
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
        title: "결제를 확인했어요",
        message: targetTier
          ? `${planTierLabel(targetTier)} 플랜 결제가 정상 처리됐습니다.`
          : "토스 결제가 정상 처리됐습니다.",
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

  const title =
    status === "success"
      ? "결제가 완료됐어요"
      : status === "confirming"
      ? "결제 상태를 확인하는 중이에요"
      : "결제를 확인하지 못했어요";

  const description =
    status === "success"
      ? "관리자 플랜 정보가 곧 새로고침됩니다. 아래 버튼을 눌러 설정 페이지에서 혜택을 확인해 주세요."
      : status === "confirming"
      ? "토스페이먼츠 응답을 확인 중입니다. 잠시만 기다려 주세요."
      : errorMessage ?? "원인을 알 수 없는 오류가 발생했어요. 다시 시도하거나 관리자에게 문의해 주세요.";
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
      ? "설정에서 혜택 보기"
      : "설정으로 이동";
  const actionHref = status === "error" ? undefined : redirectPath;
  const actionOnClick = status === "error" ? handleRetry : undefined;

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
      </div>
    </AppShell>
  );
}
