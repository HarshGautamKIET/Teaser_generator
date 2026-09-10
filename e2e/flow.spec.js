import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * The whole platform, driven through the browser exactly as a user would.
 *
 * Sign up, fetch a video from a YouTube link, generate teasers with a real
 * Gemini call, then check the three surfaces added most recently: the run
 * report, the keep/discard verdict control, and the cross-run library.
 *
 * Everything here is real -- the containers, the database, the download, the
 * model call, and FFmpeg. A mocked version of this test could pass while the
 * deployed stack was broken, which is the only failure this file exists to
 * catch.
 */

const SOURCE_URL = "https://www.youtube.com/watch?v=IfRqrrBbT-Y";

// A fresh account per run. Reusing one would let a previous run's videos and
// clips satisfy assertions that are supposed to be about this run.
const STAMP = Date.now();
const EMAIL = `e2e-${STAMP}@example.test`;
const PASSWORD = `e2e-pw-${STAMP}`;

const SHOTS = path.join(process.cwd(), "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

let shotIndex = 0;
async function shot(page, name) {
  shotIndex += 1;
  const file = path.join(SHOTS, `${String(shotIndex).padStart(2, "0")}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`    screenshot -> ${path.relative(process.cwd(), file)}`);
}

test("long video in, ranked teaser clips out", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

  // ---------------------------------------------------------------- sign up
  await test.step("sign up", async () => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();

    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page.getByRole("heading", { name: "Sign up" })).toBeVisible();

    await page.getByPlaceholder("Your Email").fill(EMAIL);
    await page.getByPlaceholder("Password").fill(PASSWORD);
    await shot(page, "signup-form");
    await page.getByRole("button", { name: "CREATE ACCOUNT" }).click();

    // Two legitimate outcomes. With ENABLE_EMAIL_AUTOCONFIRM the sign-up
    // returns a session and the app swaps straight to the shell; without it,
    // the form reports that a confirmation is needed and flips to sign-in.
    const shell = page.getByRole("button", { name: /Generate/ }).first();
    const needsConfirm = page.getByText(/Check your email to confirm/i);
    await expect(shell.or(needsConfirm)).toBeVisible({ timeout: 30_000 });

    if (await needsConfirm.isVisible().catch(() => false)) {
      throw new Error(
        "Auth requires email confirmation. Set ENABLE_EMAIL_AUTOCONFIRM=true " +
          "in docker/supabase/.env, or the sign-up flow cannot complete headlessly.",
      );
    }
    console.log(`    signed in as ${EMAIL}`);
    await shot(page, "signed-in");
  });

  // ---------------------------------------------------- fetch from the link
  await test.step("fetch the video from a URL", async () => {
    await page.getByRole("tab", { name: "From a link" }).click();

    const urlBox = page.locator("#source-url");
    await expect(urlBox).toBeVisible();
    await urlBox.fill(SOURCE_URL);
    await shot(page, "url-entered");

    await page.getByRole("button", { name: "Fetch Video" }).click();

    // The app advances itself: App.tsx polls the video until it reports `ready`
    // and then calls setStep("options"), so there is no Continue button to
    // press on this path -- waiting for one waits forever. Waiting on the
    // options step appearing still waits for the real download and probe,
    // because that is what triggers the advance.
    const generate = page.getByRole("button", { name: /Generate Teasers/ });
    await expect(generate).toBeVisible({ timeout: 5 * 60 * 1000 });
    await shot(page, "video-ready");
  });

  // ------------------------------------------------------------- generate
  await test.step("generate teasers with a real model call", async () => {
    const generate = page.getByRole("button", { name: /Generate Teasers/ });
    await expect(generate).toBeEnabled();
    await shot(page, "options");

    const started = Date.now();
    await generate.click();

    // The run moves source -> validating -> analyzing -> ranking -> generating.
    // Waiting on a clip appearing waits for all of it, including FFmpeg.
    const firstClip = page.locator("article.teaser").first();
    await expect(firstClip).toBeVisible({ timeout: 8 * 60 * 1000 });
    console.log(`    run finished in ${Math.round((Date.now() - started) / 1000)}s`);
  });

  // --------------------------------------------------------- what came out
  await test.step("clips are real and playable", async () => {
    const clips = page.locator("article.teaser");
    const count = await clips.count();
    expect(count).toBeGreaterThan(0);
    console.log(`    ${count} clip(s) rendered`);

    // A card with a title, a hook and a <video> whose blob resolved. The blob
    // only exists once the ownership-checked media route returned real bytes.
    const first = clips.first();
    await expect(first.locator(".teaser-title")).not.toBeEmpty();
    await expect(first.locator(".teaser-hook")).not.toBeEmpty();
    await expect(first.locator("video")).toHaveAttribute("src", /^blob:/, {
      timeout: 60_000,
    });

    const playable = await first.locator("video").evaluate(
      (el) =>
        new Promise((resolve) => {
          if (el.readyState >= 1 && el.duration > 0) return resolve(el.duration);
          el.addEventListener("loadedmetadata", () => resolve(el.duration), {
            once: true,
          });
          setTimeout(() => resolve(0), 20_000);
        }),
    );
    expect(playable).toBeGreaterThan(0);
    console.log(`    first clip decodes, duration ${playable.toFixed(1)}s`);
    await shot(page, "clips");
  });

  // ------------------------------------------------- the verdict control
  await test.step("record a keep verdict", async () => {
    const first = page.locator("article.teaser").first();
    const keep = first.getByRole("button", { name: "Keep" });
    await expect(keep).toBeVisible();
    await expect(keep).toHaveAttribute("aria-pressed", "false");

    const saved = page.waitForResponse(
      (r) => r.url().includes("/feedback") && r.request().method() === "PUT",
    );
    await keep.click();
    const response = await saved;
    expect(response.status()).toBe(200);
    await expect(keep).toHaveAttribute("aria-pressed", "true");
    console.log("    verdict persisted (PUT /feedback -> 200)");
    await shot(page, "verdict-recorded");
  });

  // ------------------------------------------------------- the run report
  await test.step("the run report shows what was discarded", async () => {
    // The sidebar entries are <button> elements driving client-side view state,
    // not anchors -- there is no router here, so getByRole("link") matches
    // nothing. Same for the run list: it is a div grid with a button per row
    // rather than a <table>, so there is no <tr> to click either.
    await page.getByRole("button", { name: "Runs" }).click();
    const row = page.locator("button.table-row-main").first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await row.click();

    const report = page.getByRole("heading", { name: /What this run discarded/i });
    await expect(report).toBeVisible({ timeout: 30_000 });

    const card = page.locator("section.card", { has: report });
    await expect(card.getByText(/The model proposed/)).toBeVisible();
    console.log(
      "    report: " +
        (await card.locator(".report-lede").innerText()).replace(/\s+/g, " "),
    );

    // Both stat tiles render a value rather than an empty cell, whether or not
    // the feature they describe actually ran on this source.
    const stats = card.locator(".report-stat-value");
    await expect(stats).toHaveCount(2);
    for (const text of await stats.allInnerTexts()) {
      expect(text.trim()).not.toBe("");
      console.log(`    stat: ${text.trim()}`);
    }
    await shot(page, "run-report");
  });

  // ------------------------------------------------------------- library
  await test.step("the clip reaches the cross-run library", async () => {
    await page.getByRole("button", { name: "Library" }).click();
    const clips = page.locator("article.teaser");
    await expect(clips.first()).toBeVisible({ timeout: 30_000 });
    console.log(`    library holds ${await clips.count()} clip(s)`);

    // The verdict recorded on the generate screen is carried by the API rather
    // than held in that component's state, so it survives the navigation.
    await expect(
      clips.first().getByRole("button", { name: "Keep" }),
    ).toHaveAttribute("aria-pressed", "true");
    console.log("    verdict survived navigation");
    await shot(page, "library");
  });

  // ------------------------------------------------------------ dashboard
  await test.step("the dashboard counts the run", async () => {
    await page.getByRole("button", { name: "Dashboard" }).click();
    await expect(page.locator(".stats, .stack").first()).toBeVisible({
      timeout: 30_000,
    });
    await shot(page, "dashboard");
  });

  // A console error during any of the above is a real defect even when every
  // assertion passed -- a failed background fetch shows up here and nowhere else.
  const ignorable = /favicon|Download the React DevTools/i;
  const real = consoleErrors.filter((e) => !ignorable.test(e));
  expect(real, `console errors:\n${real.join("\n")}`).toHaveLength(0);
});
