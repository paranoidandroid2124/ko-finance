import { expect, test, type Page, type Route } from "@playwright/test";

type PlanTier = "free" | "starter" | "pro" | "enterprise";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL ?? "http://localhost:3000";
const SUCCESS_ORDER_ID = "kfinance-enterprise-e2e";
const FAIL_ORDER_ID = "kfinance-pro-fail";
const SUCCESS_AMOUNT = 185000;
const PRO_AMOUNT = 39000;

type PlanState = {
  tier: PlanTier;
  checkoutRequested: boolean;
};

const PRO_ENTITLEMENTS = [
  "search.compare",
  "search.alerts",
  "search.export",
  "evidence.inline_pdf",
  "rag.core",
  "reports.event_export",
];
const ENTERPRISE_ENTITLEMENTS = [
  "search.compare",
  "search.alerts",
  "search.export",
  "evidence.inline_pdf",
  "evidence.diff",
  "rag.core",
  "timeline.full",
  "reports.event_export",
];

const PLAN_FEATURE_FLAGS = (entitlements: string[]) => ({
  searchCompare: entitlements.includes("search.compare"),
  searchAlerts: entitlements.includes("search.alerts"),
  searchExport: entitlements.includes("search.export"),
  ragCore: entitlements.includes("rag.core"),
  evidenceInlinePdf: entitlements.includes("evidence.inline_pdf"),
  evidenceDiff: entitlements.includes("evidence.diff"),
  timelineFull: entitlements.includes("timeline.full"),
  reportsEventExport: entitlements.includes("reports.event_export"),
});

const PRO_QUOTA = {
  chatRequestsPerDay: 500,
  ragTopK: 6,
  selfCheckEnabled: true,
  peerExportRowLimit: 120,
};

const ENTERPRISE_QUOTA = {
  chatRequestsPerDay: null,
  ragTopK: 10,
  selfCheckEnabled: true,
  peerExportRowLimit: null,
};

const buildPlanPayload = (state: PlanState) => {
  const entitlements = state.tier === "enterprise" ? ENTERPRISE_ENTITLEMENTS : PRO_ENTITLEMENTS;
  const quota = state.tier === "enterprise" ? ENTERPRISE_QUOTA : PRO_QUOTA;

  return {
    planTier: state.tier,
    expiresAt: "2026-12-31T00:00:00+00:00",
    entitlements,
    featureFlags: PLAN_FEATURE_FLAGS(entitlements),
    quota,
    updatedAt: "2025-10-30T00:00:00+00:00",
    updatedBy: "qa@kfinance.ai",
    changeNote: state.tier === "enterprise" ? "Toss 업그레이드 적용" : "Playwright QA preset",
    checkoutRequested: state.checkoutRequested,
  };
};

const stubJson = async (route: Route, payload: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
};

const setupApiMocks = async (page: Page, planState: PlanState) => {
  await page.route("**/api/v1/plan/context", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await stubJson(route, buildPlanPayload(planState));
      return;
    }

    if (method === "PATCH") {
      try {
        const body = JSON.parse(route.request().postData() ?? "{}") as {
          planTier?: PlanTier;
          triggerCheckout?: boolean;
        };
        if (body.planTier) {
          planState.tier = body.planTier;
        }
        planState.checkoutRequested = Boolean(body.triggerCheckout);
      } catch {
        // ignore malformed payloads in tests
      }
      await stubJson(route, buildPlanPayload(planState));
      return;
    }

    await stubJson(route, buildPlanPayload(planState));
  });

  await page.route("**/api/v1/alerts", async (route) => {
    await stubJson(route, {
      items: [],
      plan: {
        planTier: planState.tier,
        maxAlerts: planState.tier === "enterprise" ? 999 : 5,
        remainingAlerts: planState.tier === "enterprise" ? 999 : 5,
        channels: ["email", "slack"],
        maxDailyTriggers: null,
        defaultEvaluationIntervalMinutes: 15,
        defaultWindowMinutes: 30,
        defaultCooldownMinutes: 30,
        minEvaluationIntervalMinutes: 5,
        minCooldownMinutes: 5,
        nextEvaluationAt: null,
      },
    });
  });

  await page.route("**/api/v1/alerts/channels/schema", async (route) => {
    await stubJson(route, { channels: [] });
  });

  await page.route("**/api/v1/payments/toss/config", async (route) => {
    await stubJson(route, {
      clientKey: "mock-client-key",
      successUrl: null,
      failUrl: null,
    });
  });

  await page.route("**/api/v1/payments/toss/webhook", async (route) => {
    await stubJson(route, { status: "accepted" }, 202);
  });
};

