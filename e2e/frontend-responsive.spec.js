const path = require("path");
const { test, expect } = require("@playwright/test");

const pythonBotZip = path.join(__dirname, "fixtures", "python_bot.zip");

function buildUsername(testInfo) {
  const slug = testInfo.project.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  return `user-${slug}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

async function registerAndLandInLobby(page, username) {
  await page.goto("/login");
  await expect(page.getByTestId("auth-card")).toBeVisible();
  await page.getByTestId("auth-mode-register").click();
  await page.locator("#auth-username").fill(username);
  await page.locator("#auth-password").fill("correct-horse-battery-staple");
  await page.getByTestId("auth-submit").click();
  await page.waitForURL("**/lobby");
  await expect(page.locator("body[data-page='lobby']")).toBeVisible();
}

async function uploadBot(page, name, version, zipPath) {
  await page.goto("/my-bots");
  await page.getByTestId("my-bots-open-upload").click();
  await expect(page.locator("#my-bots-upload-modal")).toBeVisible();
  await expect(page.getByTestId("my-bots-upload-form")).toBeVisible();
  await page.locator("#bot-name").fill(name);
  await page.locator("#bot-version").fill(version);
  await page.locator("#bot-file").setInputFiles(zipPath);
  await page.getByTestId("my-bots-upload-submit").click();
  await expect(page.locator("#my-bots-upload-modal")).toHaveClass(/hidden/);
  await expect(page.locator("[data-testid^='bot-row-']").first()).toContainText(name);
}

async function createTable(page, smallBlind = "0.5", bigBlind = "1") {
  await page.goto("/lobby");
  await page.locator("#create-small-blind").fill(smallBlind);
  await page.locator("#create-big-blind").fill(bigBlind);
  await page.getByTestId("create-table-submit").click();
  await expect(page.getByText("Table created successfully. It is now listed below.")).toBeVisible();
  const firstOpenButton = page.locator("[data-testid^='open-table-']:visible").first();
  await expect(firstOpenButton).toBeVisible();
  await firstOpenButton.click();
  await page.waitForURL(/\/tables\//);
  await expect(page.getByTestId("poker-table")).toBeVisible();
}

async function seatBot(page, seatNumber, optionIndex) {
  const modal = page.locator("#seat-assignment-panel");
  await page.getByTestId(`seat-${seatNumber}-take`).click();
  await expect(modal).toBeVisible();
  await expect(page.getByTestId("seat-existing-bot-id")).toBeVisible();
  await page.getByTestId("seat-existing-bot-id").selectOption({ index: optionIndex });
  await page.getByTestId("seat-select-existing-submit").click();
  await expect(modal).toHaveClass(/hidden/);
  await expect(page.locator(`#seat-${seatNumber}-name`)).not.toHaveText("Open seat");
}

test("auth flow works across responsive breakpoints", async ({ page }, testInfo) => {
  const username = buildUsername(testInfo);
  await registerAndLandInLobby(page, username);
  await expect(page.getByRole("heading", { name: "Lobby" })).toBeVisible();
  await page.getByRole("button", { name: "Logout" }).click();
  await page.waitForURL("**/login");
  await expect(page.getByTestId("auth-form")).toBeVisible();
});

test("lobby and my bots stay usable across breakpoints", async ({ page }, testInfo) => {
  const username = buildUsername(testInfo);
  await registerAndLandInLobby(page, username);
  await uploadBot(page, "Responsive Python", "1.0.0", pythonBotZip);
  await createTable(page);

  if (testInfo.project.name === "chromium-mobile") {
    await page.goto("/lobby");
    await expect(page.getByTestId("lobby-table-cards")).toBeVisible();
  } else {
    await page.goto("/lobby");
    await expect(page.getByTestId("lobby-tables-table")).toBeVisible();
  }
});

test("desktop and tablet can seat bots, run a match, and inspect history", async ({ page }, testInfo) => {
  test.slow();
  test.skip(testInfo.project.name === "chromium-mobile", "Full live-control flow is covered on desktop and tablet.");

  const username = buildUsername(testInfo);
  await registerAndLandInLobby(page, username);
  await uploadBot(page, "Arena Python A", "1.0.0", pythonBotZip);
  await uploadBot(page, "Arena Python B", "2.0.0", pythonBotZip);
  await createTable(page);

  await seatBot(page, 1, 0);
  await seatBot(page, 2, 1);

  await expect(page.locator("#seat-1-name")).not.toHaveText("Open seat");
  await expect(page.locator("#seat-2-name")).not.toHaveText("Open seat");

  await page.getByTestId("start-match").click();
  await expect
    .poll(async () => await page.locator("#match-status").textContent(), {
      message: "match should leave waiting state",
    })
    .not.toContain("waiting");

  await page.getByTestId("hand-history-button").click();
  await expect
    .poll(async () => await page.locator("[data-testid='hands-list'] li").count(), {
      message: "hand history should populate",
    })
    .toBeGreaterThan(0);

  await page.locator("[data-testid='hands-list'] li button").first().click();
  await expect(page.getByTestId("hand-detail")).not.toContainText("Select a hand");

  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByTestId("hand-detail")).toContainText("Select a hand to view full history.");
});
