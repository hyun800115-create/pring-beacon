// 봄날의 행진 시제품: 실제처럼 마을을 세우고 생산 줄을 이어 하루 이상 돌려 본다.
//   node tools/test/sm_play.mjs [출력폴더] [--secs 90]
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch } from './pw.mjs';

const args = process.argv.slice(2);
const OUT = args[0] && !args[0].startsWith('--') ? args[0] : '.';
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
fs.mkdirSync(OUT, { recursive: true });
const SECS = Number(opt('--secs', 90));

const srv = await start(0);
const browser = await launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, locale: 'ko-KR' });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + (e.stack || e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (fn, ...a) => page.evaluate(([f, a2]) => window.__SM.api[f](...a2), [fn, a]);
const shot = async (name) => { await page.screenshot({ path: path.join(OUT, name) }); console.log('shot', name); };
const log = (...a) => console.log(...a);

try {
  await page.goto(srv.url + 'index.html');
  await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 60000 });
  await sleep(800);
  const st = await api('start');
  await api('settle', st.i + 3, st.j - 3);
  await api('speed', 3);
  await page.waitForFunction(() => window.__SM.api.hall() && window.__SM.api.hall().state === 'active', null, { timeout: 60000 });
  const hall = await api('hall');
  log('hall flag', hall);
  // 건물 놓고 마을회관까지 길 잇기
  const place = async (type, ni, nj) => {
    const sp = await api('findSpot', type, ni, nj);
    if (!sp) { log('no spot', type); return null; }
    const f = await api('build', type, sp[0], sp[1]);
    const ok = f ? await api('connect', f[0], f[1]) : false;
    log('build', type, sp, 'flag', f, 'road', ok);
    return f;
  };
  await place('house', hall.i - 3, hall.j + 2);
  await place('house', hall.i - 5, hall.j + 5);
  await place('woodcutter', hall.i + 7, hall.j + 5);
  await place('sawmill', hall.i + 4, hall.j + 1);
  await place('stonecutter', hall.i + 7, hall.j - 6);
  await place('farm', hall.i - 6, hall.j - 3);
  await place('windmill', hall.i - 3, hall.j - 2);
  await place('bakery', hall.i, hall.j - 4);
  await api('center', hall.i + 1, hall.j); await api('zoom', 0.62);
  log('stats', JSON.stringify(await api('stats')));
  for (let k = 0; k < SECS / 10; k++) {
    await sleep(10000);
    if (await api('offer', true)) log('immigrants accepted');
    const s = await api('stats');
    log(`t+${(k + 1) * 10}s`, JSON.stringify(s));
    if (k === 1 || k === 4 || k % 3 === 0) await shot(`play_${String(k).padStart(2, '0')}_${s.phase}.png`);
  }
  log('people', JSON.stringify(await api('people')));
  log('news', JSON.stringify(await api('news')));
} catch (e) {
  errors.push('test: ' + (e.stack || e));
  try { await shot('fail.png'); } catch (e2) { /* */ }
}
console.log('errors:', errors.length ? '\n' + errors.slice(0, 30).join('\n') : 0);
await browser.close();
await srv.close();
