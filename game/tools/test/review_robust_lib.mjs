// Shared helpers for the robustness / performance review scripts (review_robust_*.mjs).
// Outputs go to .cache/fv_review/robust/.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { start } from './serve.mjs';
import { launch, sleep, waitFor, tapStart } from './pw.mjs';
import { fileURLToPath as fvToPath } from 'node:url';
const FV_REVIEW = process.env.FV_REVIEW || path.resolve(fvToPath(import.meta.url), '../../../../.cache/fv_review');  // 저장소/.cache/fv_review

export { start, launch, sleep, waitFor, tapStart };
export const OUT = path.join(FV_REVIEW, 'robust');
fs.mkdirSync(OUT, { recursive: true });
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/** like pw.openPage but lets the caller install init scripts / routes before navigation */
export async function newPage(browser, opts = {}) {
  const ctx = await browser.newContext({
    viewport: opts.viewport || { width: 390, height: 844 },
    deviceScaleFactor: opts.dpr || 1,
    isMobile: opts.isMobile !== false,
    hasTouch: opts.hasTouch !== false,
    locale: opts.locale || 'ko-KR',
  });
  const page = await ctx.newPage();
  const log = { errors: [], warnings: [], all: [], failedReq: [] };
  page.on('pageerror', (e) => log.errors.push('pageerror: ' + (e && e.stack ? e.stack.split('\n').slice(0, 4).join(' | ') : e)));
  page.on('console', (m) => {
    const tx = m.text();
    log.all.push(m.type() + ': ' + tx);
    if (m.type() === 'error') log.errors.push('console.error: ' + tx);
    else if (m.type() === 'warning') log.warnings.push(tx);
  });
  page.on('requestfailed', (r) => log.failedReq.push(r.url() + ' ' + (r.failure() && r.failure().errorText)));
  page.on('response', (r) => { if (r.status() >= 400) log.failedReq.push(r.status() + ' ' + r.url()); });
  return { page, ctx, log };
}

export async function bootToGame(page, url, { fresh = true, timeout = 90000 } = {}) {
  await page.goto(url, { waitUntil: 'load' });
  if (fresh) {
    await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
    await page.reload({ waitUntil: 'load' });
  }
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), timeout);
  await sleep(400);
  await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI') && window.__FV.scene && window.__FV.scene.sys.isActive(), timeout);
  await sleep(500);
}

export function writeJSON(name, obj) {
  const p = path.join(OUT, name);
  fs.writeFileSync(p, JSON.stringify(obj, null, 1));
  return p;
}

/** a static server for frost-village/ that adds CORS headers (for the sandboxed-iframe test) */
export function startCors(port = 0, prefix = '/fv/') {
  return new Promise((resolve) => {
    const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg', '.webmanifest': 'application/manifest+json' };
    const server = http.createServer((req, res) => {
      let u = decodeURIComponent((req.url || '/').split('?')[0]);
      if (!u.startsWith(prefix)) { res.writeHead(404); res.end(); return; }
      u = '/' + u.slice(prefix.length);
      if (u.endsWith('/')) u += 'index.html';
      const fp = path.join(ROOT, path.normalize(u));
      fs.stat(fp, (err, st) => {
        if (err || !st.isFile()) { res.writeHead(404, { 'access-control-allow-origin': '*' }); res.end(); return; }
        res.writeHead(200, { 'content-type': TYPES[path.extname(fp)] || 'application/octet-stream', 'access-control-allow-origin': '*', 'content-length': st.size });
        fs.createReadStream(fp).pipe(res);
      });
    });
    server.listen(port, '127.0.0.1', () => resolve({ url: `http://127.0.0.1:${server.address().port}${prefix}`, close: () => new Promise((r) => server.close(r)) }));
  });
}

/** a host page server (different origin) serving arbitrary HTML */
export function startHost(html) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end(html); });
    server.listen(0, '127.0.0.1', () => resolve({ url: `http://localhost:${server.address().port}/`, close: () => new Promise((r) => server.close(r)) }));
  });
}
