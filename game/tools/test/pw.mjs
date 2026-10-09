// Shared Playwright helpers for the Frost Village tests (resolves the global 'playwright' package).
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';

const require = createRequire(import.meta.url);
// 크롬은 저장소/.cache/pw-browsers 에 설치돼 있다.
{
  const { fileURLToPath } = await import('node:url');
  const { existsSync } = await import('node:fs');
  const b = path.resolve(fileURLToPath(import.meta.url), '../../../../.cache/pw-browsers');
  if (!process.env.PLAYWRIGHT_BROWSERS_PATH && existsSync(b)) process.env.PLAYWRIGHT_BROWSERS_PATH = b;
}

export function loadPlaywright() {
  try { return require('playwright'); } catch (e) { /* fall through */ }
  const roots = [];
  try { roots.push(execSync('npm root -g', { encoding: 'utf8' }).trim()); } catch (e) { /* */ }
  roots.push('/opt/node22/lib/node_modules', '/usr/local/lib/node_modules', '/usr/lib/node_modules');
  for (const r of roots) {
    try { return require(path.join(r, 'playwright')); } catch (e) { /* next */ }
  }
  throw new Error("Could not find the 'playwright' package. Install it with: npm i -g playwright && npx playwright install chromium");
}

export async function launch() {
  const { chromium } = loadPlaywright();
  return chromium.launch({
    headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl', '--no-sandbox'],
  });
}

/** new mobile-like page with console / error capture */
export async function openPage(browser, url, opts = {}) {
  const ctx = await browser.newContext({
    viewport: opts.viewport || { width: 390, height: 844 },
    deviceScaleFactor: opts.dpr || 2,
    isMobile: opts.isMobile !== false,
    hasTouch: opts.hasTouch !== false,
    locale: opts.locale || 'ko-KR',
  });
  const page = await ctx.newPage();
  const log = { errors: [], warnings: [], missing404: [], all: [] };
  page.on('pageerror', (e) => log.errors.push('pageerror: ' + (e && e.stack ? e.stack : e)));
  page.on('console', (m) => {
    const tx = m.text();
    log.all.push(m.type() + ': ' + tx);
    if (m.type() === 'error') {
      if (/Failed to load resource: the server responded with a status of 404/.test(tx)) log.missing404.push(tx + ' ' + (m.location() && m.location().url || ''));
      else log.errors.push('console.error: ' + tx);
    } else if (m.type() === 'warning') log.warnings.push(tx);
  });
  page.on('response', (r) => { if (r.status() === 404) log.missing404.push('404 ' + r.url()); });
  await page.goto(url, { waitUntil: 'load' });
  return { page, ctx, log };
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** wait until a JS expression is truthy in the page */
export async function waitFor(page, fn, timeout = 20000, arg) {
  return page.waitForFunction(fn, arg, { timeout, polling: 100 });
}

/** tap the canvas centre (title screen) */
export async function tapStart(page) {
  const c = await page.$('canvas');
  const b = await c.boundingBox();
  await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height * 0.6);
}

/**
 * steer the player to a world point using __FV.setInput (like a joystick), with a teleport fallback
 */
export async function walkTo(page, target, opts = {}) {
  const tol = opts.tol || 22;
  const t0 = Date.now();
  let last = null, stuck = 0;
  while (Date.now() - t0 < (opts.timeout || 12000)) {
    const s = await page.evaluate(() => window.__FV.state().player);
    const dx = target.x - s.x, dy = target.y - s.y;
    const d = Math.hypot(dx, dy * 2);
    if (d < tol) break;
    const k = Math.min(1, d / 60);
    await page.evaluate(([x, y]) => window.__FV.setInput(x, y), [(dx / Math.hypot(dx, dy)) * k, (dy / Math.hypot(dx, dy)) * k]);
    await sleep(80);
    if (last && Math.hypot(s.x - last.x, s.y - last.y) < 1.5) { if (++stuck > 12) break; } else stuck = 0;
    last = s;
  }
  await page.evaluate(() => window.__FV.setInput(0, 0));
  const s = await page.evaluate(() => window.__FV.state().player);
  if (Math.hypot(target.x - s.x, (target.y - s.y) * 2) > tol * 1.6 && opts.teleport !== false) {
    await page.evaluate(([x, y]) => window.__FV.teleport(x, y), [target.x, target.y]);
    return false;
  }
  return true;
}

// 창을 띄우지 않고 진짜 그래픽카드(D3D11)를 쓰는 크롬 — 대표님 화면을 가리지 않는다. (headless:false 금지)
export const GPU_ARGS = ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'];
export async function launchGpu(extra = {}) {
  const { chromium } = loadPlaywright();
  return chromium.launch(Object.assign({ headless: true, args: GPU_ARGS }, extra));
}
