"use client";

import entitlementLabelData from "@/data/plan/entitlementLabels.json";
import type { PlanTier } from "@/store/planStore/types";

export const PLAN_DESCRIPTIONS: Record<PlanTier, string> = {
  free: "처음 만나는 분들이 부담 없이 둘러볼 수 있는 체험 플랜이에요.",
  starter: "워치리스트·RAG 자동화를 가볍게 묶은 경량 유료 플랜이에요.",
  pro: "팀 동료들과 자동화를 키우는 플랜이에요. 이메일·웹훅 채널이 바로 열려요.",
  enterprise: "전용 파트너와 아낌없이 협업하는 플랜이에요. 모든 채널과 맞춤 한도를 함께 드려요.",
};

export const PLAN_TIER_LABELS: Record<PlanTier, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

export const PLAN_ENTITLEMENT_LABELS: Record<string, string> = entitlementLabelData;

