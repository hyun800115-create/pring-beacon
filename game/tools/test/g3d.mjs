// 3D 게임 자동 확인: node tools/test/g3d.mjs <출력폴더> [--gpu] [--perf] [--play 초] [--vp WxH]
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch } from './pw.mjs';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const OUT = args[0]; fs.mkdirSync(OUT, { recursive: true });
const has = (k) => args.includes(k); const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const [vw, vh] = opt('--vp', '1280x720').split('x').map(Number);
const srv = await start(0);
const b = has('--gpu') ? await chromium.launch({ headless: true, args: ['--ignore-gpu-blocklist', '--use-angle=d3d11', '--enable-gpu'] }) : await launch();
const page = await (await b.newContext({ viewport: { width: vw, height: vh } })).newPage();
const errs = [];
page.on('pageerror', (e) => errs.push('pageerror: ' + (e.stack || e)));
page.on('console', (m) => { if ((m.type() === 'error' && !m.text().includes('404')) || (m.type() === 'warning' && !m.text().includes('GPU stall'))) errs.push(m.type() + ': ' + m.text()); });
page.on('response', (r) => { if (r.status() >= 400 && !/assets3d\/(props\/(item_|deco_)|chars\/animal_)/.test(r.url())) errs.push('HTTP ' + r.status() + ' ' + r.url()); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (fn, ...a) => page.evaluate(([f, a2]) => window.__SM.api[f](...a2), [fn, a]);
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n) }); console.log('shot', n); };
const log = (...a) => console.log(...a);
try {
  await page.goto(srv.url + 'index.html' + (has('--perf') ? '?perf=1' : '?debug=1'));
  await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 120000 });
  await sleep(2500);
  log('stats', JSON.stringify(await api('stats')));
  await shot(has('--perf') ? 'perf.png' : 'start.png');
  const secs = Number(opt('--play', 0));
  if (secs && !has('--perf')) {
    const st = await api('start');
    await api('settle', st.x + 6, st.z - 6, 0.3);
    await api('speed', 3);
    await sleep(4000); await shot('hall_site.png');
    await page.waitForFunction(() => window.__SM.api.hall() && window.__SM.api.hall().state === 'active', null, { timeout: 120000 });
    const h = await api('hall'); log('hall', JSON.stringify(h));
    const place = async (type, dx, dz, rot = 0) => {
      const sp = await api('findSpot', type, h.x + dx, h.z + dz, rot);
      if (!sp) { log('no spot', type); return null; }
      const r = await api('build', type, sp[0], sp[1], rot);
      log('build', type, sp.map((v) => v.toFixed(1)), typeof r === 'string' ? r : 'ok');
      if (typeof r !== 'string') await api('road', [[r.door.x, r.door.z], [h.door.x, h.door.z]]);
      return r;
    };
    await place('house', -9, 4, 0.4); await place('house', -10, -4, -0.3);
    await place('woodcutter', 14, 10, 0); await place('sawmill', 9, 2, 0);
    await place('quarry', -14, -14, 0.8); await place('farm', -2, 14, 0); await place('windmill', 6, 14, 0); await place('bakery', 12, -6, 0);
    await place('tavern', -4, -12, 0); await place('well', 4, 8, 0);
    await api('cam', h.x, h.z + 3, 40);
    for (let k = 0; k < secs / 10; k++) {
      await sleep(10000);
      if (await api('offer', true)) log('immigrants accepted');
      const s = await api('stats');
      log(`t+${(k + 1) * 10}s`, JSON.stringify(s));
      if (k % 3 === 0) await shot(`play_${String(k).padStart(2, '0')}_${s.phase}.png`);
    }
    log('news', JSON.stringify(await api('news')));
  }
  if (has('--perf')) { await sleep(6000); log('stats', JSON.stringify(await api('stats'))); await shot('perf2.png'); }
} catch (e) { errs.push('test: ' + (e.stack || e)); try { await shot('fail.png'); } catch (e2) { /* */ } }
log('errors', errs.length ? '\n' + errs.slice(0, 25).join('\n') : 0);
await b.close(); await srv.close();
