import { expect, test, type Route } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL ?? "http://localhost:3000";

const PLAN_CONTEXT_RESPONSE = {
  planTier: "pro",
  expiresAt: "2026-12-31T00:00:00+00:00",
  entitlements: ["search.compare", "search.alerts", "evidence.inline_pdf"],
  featureFlags: {
    searchCompare: true,
    searchAlerts: true,
    searchExport: false,
    evidenceInlinePdf: true,
    evidenceDiff: false,
    timelineFull: false,
  },
  quota: {
    chatRequestsPerDay: 500,
    ragTopK: 6,
    selfCheckEnabled: true,
    peerExportRowLimit: 120,
  },
  updatedAt: "2025-01-01T00:00:00+00:00",
  updatedBy: "qa@kfinance.ai",
  changeNote: "QA preset",
  checkoutRequested: false,
};

const WEBHOOK_AUDIT_RESPONSE = {
  items: [
    {
      loggedAt: "2025-02-01T00:00:00+00:00",
      result: "processed",
      context: {
        order_id: "kfinance-enterprise-qa",
        transmission_id: "webhook-trans-qa",
        status: "DONE",
      },
      payload: {
        eventType: "PAYMENT_STATUS_CHANGED",
        data: { status: "DONE", orderId: "kfinance-enterprise-qa" },
      },
    },
  ],
};

const adminRoutes = async (route: Route) => {
  const url = route.request().url();
  if (url.includes("/api/v1/plan/context")) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PLAN_CONTEXT_RESPONSE),
    });
    return;
  }
  if (url.includes("/api/v1/admin/webhooks/toss/events")) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(WEBHOOK_AUDIT_RESPONSE),
    });
    return;
  }
  if (url.includes("/api/v1/admin/plan/quick-adjust")) {
    const payload = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...PLAN_CONTEXT_RESPONSE,
        planTier: payload.planTier ?? PLAN_CONTEXT_RESPONSE.planTier,
        entitlements: payload.entitlements ?? PLAN_CONTEXT_RESPONSE.entitlements,
        quota: {
          ...PLAN_CONTEXT_RESPONSE.quota,
          ...(payload.quota ?? {}),
        },
        checkoutRequested: Boolean(payload.forceCheckoutRequested ?? false),
      }),
    });
    return;
  }
  await route.fallback();
};

test.describe("Admin Quick Actions", () => {
  test("locks default entitlements and supports webhook replay", async ({ page }) => {
    const replayCalls: unknown[] = [];

    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/api/v1/admin/webhooks/toss/replay")) {
        replayCalls.push(JSON.parse(route.request().postData() ?? "{}"));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "DONE", orderId: "kfinance-enterprise-qa", tier: "enterprise" }),
        });
        return;
      }
      await adminRoutes(route);
    });

    await page.goto(`${BASE_URL}/admin`);

    await expect(page.getByText("플랜 퀵 액션")).toBeVisible();

    const compareCheckbox = page.getByLabel("비교 검색");
    await expect(compareCheckbox).toBeChecked();
    await expect(compareCheckbox).toBeDisabled();

    const exportCheckbox = page.getByLabel("데이터 내보내기");
    await expect(exportCheckbox).toBeDisabled();

    await page.getByLabel("적용할 플랜 티어").selectOption("enterprise");
    await expect(exportCheckbox).toBeChecked();
    await expect(exportCheckbox).toBeDisabled();

    const replayButton = page.getByRole("button", { name: "재시도" }).first();
    await replayButton.click();
    expect(replayCalls.length).toBe(1);
    expect(replayCalls[0]).toMatchObject({ transmissionId: "webhook-trans-qa" });
  });
});
