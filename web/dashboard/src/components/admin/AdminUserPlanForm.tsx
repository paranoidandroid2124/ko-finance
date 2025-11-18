"use client";

import { useState } from "react";

import { useUpdateUserPlanTier } from "@/hooks/useAdminQuickActions";
import { useToastStore } from "@/store/toastStore";
import type { PlanTier } from "@/store/planStore";
import { PLAN_TIERS } from "@/config/planConfig";
import { getPlanLabel } from "@/lib/planTier";

type AdminUserPlanFormProps = {
  className?: string;
};

export function AdminUserPlanForm({ className }: AdminUserPlanFormProps) {
  const [email, setEmail] = useState("");
  const [planTier, setPlanTier] = useState<PlanTier>("pro");
  const [note, setNote] = useState("");
  const updateUserPlan = useUpdateUserPlanTier();
  const showToast = useToastStore((state) => state.show);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email.trim()) {
      return;
    }
    try {
      const result = await updateUserPlan.mutateAsync({
        email: email.trim(),
        planTier,
        note: note.trim() || undefined,
      });
      showToast({
        intent: "success",
        title: "사용자 플랜을 업데이트했어요",
        message: `${result.email} → ${getPlanLabel(result.planTier)}`,
      });
      setEmail("");
      setNote("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "플랜을 변경하지 못했습니다.";
      showToast({
        intent: "error",
        title: "플랜 변경 실패",
        message,
      });
    }
  };

  return (
    <section
      className={`rounded-3xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark ${className ?? ""}`}
    >
      <header className="space-y-2">
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">사용자 플랜 수동 변경</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          결제/프로모션 예외 케이스에서 특정 사용자의 기본 플랜 티어를 직접 덮어쓸 수 있습니다. 감사 로그에 기록되므로
          사유를 남겨 주세요.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <label className="flex flex-col gap-2 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
          사용자 이메일
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="user@company.com"
            className="rounded-2xl border border-border-light bg-background-base px-4 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
          />
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
          적용할 플랜
          <select
            value={planTier}
            onChange={(event) => setPlanTier(event.target.value as PlanTier)}
            className="rounded-2xl border border-border-light bg-background-base px-4 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
          >
            {PLAN_TIERS.map((tier) => (
              <option key={tier} value={tier}>
                {getPlanLabel(tier)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
          메모 (선택)
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            placeholder="변경 사유를 입력하면 감사 로그에 함께 저장됩니다."
            className="rounded-2xl border border-border-light bg-background-base px-4 py-2 text-sm text-text-primaryLight outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-baseDark dark:text-text-primaryDark"
          />
        </label>

        <button
          type="submit"
          disabled={updateUserPlan.isPending || !email.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {updateUserPlan.isPending ? "업데이트 중..." : "플랜 변경"}
        </button>
      </form>
    </section>
  );
}
