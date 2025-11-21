"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "next/navigation";

import { PaymentResultCard } from "@/components/payments/PaymentResultCard";
import { AppShell } from "@/components/layout/AppShell";
import { planTierLabel } from "@/constants/planPricing";
import { logEvent } from "@/lib/telemetry";
import type { PlanTier } from "@/store/planStore";
import { useToastStore } from "@/store/toastStore";

const isPlanTier = (value: string | null): value is PlanTier =>
  value === "free" || value === "starter" || value === "pro" || value === "enterprise";

const safeRedirectPath = (value?: string | null) => {
  if (!value || !value.startsWith("/")) {
    return "/settings";
  }
  return value;
};

const TOSS_ERROR_MESSAGES: Record<string, string> = {
  USER_CANCEL: "사용자가 결제를 취소했어요. 다시 시도해 주세요.",
  CANCELLED: "결제가 취소됐어요. 다시 시도하거나 다른 결제 수단을 선택해 주세요.",
  TIMEOUT: "결제 시간이 초과됐어요. 네트워크를 확인하고 다시 시도해 주세요.",
  PAY_PROCESSING: "토스에서 결제 결과를 확인 중이에요. 잠시 후 다시 시도해 주세요.",
  PAY_PROCESSING_RETRY: "결제 확인에 시간이 걸리고 있어요. 잠시 후 다시 시도해 주세요.",
  PAY_STATUS_NOT_DONE: "결제가 완료되지 않았어요. 잠시 후 다시 시도해 주세요.",
  INVALID_REQUEST: "결제 요청 정보가 올바르지 않아요. 입력 값을 다시 확인해 주세요.",
  EXCEED_LIMIT: "결제 한도를 초과했어요. 다른 결제 수단을 사용해 주세요.",
};

export default function TossPaymentFailPage() {
  return (
    <Suspense fallback={<PaymentStatusFallback />}>
      <TossPaymentFailPageInner />
    </Suspense>
  );
}

function PaymentStatusFallback() {
  return (
    <AppShell>
      <div className="flex h-[50vh] items-center justify-center text-slate-300">결제 상태를 확인하는 중입니다…</div>
    </AppShell>
  );
}

function TossPaymentFailPageInner() {
  const searchParams = useSearchParams();
  const pushToast = useToastStore((state) => state.show);
  const toastShownRef = useRef(false);

  const orderId = searchParams?.get("orderId") ?? null;
  const code = searchParams?.get("code") ?? null;
  const failureMessage = searchParams?.get("message") ?? null;
  const tierParam = searchParams?.get("tier") ?? null;
  const amountParam = searchParams?.get("amount") ?? null;
  const redirectPath = safeRedirectPath(searchParams?.get("redirectPath"));

  const amountLabel = useMemo(() => {
    const parsed = amountParam ? Number.parseInt(amountParam, 10) : NaN;
    if (!Number.isFinite(parsed)) {
      return "확인 불가";
    }
    return `${parsed.toLocaleString("ko-KR")}원`;
  }, [amountParam]);

  const tierLabel = useMemo(() => (isPlanTier(tierParam) ? planTierLabel(tierParam) : "미지정"), [tierParam]);

  const resolvedMessage = useMemo(() => {
    const trimmed = failureMessage?.trim();
    if (trimmed) {
      return trimmed;
    }
    if (code && TOSS_ERROR_MESSAGES[code]) {
      return TOSS_ERROR_MESSAGES[code];
    }
    if (code) {
      return `오류 코드(${code})로 결제가 중단됐어요. 관리자에게 문의해 주세요.`;
    }
    return "결제가 완료되지 않았어요. 다시 시도해 주세요.";
  }, [code, failureMessage]);

  const supportAction = useMemo(() => {
    const params = new URLSearchParams({
      subject: "Toss 결제 실패 문의",
      body: `orderId=${orderId ?? "미확인"}&code=${code ?? "N/A"}`,
    });
    return {
      label: "도움이 필요하신가요?",
      href: `mailto:support@kfinance.ai?${params.toString()}`,
      external: true,
    };
  }, [code, orderId]);

  useEffect(() => {
    logEvent("payments.checkout.redirect_fail", {
      orderId,
      code,
      message: resolvedMessage,
      tier: tierParam,
      amount: amountParam,
    });

    if (!toastShownRef.current) {
      toastShownRef.current = true;
      pushToast({
        id: `payments/fail/${orderId ?? "unknown"}`,
        title: "결제가 완료되지 않았어요",
        message: resolvedMessage,
        intent: "error",
      });
    }
  }, [amountParam, code, orderId, pushToast, resolvedMessage, tierParam]);

  const detailItems = useMemo(
    () => [
      { label: "주문 번호", value: orderId ?? "확인 불가" },
      { label: "요청 플랜", value: tierLabel, emphasize: true },
      { label: "결제 금액", value: amountLabel, emphasize: true },
      ...(code ? [{ label: "오류 코드", value: code }] : []),
    ],
    [amountLabel, code, orderId, tierLabel],
  );

  return (
    <AppShell>
      <div className="mx-auto max-w-xl space-y-6 py-10">
        <PaymentResultCard
          status="error"
          title="결제를 확인하지 못했어요"
          description={resolvedMessage}
          details={detailItems}
          actionHref={redirectPath}
          actionLabel="다시 결제 시도하기"
          secondaryAction={supportAction}
        />
      </div>
    </AppShell>
  );
}
