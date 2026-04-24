import { test, expect } from "@playwright/test";

test.describe("ops-admin smoke", () => {
  test("dashboard renders with headline, KPI cards and sidebar navigation", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/대시보드|Dashboard/);
    await expect(page.getByText(/실행 중 수집|Active collections/)).toBeVisible();
    await expect(page.getByRole("link", { name: /조달 주문|Procurement Jobs/ })).toBeVisible();
  });

  test("jobs page shows not-connected guide when no token saved", async ({ page }) => {
    await page.goto("/jobs");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      /조달 주문|Procurement Jobs/,
    );
    await expect(
      page.getByRole("link", { name: /설정|Settings/ }),
    ).toBeVisible();
  });

  test("navigating between sections updates breadcrumb and URL", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: /수집 결과|Results/ }).click();
    await expect(page).toHaveURL(/\/results$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/수집 결과|Results/);

    await page.getByRole("link", { name: /알림|Notifications/ }).click();
    await expect(page).toHaveURL(/\/notifications$/);
  });

  test("settings page exposes backend URL and token inputs", async ({ page }) => {
    await page.goto("/settings");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/설정|Settings/);
    await expect(page.getByLabel(/백엔드 URL|Backend URL/)).toBeVisible();
    await expect(page.getByLabel(/Bearer/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^(설정 저장|Save)$/ }),
    ).toBeEnabled();
  });

  test("header shows theme and locale controls", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("button", { name: /테마 전환|Toggle theme/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /언어 전환|Change language/ }),
    ).toBeVisible();
  });

  test("experiments page shows four parser tabs", async ({ page }) => {
    await page.goto("/experiments");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      /파서 실험|Parser Experiments/,
    );
    const tabList = page.getByRole("tablist");
    await expect(tabList.getByRole("tab")).toHaveCount(4);
  });
});
