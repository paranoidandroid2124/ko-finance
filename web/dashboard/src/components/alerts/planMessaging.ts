import type { PlanTier } from "@/store/planStore";

type AlertPlanTier = PlanTier | "free" | "pro" | "enterprise";

type QuotaInfo = {
  remaining: number;
  max: number;
};

type PlanLockCopy = {
  requiredTier: PlanTier;
  title: string;
  description: string;
};

type QuotaFormatter = (info: QuotaInfo) => string;

type BuilderCopy = {
  disabledTooltip: string;
  disabledHint: string;
  quotaToast: {
    title: string;
    description: QuotaFormatter;
  };
  quotaBanner: QuotaFormatter;
  lock?: PlanLockCopy;
};

type BellCopy = {
  disabledTooltip: string;
  disabledHint: string;
  quotaToast: {
    title: string;
    description: QuotaFormatter;
  };
};

type PlanCopy = {
  builder: BuilderCopy;
  bell: BellCopy;
};

const formatLimitDescription = (info: QuotaInfo, whenLimited: string, whenUnlimited: string): string => {
  if (info.max <= 0) {
    return whenUnlimited;
  }
  return whenLimited
    .replace('{max}', info.max.toLocaleString('ko-KR'))
    .replace('{remaining}', Math.max(info.remaining, 0).toLocaleString('ko-KR'));
};

