import type { PlanTier } from "@/store/planStore/types";

export type PlanTierAction = {
  label: string;
  action?: "upgrade" | "contact" | "link";
  href?: string;
  tier?: PlanTier;
  target?: "_blank" | "_self";
};

export type PlanTierCopy = {
  title: string;
  tagline: string;
  description?: string | null;
  badge?: string | null;
  features: string[];
  supportNote?: string | null;
  primaryAction: PlanTierAction;
  secondaryAction?: PlanTierAction;
};

export const PLAN_TIERS: PlanTier[] = ["free", "starter", "pro", "enterprise"];

const CONTACT_PATH = "/contact?plan=enterprise";

export const PLAN_TIER_CONFIG: Record<PlanTier, PlanTierCopy> = {
  free: {
    title: "Free",
    tagline: "처음 만나는 분들이 부담 없이 둘러볼 수 있는 체험 플랜이에요.",
    description: "워치리스트와 AI 리서치를 가볍게 시작할 때 적합합니다.",
    badge: "Free",
    features: [
      "AI를 통한 공시 분석",
      "공시·뉴스·요약 기본 피드 열람",
      "감성 지표와 리포트 샘플 미리 보기",
      "간단한 PDF 다운로드 및 공유",
    ],
    supportNote: undefined,
    primaryAction: {
      label: "플랜 비교 보기",
      action: "link",
      href: "/pricing",
    },
  },
  starter: {
    title: "Starter",
    tagline: "워치리스트·RAG 자동화를 가볍게 묶은 경량 유료 플랜이에요.",
    description: "소규모 팀이 매일 반복되는 리서치를 자동화할 때 적합합니다.",
    badge: "Starter",
    features: [
      "워치리스트 50 · 알림 룰 10개",
      "하루 80회 RAG 질문과 청구 링크",
      "PDF 하이라이트 · 요약 스니펫 저장",
      "Starter 30일 Pro 체험 쿠폰 포함",
    ],
    supportNote: undefined,
    primaryAction: {
      label: "Starter 업그레이드",
      action: "upgrade",
      tier: "starter",
    },
    secondaryAction: {
      label: "플랜 비교 보기",
      action: "link",
      href: "/pricing",
    },
  },
  pro: {
    title: "Pro",
    tagline: "팻 단위로 본격 자동화를 키우는 플랜이에요.",
    description: "확장된 AI 대화와 자동화된 리포트를 바로 적용할 수 있습니다.",
    badge: "Best",
    features: [
      "확장된 AI 대화 기능",
      "워치리스트 자동 알림(Slack/Email)",
      "기업 비교 검색과 인라인 PDF 뷰어",
      "Event Study 리포트를 PDF·ZIP으로 내려받기",
      "맞춤 다이제스트와 운용 리포트 자동 발송",
    ],
    supportNote: undefined,
    primaryAction: {
      label: "Pro 업그레이드",
      action: "upgrade",
      tier: "pro",
    },
    secondaryAction: {
      label: "엔터프라이즈 문의",
      action: "contact",
      href: CONTACT_PATH,
    },
  },
  enterprise: {
    title: "Team",
    tagline: "팀 협업과 보안 요구를 충족하는 조직용 패키지예요.",
    description: "팀 채팅·워크스페이스·보안/감사 요구사항이 있는 조직에 적합합니다.",
    badge: "Team",
    features: ["팀 워크스페이스와 RBAC", "감사 로그 및 보안 점검 지원", "Slack/Email/웹훅 실시간 통합", "팀 온보딩·지원 채널"],
    supportNote: "보안/감사 준비가 필요하다면 전담 지원 채널로 도와드려요.",
    primaryAction: {
      label: "팀 플랜 문의",
      action: "contact",
      href: CONTACT_PATH,
    },
    secondaryAction: {
      label: "도입 상담 일정 예약",
      action: "link",
      href: CONTACT_PATH,
    },
  },
};

export const getPlanTierConfig = (tier: PlanTier): PlanTierCopy => PLAN_TIER_CONFIG[tier];
