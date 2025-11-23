import type { PlanTier } from "@/store/planStore";
import { getPlanLabel } from "@/lib/planTier";

export type PlanCheckoutPreset = {
  amount: number;
  orderName: string;
};

/**
 * 샌드박스 결제 테스트 금액입니다. 실제 요금제가 확정되면 서버·환경 변수 기반으로 교체하세요.
 */
export const PLAN_CHECKOUT_PRESETS: Record<Exclude<PlanTier, "free">, PlanCheckoutPreset> = {
  starter: {
    amount: 9900,
    orderName: "Nuvien Starter 플랜 구독",
  },
  pro: {
    amount: 39000,
    orderName: "Nuvien Pro 플랜 구독",
  },
  enterprise: {
    amount: 185000,
    orderName: "Nuvien Team 플랜 구독",
  },
};

export const planTierLabel = (tier: PlanTier): string => getPlanLabel(tier);
