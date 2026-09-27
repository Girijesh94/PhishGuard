import { test, expect } from "@playwright/test";
import fs from "node:fs";
const shots = "../artifacts/web-preview";
test.beforeAll(() => fs.mkdirSync(shots, { recursive: true }));
test("desktop graphics, live scan, validation and outage recovery", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Some links aren't what they seem." }),
  ).toBeVisible();
  await expect(page.locator(".shield-scene canvas")).toBeVisible({
    timeout: 30000,
  });
  await expect(page.locator(".glass-surface canvas")).toHaveCount(1, {
    timeout: 15000,
  });
  await expect(page.locator(".service-state")).toHaveText("Model connected");
  await page.getByRole("button", { name: "Pause visual motion" }).click();
  await page.screenshot({ path: shots + "/desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Try an example" }).click();
  await page.getByRole("button", { name: "Analyze link", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Fewer signs of phishing" }),
  ).toBeVisible();
  await expect(page.locator(".score strong")).toHaveText("12.1%");
  await page.getByText("What influenced the text model?").click();
  await expect(page.locator(".feature-list span")).toHaveCount(3);
  await page.screenshot({ path: shots + "/scan-result.png", fullPage: true });
  await page.getByRole("textbox", { name: "URL to check" }).fill("not a url");
  await page.getByRole("button", { name: "Analyze link", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Enter a web address");
  await page
    .getByRole("textbox", { name: "URL to check" })
    .fill("https://example.com");
  await page.route("**/model/predict", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: '{"detail":"unavailable"}',
    }),
  );
  await page.getByRole("button", { name: "Analyze link", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("scanner is unavailable");
  await page.getByRole("button", { name: "What does the score mean?" }).click();
  await expect(page.locator("#answer-1")).toBeVisible();
  expect(errors).toEqual([]);
});
test("mobile layout, keyboard access, reduced motion, WebGL fallback", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (kind === "webgl" || kind === "webgl2") return null;
      return original.call(this, kind, ...args);
    };
  });
  await page.goto("/");
  await expect(page.locator(".hero-art .shield-fallback")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Resume visual motion" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to URL scanner" }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Check a link", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("textbox", { name: "URL to check" }),
  ).toBeFocused();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: shots + "/mobile.png", fullPage: true });
});
test("mobile renders all four visual integrations", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".shield-scene canvas")).toBeVisible({
    timeout: 30000,
  });
  await expect(page.locator(".gradient-backdrop canvas")).toBeVisible();
  await expect(page.locator(".glass-surface canvas")).toHaveCount(1, {
    timeout: 15000,
  });
  await expect(page.locator(".liquid-mark canvas")).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: "Pause visual motion" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: shots + "/mobile-3d.png", fullPage: true });
});