test.describe("Toss 결제 플로우", () => {
  test("플랜 업그레이드 성공 시 Enterprise로 전환된다", async ({ page }) => {
    const planState: PlanState = { tier: "pro", checkoutRequested: false };

    await setupApiMocks(page, planState);

    const confirmResponses: Array<{ orderId: string; amount: number }> = [];

    await page.route("**/api/v1/payments/toss/confirm", async (route) => {
      const payload = JSON.parse(route.request().postData() ?? "{}") as {
        orderId?: string;
        amount?: number;
        paymentKey?: string;
      };
      planState.tier = "enterprise";
      planState.checkoutRequested = false;
      confirmResponses.push({ orderId: payload.orderId ?? "", amount: payload.amount ?? 0 });
      await stubJson(route, {
        paymentKey: payload.paymentKey ?? "pay_mock_success",
        orderId: payload.orderId ?? SUCCESS_ORDER_ID,
        approvedAt: new Date().toISOString(),
        raw: { status: "DONE" },
      });
    });

    const successUrl = `${BASE_URL}/payments/success?paymentKey=pay_mock_success&orderId=${SUCCESS_ORDER_ID}&amount=${SUCCESS_AMOUNT}&tier=enterprise&redirectPath=/settings`;

    await page.goto(successUrl);

    await page.waitForResponse((response) => response.url().includes("/payments/toss/confirm"));

    await expect(page.getByText("결제가 완료됐어요")).toBeVisible();
    expect(confirmResponses.length).toBeGreaterThanOrEqual(1);

    const benefitLink = page.getByRole("link", { name: "설정에서 혜택 보기" });
    await expect(benefitLink).toBeVisible();
    await benefitLink.click();

    await page.waitForURL("**/settings", { timeout: 10_000 });
    await expect(page.getByText("Enterprise").first()).toBeVisible();
    expect(planState.tier).toBe("enterprise");
  });

  test("사용자 취소 시 실패 페이지 안내 후 플랜이 유지된다", async ({ page }) => {
    const planState: PlanState = { tier: "pro", checkoutRequested: false };

    await setupApiMocks(page, planState);

    const failUrl = `${BASE_URL}/payments/fail?orderId=${FAIL_ORDER_ID}&amount=${PRO_AMOUNT}&tier=pro&code=USER_CANCEL&message=${encodeURIComponent(
      "사용자가 결제를 취소했어요.",
    )}&redirectPath=/settings`;

    await page.goto(failUrl);

    await expect(page.getByText("결제를 확인하지 못했어요")).toBeVisible();

    const retryLink = page.getByRole("link", { name: "다시 결제 시도하기" });
    await expect(retryLink).toBeVisible();
    await expect(page.getByRole("link", { name: "도움이 필요하신가요?" })).toBeVisible();

    planState.checkoutRequested = false;
    planState.tier = "pro";

    await retryLink.click();

    await page.waitForURL("**/settings", { timeout: 12_000 });
    await expect(page.getByText("Pro").first()).toBeVisible();
    expect(planState.tier).toBe("pro");
  });

  test("결제 확인이 실패하면 에러 메시지를 표시한다", async ({ page }) => {
    const planState: PlanState = { tier: "pro", checkoutRequested: false };

    await setupApiMocks(page, planState);

    let confirmAttempts = 0;
    await page.route("**/api/v1/payments/toss/confirm", async (route) => {
      confirmAttempts += 1;
      planState.checkoutRequested = true;
      await stubJson(
        route,
        {
          detail: { message: "결제 확인 중 오류가 발생했어요." },
        },
        400,
      );
    });

    const successUrl = `${BASE_URL}/payments/success?paymentKey=pay_mock_error&orderId=${SUCCESS_ORDER_ID}&amount=${SUCCESS_AMOUNT}&tier=enterprise&redirectPath=/settings`;

    await page.goto(successUrl);

    await page.waitForResponse((response) => response.url().includes("/payments/toss/confirm"));

    await expect(page.getByText("결제를 확인하지 못했어요")).toBeVisible();
    await expect(page.locator("body")).toContainText("결제 확인 중 오류가 발생했어요.");
    expect(confirmAttempts).toBeGreaterThanOrEqual(1);

    const retryButton = page.getByRole("button", { name: "다시 결제 확인하기" });
    await expect(retryButton).toBeVisible();
    await expect(page.getByRole("link", { name: "도움이 필요하신가요?" })).toBeVisible();

    const responsePromise = page.waitForResponse((response) => response.url().includes("/payments/toss/confirm"));
    await retryButton.click();
    await responsePromise;

    expect(confirmAttempts).toBeGreaterThanOrEqual(2);
    await expect(page).toHaveURL(/payments\/success/);
    expect(planState.checkoutRequested).toBe(true);
  });
});
