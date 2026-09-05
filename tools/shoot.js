/* Screenshots for a checkpoint: every draft, at every width, in both themes.
   Uses the system Chrome through playwright-core so no browser download is needed.
   It also fails loudly on console errors and on any request that is not a font,
   because "no console errors, no external request except fonts" is a check the
   brief makes, and a screenshot run is the cheapest place to enforce it. */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "screenshots");
const BASE = process.env.BASE || "http://127.0.0.1:8765/noctua";
const WIDTHS = [
  { w: 1440, h: 900, tag: "1440" },
  { w: 768, h: 1024, tag: "768" },
  { w: 360, h: 800, tag: "360" },
];
const PAGES = (process.env.PAGES || "index,docs/index,docs/data-lens,404").split(",");
const LANGS = (process.env.LANGS || "en,it").split(",");
const SELF = new URL(BASE).hostname;   // the host under test, local or live
const ALLOWED_HOSTS = [];             // fonts are self-hosted: nothing else may be requested

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const problems = [];
  const external = new Set();

  for (const name of PAGES) {
   for (const lang of LANGS) {
    for (const { w, h, tag } of WIDTHS) {
      for (const theme of ["dark", "light"]) {
        const ctx = await browser.newContext({ viewport: { width: w, height: h },
                                               deviceScaleFactor: 2 });
        await ctx.addInitScript((s) => {
          try {
            localStorage.setItem("noctua-theme", s.theme);
            localStorage.setItem("noctua-lang", s.lang);
          } catch (e) {}
        }, { theme, lang });
        const page = await ctx.newPage();
        page.on("console", (m) => {
          if (m.type() === "error") problems.push(`${name} ${lang} ${tag} ${theme} console: ${m.text()}`);
        });
        page.on("pageerror", (e) => problems.push(`${name} ${lang} ${tag} ${theme} pageerror: ${e.message}`));
        page.on("response", (r) => {
          // a 404 on a favicon or an icon is silent in the page and invisible in a screenshot
          if (r.status() >= 400) problems.push(`${name} ${lang}: ${r.status()} on ${r.url()}`);
        });
        page.on("request", (r) => {
          const u = new URL(r.url());
          if (u.hostname !== SELF && u.protocol !== "data:") external.add(u.hostname);
        });

        await page.goto(`${BASE}/${name}.html?lang=${lang}`, { waitUntil: "networkidle" });

        const shown = await page.evaluate(() => document.documentElement.lang);
        if (shown !== lang) problems.push(`${name} ${lang}: <html lang> is "${shown}"`);
        await page.waitForTimeout(220);

        // horizontal overflow is a hard fail, not something to notice in the PNG
        const overflow = await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (overflow > 0) problems.push(`${name} ${lang} ${tag} ${theme}: horizontal overflow ${overflow}px`);

        const slug = name.replace("/", "-");
        await page.screenshot({ path: path.join(OUT, `${slug}-${lang}-${tag}-${theme}.png`),
                                fullPage: tag !== "1440" });
        if (tag === "1440") {
          await page.screenshot({ path: path.join(OUT, `${slug}-${lang}-${tag}-${theme}-full.png`),
                                  fullPage: true });
        }
        await ctx.close();
      }
    }
   }
  }
  await browser.close();

  const bad = [...external].filter((h) => !ALLOWED_HOSTS.includes(h));
  console.log(`external hosts requested: ${[...external].join(", ") || "none"}`);
  if (bad.length) problems.push(`external requests: ${bad.join(", ")}`);
  if (problems.length) { problems.forEach((p) => console.log("FAIL " + p)); process.exit(1); }
  console.log("OK — no console errors, no page errors, no horizontal overflow, no external requests");
})();
