/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-call */
"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { resolveApiBase } from "@/lib/apiBase";
import { loadTossPayments } from "@/lib/tossPayments";
import { logEvent } from "@/lib/telemetry";
import { useToastStore } from "@/store/toastStore";
import type { PlanTier } from "@/store/planStore";
import { planTierLabel, PLAN_CHECKOUT_PRESETS } from "@/constants/planPricing";

type TossPaymentsConfig = {
  clientKey: string;
  successUrl?: string | null;
  failUrl?: string | null;
};

type CheckoutOptions = {
  targetTier: Exclude<PlanTier, "free">;
  amount?: number;
  orderName?: string;
  customerName?: string;
  customerEmail?: string;
  redirectPath?: string;
};

const buildUrl = (baseUrl: string | null | undefined, fallbackPath: string) => {
  const origin = typeof window !== "undefined" ? window.location.origin : "https://localhost";
  try {
    return new URL(baseUrl ?? fallbackPath, origin);
  } catch {
    return new URL(fallbackPath, origin);
  }
};

const generateOrderId = (tier: PlanTier) => {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Date.now().toString();
  return `kfinance-${tier}-${random}`;
};

export const useTossCheckout = () => {
  const [isPreparing, setIsPreparing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const toast = useToastStore((state) => state.show);

  const configRef = useRef<TossPaymentsConfig | null>(null);

  const ensureConfig = useCallback(async (): Promise<TossPaymentsConfig> => {
    if (configRef.current) {
      return configRef.current;
    }

    const baseUrl = resolveApiBase();
    const response = await fetch(`${baseUrl}/api/v1/payments/toss/config`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("결제 구성을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    }

    const payload = (await response.json()) as TossPaymentsConfig;
    configRef.current = payload;
    return payload;
  }, []);

  const startCheckout = useCallback(
    async ({ targetTier, amount, orderName, customerName, customerEmail, redirectPath }: CheckoutOptions) => {
      setIsPreparing(true);
      setLastError(null);

      try {
        const config = await ensureConfig();
        const toss = await loadTossPayments(config.clientKey);

        const preset = PLAN_CHECKOUT_PRESETS[targetTier];
        const effectiveAmount = amount ?? preset.amount;
        const effectiveName = orderName ?? preset.orderName;

        if (!effectiveAmount || effectiveAmount <= 0) {
          throw new Error("테스트 결제 금액이 설정되지 않았어요. 관리자에게 문의해 주세요.");
        }

        const orderId = generateOrderId(targetTier);
        const currentPath =
          redirectPath ??
          (typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/settings");

        const successUrl = buildUrl(config.successUrl, "/payments/success");
        successUrl.searchParams.set("orderId", orderId);
        successUrl.searchParams.set("tier", targetTier);
        successUrl.searchParams.set("amount", String(effectiveAmount));
        successUrl.searchParams.set("redirectPath", currentPath);

        const failUrl = buildUrl(config.failUrl, "/payments/fail");
        failUrl.searchParams.set("orderId", orderId);
        failUrl.searchParams.set("tier", targetTier);
        failUrl.searchParams.set("amount", String(effectiveAmount));
        failUrl.searchParams.set("redirectPath", currentPath);

        logEvent("payments.checkout.request", {
          targetTier,
          amount: effectiveAmount,
        });

        await toss.requestPayment("CARD", {
          amount: effectiveAmount,
          orderId,
          orderName: effectiveName,
          customerName: customerName ?? undefined,
          customerEmail: customerEmail ?? undefined,
          successUrl: successUrl.toString(),
          failUrl: failUrl.toString(),
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "결제 창을 열지 못했어요. 잠시 후 다시 시도해 주세요.";
        setLastError(message);
        toast({
          id: "payments/checkout-error",
          title: "결제 준비 중 오류가 발생했어요",
          message,
          intent: "error",
        });
        logEvent("payments.checkout.error", {
          targetTier,
          amount,
          message,
        });
        throw error;
      } finally {
        setIsPreparing(false);
      }
    },
    [ensureConfig, toast],
  );

  const helpers = useMemo(
    () => ({
      isPreparing,
      lastError,
      startCheckout,
      getPreset: (tier: PlanTier) => PLAN_CHECKOUT_PRESETS[tier as Exclude<PlanTier, "free">] ?? null,
      getTierLabel: (tier: PlanTier) => planTierLabel(tier),
    }),
    [isPreparing, lastError, startCheckout],
  );

  return helpers;
};