const PLAN_COPY: Record<AlertPlanTier, PlanCopy> = {
  free: {
    builder: {
      disabledTooltip: 'Pro 플랜에서 새로운 알림을 만들 수 있어요.',
      disabledHint: 'Pro로 업그레이드하면 이메일·Slack·Webhook 등 추가 채널과 더 많은 슬롯이 열립니다.',
      quotaToast: {
        title: '알림 슬롯이 없습니다',
        description: (info) =>
          formatLimitDescription(
            info,
            'Free 플랜에서는 최대 {max}개의 알림만 만들 수 있어요. 기존 알림을 비활성화하거나 Pro로 업그레이드해 주세요.',
            'Free 플랜 한도를 모두 사용했습니다. 업그레이드 후 다시 시도해 주세요.'
          ),
      },
      quotaBanner: (info) =>
        formatLimitDescription(
          info,
          'Free 플랜 한도 {max}개를 모두 사용했습니다. Pro 플랜으로 업그레이드하면 더 많은 알림을 설정할 수 있어요.',
          'Free 플랜 한도를 모두 사용했습니다. 업그레이드하면 제한이 해제됩니다.'
        ),
      lock: {
        requiredTier: 'pro',
        title: 'Pro 플랜에서 사용할 수 있는 기능이에요',
        description: 'Free 플랜에서는 알림 자동화를 미리보기로만 제공합니다. Pro로 업그레이드하고 이메일·Slack 등 원하는 채널로 즉시 보내 보세요.',
      },
    },
    bell: {
      disabledTooltip: 'Pro 플랜으로 업그레이드하면 새로운 알림을 만들 수 있어요.',
      disabledHint: 'Pro 이상에서 이메일, Slack, Webhook 채널과 추가 슬롯이 제공됩니다.',
      quotaToast: {
        title: '알림 한도를 모두 사용했습니다',
        description: (info) =>
          formatLimitDescription(
            info,
            'Free 플랜에서는 최대 {max}개의 알림만 유지할 수 있어요. 기존 알림을 정리하거나 업그레이드해 주세요.',
            'Free 플랜에서는 추가 알림을 만들 수 없어요. 플랜을 업그레이드해 주세요.'
          ),
      },
    },
  },
  pro: {
    builder: {
      disabledTooltip: '남은 알림 슬롯이 없습니다.',
      disabledHint: '사용 중인 슬롯을 정리하거나 Enterprise로 확장하면 Webhook 등의 채널을 계속 사용할 수 있어요.',
      quotaToast: {
        title: '알림 한도를 초과했습니다',
        description: (info) =>
          formatLimitDescription(
            info,
            'Pro 플랜 알림 한도 {max}개를 모두 사용했습니다. 기존 규칙을 정리하거나 Enterprise로 업그레이드해 주세요.',
            '알림 슬롯을 비워야 새 규칙을 만들 수 있어요.'
          ),
      },
      quotaBanner: (info) =>
        formatLimitDescription(
          info,
          'Pro 플랜 한도 {max}개를 모두 사용했습니다. Enterprise로 확장하면 무제한으로 관리할 수 있어요.',
          '프로 플랜 한도를 모두 사용했습니다. 슬롯을 비우거나 플랜을 확장해 주세요.'
        ),
    },
    bell: {
      disabledTooltip: '남은 알림 슬롯이 없습니다.',
      disabledHint: '사용하지 않는 알림을 비활성화하거나 Enterprise 플랜으로 확장해 주세요.',
      quotaToast: {
        title: '알림 한도를 넘었어요',
        description: (info) =>
          formatLimitDescription(
            info,
            'Pro 플랜 한도 {max}개를 모두 사용했습니다. 기존 알림을 정리하거나 Enterprise로 확장해 주세요.',
            '알림 슬롯이 가득 찼습니다. Enterprise 플랜으로 확장하면 무제한으로 이용할 수 있어요.'
          ),
      },
    },
  },
  enterprise: {
    builder: {
      disabledTooltip: '남은 알림 슬롯을 확인해 주세요.',
      disabledHint: 'Enterprise 플랜은 무제한 알림을 지원합니다. 문제 발생 시 관리자에게 문의해 주세요.',
      quotaToast: {
        title: '알림 한도를 초과했습니다',
        description: (info) =>
          formatLimitDescription(
            info,
            'Enterprise 플랜 한도 {max}개를 모두 사용했습니다. 슬롯을 정리하거나 지원팀에 확장을 요청해 주세요.',
            'Enterprise 플랜은 무제한 알림을 지원합니다. 필요한 채널을 자유롭게 추가하세요.',
          ),
      },
      quotaBanner: (info) =>
        formatLimitDescription(
          info,
          'Enterprise 플랜 한도 {max}개를 모두 사용했습니다. 슬롯을 정리하거나 지원팀에 확장을 요청해 주세요.',
          'Enterprise 플랜은 무제한 알림을 지원합니다. 필요한 채널을 자유롭게 추가하세요.',
        ),
    },
    bell: {
      disabledTooltip: '남은 알림 슬롯을 확인해 주세요.',
      disabledHint: '슬롯을 정리하거나 지원팀에 확장을 요청해 주세요.',
      quotaToast: {
        title: '알림 한도를 초과했습니다',
        description: (info) =>
          formatLimitDescription(
            info,
            'Enterprise 플랜 한도 {max}개를 모두 사용했습니다. 슬롯을 정리하거나 지원팀에 확장을 요청해 주세요.',
            'Enterprise 플랜은 무제한 알림을 지원합니다. 필요한 채널을 자유롭게 추가하세요.',
          ),
      },
    },
  },
};

export const UNKNOWN_PLAN_COPY: PlanCopy = {
  builder: {
    disabledTooltip: '플랜 정보를 불러오지 못했어요.',
    disabledHint: '페이지를 새로고침하거나 관리자에게 문의해 주세요.',
    quotaToast: {
      title: '알림을 만들 수 없습니다',
      description: () => '플랜 정보를 불러오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.',
    },
    quotaBanner: () => '플랜 정보를 확인하지 못했습니다. 새로고침 후 다시 시도해 주세요.',
  },
  bell: {
    disabledTooltip: '플랜 정보를 불러오지 못했어요.',
    disabledHint: '새로고침 후 다시 시도하거나 관리자에게 문의해 주세요.',
    quotaToast: {
      title: '알림을 만들 수 없습니다',
      description: () => '플랜 정보를 불러오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.',
    },
  },
};

export const parsePlanTier = (value?: string | null): AlertPlanTier => {
  if (value === 'enterprise') {
    return 'enterprise';
  }
  if (value === 'pro') {
    return 'pro';
  }
  return 'free';
};

export const getPlanCopy = (tier: AlertPlanTier): PlanCopy => {
  return PLAN_COPY[tier] ?? PLAN_COPY.free;
};
