import type { Meta, StoryObj } from "@storybook/react";
import { PaymentResultCard } from "@/components/payments/PaymentResultCard";

const meta: Meta<typeof PaymentResultCard> = {
  title: "Payments/PaymentResultCard",
  component: PaymentResultCard,
  args: {
    actionHref: "/settings",
  },
};

export default meta;

type Story = StoryObj<typeof PaymentResultCard>;

export const Success: Story = {
  args: {
    status: "success",
    title: "결제가 완료됐어요",
    description: "관리자 플랜 정보가 곧 새로고침됩니다. 잠시 뒤 이전 페이지로 돌아가 다시 확인해 주세요.",
    details: [
      { label: "주문 번호", value: "kfinance-pro-12345" },
      { label: "결제 금액", value: "39,000원" },
      { label: "적용 플랜", value: "Pro" },
    ],
    actionLabel: "대시보드로 이동",
  },
};

export const Failure: Story = {
  args: {
    status: "error",
    title: "결제를 확인하지 못했어요",
    description: "사용자 취소로 결제가 완료되지 않았어요. 다시 시도하거나 관리자에게 문의해 주세요.",
    details: [
      { label: "주문 번호", value: "kfinance-pro-12345" },
      { label: "요청 플랜", value: "Pro" },
      { label: "결제 금액", value: "39,000원" },
      { label: "오류 코드", value: "USER_CANCEL" },
    ],
    actionLabel: "다시 시도하기",
  },
};
