"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { TossPaymentsInstance } from "@tosspayments/payment__types";
import { resolveApiBase } from "@/lib/apiBase";
import { loadTossPayments } from "@/lib/tossPayments";
import { logEvent } from "@/lib/telemetry";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
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

type CheckoutInitResponse = {
  orderId: string;
  planTier: PlanTier;
  amount: number;
  currency: string;
  orderName: string;
  successPath: string;
  failPath: string;
};

const buildUrl = (baseUrl: string | null | undefined, fallbackPath: string) => {
  const origin = typeof window !== "undefined" ? window.location.origin : "https://localhost";
  try {
    return new URL(baseUrl ?? fallbackPath, origin);
  } catch {
    return new URL(fallbackPath, origin);
  }
};

type ApiErrorDetail = {
  detail?: {
    message?: string;
  };
};

const readErrorDetail = async (response: Response): Promise<ApiErrorDetail | undefined> => {
  try {
    return (await response.json()) as ApiErrorDetail;
  } catch {
    return undefined;
  }
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
        const toss: TossPaymentsInstance = await loadTossPayments(config.clientKey);

        const preset = PLAN_CHECKOUT_PRESETS[targetTier];
        const currentPath =
          redirectPath ??
          (typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : "/settings");

        const baseUrl = resolveApiBase();
        const initResponse = await fetchWithAuth(`${baseUrl}/api/v1/payments/toss/checkout`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            planTier: targetTier,
            amount,
            orderName: orderName ?? preset.orderName,
            customerName,
            customerEmail,
            redirectPath: currentPath,
          }),
        });

        if (!initResponse.ok) {
          const detail = await readErrorDetail(initResponse);
          const message = detail?.detail?.message ?? "결제 준비 요청이 실패했어요. 잠시 후 다시 시도해 주세요.";
          throw new Error(message);
        }

        const checkout = (await initResponse.json()) as CheckoutInitResponse;

        const successUrl = buildUrl(config.successUrl, checkout.successPath);
        const failUrl = buildUrl(config.failUrl, checkout.failPath);

        logEvent("payments.checkout.request", {
          targetTier,
          amount: checkout.amount,
          orderId: checkout.orderId,
        });

        await toss.requestPayment("CARD", {
          amount: checkout.amount,
          orderId: checkout.orderId,
          orderName: checkout.orderName,
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
