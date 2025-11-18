"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { AppShell } from "@/components/layout/AppShell";
import { useToastStore } from "@/store/toastStore";
import { useOnboardingStore } from "@/store/onboardingStore";
import { useOnboardingWizardStore } from "@/store/onboardingWizardStore";
import { planTierLabel } from "@/constants/planPricing";
import { resolveApiBase } from "@/lib/apiBase";
import { fetchWithAuth } from "@/lib/fetchWithAuth";
import type { PlanTier } from "@/store/planStore";

type CheckoutResult = {
  orderId: string;
  successPath: string;
  failPath: string;
  planTier: PlanTier;
  amount: number;
};

const STEP_CLASSES =
  "rounded-xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark";

export default function OnboardingWizardPage() {
  const wizard = useOnboardingWizardStore();
  const onboardingStore = useOnboardingStore();
  const toast = useToastStore((state) => state.show);
  const router = useRouter();
  const { update } = useSession();
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [inviteInput, setInviteInput] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [checkoutResult, setCheckoutResult] = useState<CheckoutResult | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [completionLoading, setCompletionLoading] = useState(false);
  const [slugStatus, setSlugStatus] = useState<"idle" | "checking" | "available" | "taken" | "error">("idle");
  const [slugHint, setSlugHint] = useState("슬러그를 입력하지 않으면 자동으로 생성됩니다.");
  const [checkingPayment, setCheckingPayment] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  useEffect(() => {
    if (!wizard.state && !wizard.loading) {
      void wizard.fetchState().catch((error) => {
        toast({ id: "onboarding/state", title: "온보딩 상태를 불러오지 못했습니다.", message: String(error), intent: "error" });
      });
    }
  }, [toast, wizard]);

  useEffect(() => {
    if (wizard.state?.org) {
      setOrgName(wizard.state.org.name);
      setOrgSlug(wizard.state.org.slug ?? "");
    }
  }, [wizard.state?.org]);

  useEffect(() => {
    const trimmed = orgSlug.trim();
    if (!trimmed) {
      setSlugStatus("idle");
      setSlugHint("슬러그를 입력하지 않으면 자동으로 생성됩니다.");
      return;
    }
    setSlugStatus("checking");
    setSlugHint("슬러그 사용 가능 여부를 확인하는 중입니다…");
    const handle = window.setTimeout(() => {
      void wizard
        .checkSlug(trimmed)
        .then((available) => {
          setSlugStatus(available ? "available" : "taken");
          setSlugHint(available ? "사용 가능한 슬러그입니다." : "이미 사용 중인 슬러그입니다.");
        })
        .catch(() => {
          setSlugStatus("error");
          setSlugHint("슬러그 상태를 확인할 수 없습니다.");
        });
    }, 400);
    return () => window.clearTimeout(handle);
  }, [orgSlug, wizard]);

  const wizardState = wizard.state;

  const sortedPlanOptions = useMemo(() => {
    if (!wizardState) {
      return [];
    }
    const order: PlanTier[] = ["free", "starter", "pro", "enterprise"];
    const map = new Map<PlanTier, typeof wizardState.planOptions[number]>();
    wizardState.planOptions.forEach((option) => {
      map.set(option.tier, option);
    });
    return order
      .map((tier) => map.get(tier))
      .filter(Boolean)
      .map((option) => option!);
  }, [wizardState]);

  const handleSaveOrg = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!orgName.trim()) {
      toast({ id: "onboarding/org", title: "조직 이름을 입력해주세요.", intent: "error" });
      return;
    }
    try {
      const org = await wizard.updateOrg({ name: orgName.trim(), slug: orgSlug || undefined });
      await update?.({ orgId: org.id });
      toast({ id: "onboarding/org/saved", title: "조직 정보가 저장되었습니다.", intent: "success" });
    } catch (error) {
      toast({
        id: "onboarding/org/error",
        title: "조직 정보를 저장하지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    }
  };

  const handleInviteSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!wizard.state?.org) {
      return;
    }
    const emails = inviteInput
      .split(/[,;\s]+/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (emails.length === 0) {
      toast({ id: "onboarding/invite/empty", title: "초대할 이메일을 입력해주세요.", intent: "error" });
      return;
    }
    try {
      const members = await wizard.inviteMembers({
        orgId: wizard.state.org.id,
        invites: emails.map((email) => ({ email, role: inviteRole })),
      });
      setInviteInput("");
      toast({
        id: "onboarding/invite/success",
        title: `${emails.length}명의 구성원을 초대했습니다.`,
        message: `현재 ${members.length}명이 워크스페이스에 있습니다.`,
        intent: "success",
      });
    } catch (error) {
      toast({
        id: "onboarding/invite/error",
        title: "구성원 초대에 실패했습니다.",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    }
  };

  const handlePlanSelect = async (tier: PlanTier) => {
    if (!wizard.state?.org) {
      return;
    }
    try {
      await wizard.selectPlan({ orgId: wizard.state.org.id, planTier: tier });
      toast({
        id: `onboarding/plan/${tier}`,
        title: `${planTierLabel(tier)} 플랜이 선택되었습니다.`,
        intent: "success",
      });
    } catch (error) {
      toast({
        id: `onboarding/plan/${tier}/error`,
        title: "플랜을 변경하지 못했습니다.",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    }
  };

  const handleCheckout = useCallback(async () => {
    if (!wizard.state?.org) {
      return;
    }
    setCheckoutLoading(true);
    try {
      const response = await fetchWithAuth(`${resolveApiBase()}/api/v1/payments/toss/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Org-Id": wizard.state.org.id,
        },
        body: JSON.stringify({
          planTier: wizard.state.org.planTier,
          redirectPath: "/settings",
        }),
      });
      if (!response.ok) {
        throw new Error("결제 주문을 생성하지 못했습니다.");
      }
      const payload = (await response.json()) as {
        orderId: string;
        successPath: string;
        failPath: string;
        planTier: PlanTier;
        amount: number;
      };
      const checkout = {
        orderId: payload.orderId,
        successPath: payload.successPath,
        failPath: payload.failPath,
        planTier: payload.planTier,
        amount: payload.amount,
      };
      setCheckoutResult(checkout);
      setPaymentStatus(null);
      setPaymentError(null);
      toast({ id: "onboarding/checkout", title: "토스 결제 주문이 생성되었습니다.", intent: "success" });
    } catch (error) {
      toast({
        id: "onboarding/checkout/error",
        title: "결제 주문 생성에 실패했습니다.",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    } finally {
      setCheckoutLoading(false);
    }
  }, [toast, wizard.state?.org]);

  const handleVerifyPayment = useCallback(async () => {
    if (!checkoutResult) {
      return;
    }
    setCheckingPayment(true);
    setPaymentError(null);
    try {
      const response = await fetchWithAuth(`${resolveApiBase()}/api/v1/payments/toss/orders/${checkoutResult.orderId}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error("주문 상태를 확인하지 못했습니다.");
      }
      const payload = await response.json();
      const status = String(payload.status || "").toLowerCase();
      setPaymentStatus(status);
      if (status === "confirmed" || status === "paid") {
        toast({ id: "onboarding/payment/confirmed", title: "결제가 확인되었습니다.", intent: "success" });
        await wizard.fetchState();
      } else {
        toast({
          id: "onboarding/payment/pending",
          title: "결제가 아직 완료되지 않았습니다.",
          message: `현재 상태: ${payload.status}`,
          intent: "info",
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "결제 상태 조회 중 문제가 발생했습니다.";
      setPaymentError(message);
      toast({ id: "onboarding/payment/error", title: "결제 상태 확인 실패", message, intent: "error" });
    } finally {
      setCheckingPayment(false);
    }
  }, [checkoutResult, toast, wizard]);

  const handleComplete = async () => {
    if (completionLoading) {
      return;
    }
    setCompletionLoading(true);
    try {
      await onboardingStore.completeOnboarding([]);
      await update?.({ onboardingRequired: false });
      toast({ id: "onboarding/completed", title: "온보딩이 완료되었습니다.", intent: "success" });
      router.push("/");
    } catch (error) {
      toast({
        id: "onboarding/complete/error",
        title: "온보딩 완료 처리에 실패했습니다.",
        message: error instanceof Error ? error.message : undefined,
        intent: "error",
      });
    } finally {
      setCompletionLoading(false);
    }
  };

  if (wizard.loading && !wizard.state) {
    return (
      <AppShell>
        <div className="flex min-h-[60vh] items-center justify-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          온보딩 상태를 불러오는 중입니다...
        </div>
      </AppShell>
    );
  }

  if (wizard.error && !wizard.state) {
    return (
      <AppShell>
        <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-4 text-center">
          <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
            온보딩 상태를 불러오지 못했습니다.
          </p>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{wizard.error}</p>
          <button
            type="button"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
            onClick={() => wizard.fetchState().catch(() => undefined)}
          >
            다시 시도하기
          </button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <header>
          <h1 className="text-2xl font-bold text-text-primaryLight dark:text-text-primaryDark">워크스페이스 온보딩</h1>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            조직 정보 설정 → 구성원 초대 → 플랜 선택 → 결제 순으로 진행해 주세요.
          </p>
        </header>

        <section className={STEP_CLASSES}>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">1. 조직 정보</h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            워크스페이스 이름과 슬러그(URL)를 입력하면 구성원과 공유할 수 있어요.
          </p>
          <form className="mt-4 space-y-4" onSubmit={handleSaveOrg}>
            <div>
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">이름</label>
              <input
                type="text"
                className="mt-1 w-full rounded-lg border border-border-light px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark"
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                슬러그 (선택)
              </label>
              <input
                type="text"
                className="mt-1 w-full rounded-lg border border-border-light px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark"
                value={orgSlug}
                onChange={(event) => setOrgSlug(event.target.value)}
                placeholder="예: research-team"
              />
              <p
                className={`mt-1 text-xs ${
                  slugStatus === "available"
                    ? "text-emerald-500"
                    : slugStatus === "taken" || slugStatus === "error"
                    ? "text-amber-500"
                    : "text-text-tertiaryLight dark:text-text-tertiaryDark"
                }`}
              >
                {slugHint}
              </p>
            </div>
            <button
              type="submit"
              className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
            >
              조직 정보 저장
            </button>
          </form>
        </section>

        <section className={STEP_CLASSES}>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">2. 구성원 초대</h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            이메일을 쉼표 또는 줄바꿈으로 구분해 입력하면 초대 링크가 전송됩니다.
          </p>
          <form className="mt-4 space-y-4" onSubmit={handleInviteSubmit}>
            <textarea
              className="min-h-[120px] w-full rounded-lg border border-border-light px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark"
              value={inviteInput}
              onChange={(event) => setInviteInput(event.target.value)}
              placeholder="alice@example.com, bob@example.com"
            />
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
                역할 선택
              </label>
              <select
                className="rounded-lg border border-border-light px-3 py-2 text-sm focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-dark"
                value={inviteRole}
                onChange={(event) => setInviteRole(event.target.value)}
              >
                <option value="viewer">Viewer</option>
                <option value="editor">Editor</option>
                <option value="admin">Admin</option>
              </select>
              <span className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">
                선택한 역할이 입력된 모든 이메일에 적용됩니다.
              </span>
            </div>
            <button
              type="submit"
              className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 dark:border-border-dark dark:text-text-primaryDark dark:hover:bg-border-dark/40"
            >
              초대 링크 보내기
            </button>
          </form>
          <div className="mt-4 rounded-lg bg-background-light/60 p-3 text-sm text-text-secondaryLight dark:bg-background-dark/50 dark:text-text-secondaryDark">
            현재 구성원 수: <span className="font-semibold">{wizard.state?.org.memberCount ?? 0}명</span>
          </div>
        </section>

        <section className={STEP_CLASSES}>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">3. 플랜 선택</h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            원하는 플랜을 선택하면 세부 기능과 요금이 적용됩니다.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {sortedPlanOptions.map((option) => {
              const isActive = wizard.state?.org.planTier === option.tier;
              return (
                <button
                  key={option.tier}
                  type="button"
                  onClick={() => handlePlanSelect(option.tier)}
                  className={`flex h-full flex-col rounded-xl border px-4 py-3 text-left transition hover:border-primary ${
                    isActive
                      ? "border-primary shadow-lg shadow-primary/10 dark:border-primary.dark"
                      : "border-border-light dark:border-border-dark"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-base font-semibold text-text-primaryLight dark:text-text-primaryDark">
                        {option.title}
                      </p>
                      <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{option.tagline}</p>
                    </div>
                    {isActive ? (
                      <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                        선택됨
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-3 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                    {(option.features ?? []).slice(0, 3).map((feature) => (
                      <p key={`${option.tier}-${feature}`}>• {feature}</p>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className={STEP_CLASSES}>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">4. 결제 및 완료</h2>
          <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            유료 플랜을 선택한 경우 토스 결제 주문을 생성한 뒤 완료해 주세요.
          </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 disabled:opacity-60 dark:border-border-dark dark:text-text-primaryDark"
            onClick={handleCheckout}
            disabled={checkoutLoading}
          >
            {checkoutLoading ? "결제 주문 생성 중..." : "토스 결제 주문 생성"}
          </button>
          {checkoutResult ? (
            <button
              type="button"
              className="rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-primaryLight transition hover:bg-border-light/40 disabled:opacity-60 dark:border-border-dark dark:text-text-primaryDark"
              onClick={handleVerifyPayment}
              disabled={checkingPayment}
            >
              {checkingPayment ? "결제 상태 확인 중..." : "결제 완료 확인"}
            </button>
          ) : null}
          <button
            type="button"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90 disabled:opacity-60"
            onClick={handleComplete}
            disabled={completionLoading}
          >
            {completionLoading ? "처리 중..." : "온보딩 완료"}
          </button>
        </div>
          {checkoutResult ? (
            <div className="mt-4 rounded-lg bg-background-light/70 p-4 text-sm text-text-secondaryLight dark:bg-background-dark/60 dark:text-text-secondaryDark">
              <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">최근 생성된 주문</p>
              <p className="mt-1">주문 번호: {checkoutResult.orderId}</p>
              <p>플랜: {planTierLabel(checkoutResult.planTier)}</p>
              <p>금액: {checkoutResult.amount.toLocaleString("ko-KR")}원</p>
          <div className="mt-2 flex gap-3 text-xs">
            <a href={checkoutResult.successPath} className="text-primary hover:underline">
              성공 URL
            </a>
            <a href={checkoutResult.failPath} className="text-primary hover:underline">
              실패 URL
            </a>
          </div>
          {paymentStatus ? (
            <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              최근 확인된 결제 상태: <span className="font-semibold">{paymentStatus}</span>
            </p>
          ) : null}
          {paymentError ? (
            <p className="mt-1 text-xs text-amber-500">
              {paymentError}
            </p>
          ) : null}
        </div>
      ) : null}
        </section>
      </div>
    </AppShell>
  );
}
