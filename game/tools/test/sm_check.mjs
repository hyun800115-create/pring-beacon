// 봄날의 행진 시제품 자동 확인: 서버를 띄우고 크롬으로 열어 오류·화면을 확인한다.
//   node tools/test/sm_check.mjs [출력폴더] [--perf] [--vp 1280x720] [--steps]
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch } from './pw.mjs';

const args = process.argv.slice(2);
const OUT = args[0] && !args[0].startsWith('--') ? args[0] : '.';
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const has = (k) => args.includes(k);
fs.mkdirSync(OUT, { recursive: true });

const srv = await start(0);
const browser = await launch();
const [vw, vh] = opt('--vp', '1280x720').split('x').map(Number);
const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1, locale: 'ko-KR', isMobile: has('--mobile'), hasTouch: has('--mobile') });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + (e.stack || e)));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
page.on('response', (r) => { if (r.status() >= 400) errors.push('404: ' + r.url()); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (fn, ...a) => page.evaluate(([f, a2]) => window.__SM.api[f](...a2), [fn, a]);
const shot = async (name) => { const p = path.join(OUT, name); await page.screenshot({ path: p }); console.log('shot', p); };

try {
  await page.goto(srv.url + 'index.html' + (has('--perf') ? '?perf=1' : ''));
  await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 60000 });
  await sleep(1500);
  console.log('stats', JSON.stringify(await api('stats')));
  await shot(has('--perf') ? 'perf_0.png' : 'start.png');
  if (has('--perf')) {
    await sleep(6000);
    console.log('stats', JSON.stringify(await api('stats')));
    await shot('perf_1.png');
    await api('zoom', 0.22); await sleep(3000);
    console.log('stats(zoom out)', JSON.stringify(await api('stats')));
    await shot('perf_2.png');
  }
  if (has('--steps')) {
    const st = await api('start');
    await api('settle', st.i + 3, st.j - 3);
    await api('speed', 3);
    await sleep(6000);
    await shot('hall_building.png');
    console.log('stats', JSON.stringify(await api('stats')));
    await page.waitForFunction(() => window.__SM.api.hall() && window.__SM.api.hall().state === 'active', null, { timeout: 60000 });
    await sleep(2000);
    await shot('hall_done.png');
    console.log('stats', JSON.stringify(await api('stats')));
  }
} catch (e) {
  errors.push('test: ' + (e.stack || e));
  try { await shot('fail.png'); } catch (e2) { /* */ }
}
console.log('errors:', errors.length ? '\n' + errors.slice(0, 30).join('\n') : 0);
await browser.close();
await srv.close();
