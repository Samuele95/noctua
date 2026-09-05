/* Proves the chain diagram is usable without a mouse, and that hovering a source really
   narrows the lanes. Run after any change to chain.js or chain.css. */
const { chromium } = require("playwright-core");
const path = require("path");

(async () => {
  const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const results = [];
  const fail = (m) => { results.push("FAIL " + m); };
  const ok = (m) => { results.push("ok   " + m); };

  for (const lang of ["en", "it"]) {
  for (const name of ["index"]) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 },
                                           deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(`${process.env.BASE || "http://127.0.0.1:8765/noctua"}/${name}.html?lang=${lang}`, { waitUntil: "networkidle" });

    const stages = await page.locator(".stage").count();
    stages === 10 ? ok(`${name} ${lang}: 10 stage buttons`) : fail(`${name} ${lang}: ${stages} stage buttons, want 10`);

    // keyboard only: tab until the first stage has focus, then walk with ArrowRight
    let guard = 0, reached = false;
    while (guard++ < 40) {
      await page.keyboard.press("Tab");
      if (await page.evaluate(() => document.activeElement.classList.contains("stage"))) {
        reached = true; break;
      }
    }
    reached ? ok(`${name} ${lang}: a stage is reachable by Tab (${guard} presses)`)
            : fail(`${name} ${lang}: no stage reachable by Tab`);

    const focusFilled = await page.locator("#chain-detail .detail-head h3").count();
    focusFilled ? ok(`${name} ${lang}: focus alone fills the detail region`)
                : fail(`${name} ${lang}: focus did not fill the detail region`);

    await page.keyboard.press("ArrowRight");
    const moved = await page.evaluate(() => document.activeElement.dataset.stage);
    moved ? ok(`${name} ${lang}: ArrowRight moves along the rail (now "${moved}")`)
          : fail(`${name} ${lang}: ArrowRight did not move focus`);

    await page.keyboard.press("Enter");
    const pinned = await page.locator('.stage[aria-pressed="true"]').count();
    pinned === 1 ? ok(`${name} ${lang}: Enter pins one stage`) : fail(`${name} ${lang}: Enter pinned ${pinned}`);

    await page.keyboard.press("Escape");
    const afterEsc = await page.locator('.stage[aria-pressed="true"]').count();
    afterEsc === 0 ? ok(`${name} ${lang}: Escape unpins`) : fail(`${name} ${lang}: Escape left ${afterEsc} pinned`);

    // hovering a source narrows the lanes
    await page.locator('.src[data-lane="dataset"]').hover();
    const dimmed = await page.locator(".stage.is-off").count();
    dimmed > 0 ? ok(`${name} ${lang}: hovering "dataset" dims ${dimmed} off-lane stages`)
               : fail(`${name} ${lang}: hovering a source dimmed nothing`);

    // a capture with a stage selected, for the record
    await page.locator('.stage[data-stage="shape"]').click();
    await page.waitForTimeout(150);
    await page.locator("#chain-diagram").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(__dirname, "..", "screenshots",
                                            `${name}-${lang}-1440-stage-selected.png`) });
    await ctx.close();
  }
  }
  await browser.close();
  results.forEach((r) => console.log(r));
  process.exit(results.some((r) => r.startsWith("FAIL")) ? 1 : 0);
})();
