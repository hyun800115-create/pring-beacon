// 새 기능 시험: 영토·상인·장식·카드·집 옮기기·봉화·결혼/출산/장례
//   PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/features.mjs <출력폴더> [--gpu]
import fs from 'node:fs';
import path from 'node:path';
import { start } from './serve.mjs';
import { launch } from './pw.mjs';
import { chromium } from 'playwright';
const OUT = process.argv[2]; fs.mkdirSync(OUT, { recursive: true });
const gpu = process.argv.includes('--gpu');
const srv = await start(0);
const b = gpu ? await chromium.launch({ headless: false, args: ['--ignore-gpu-blocklist'] }) : await launch();
const page = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
const errs = [];
page.on('pageerror', (e) => errs.push('pageerror: ' + (e.stack || e)));
page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text()); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
const shot = async (n) => { await page.screenshot({ path: path.join(OUT, n) }); console.log('shot', n); };
const log = (...a) => console.log(...a);
try {
  await page.goto(srv.url + 'index.html');
  await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 120000 });
  const st = await api('start');
  await api('settle', st.x + 6, st.z - 6, 0.3); await api('finishAll');
  await sleep(1500);
  const h = await api('hall');
  const place = async (type, dx, dz, rot = 0) => { const sp = await api('findSpot', type, h.x + dx, h.z + dz, rot); if (!sp) { log('no spot', type); return null; } const r = await api('build', type, sp[0], sp[1], rot); log('build', type, typeof r === 'string' ? r : 'ok'); return sp; };
  for (const [t, dx, dz] of [['house', -9, 3], ['house', -8, -6], ['tavern', 6, 10], ['coop', 12, -6], ['orchard', -4, 14], ['apiary', 14, 6], ['watchtower', 0, -20], ['shop', 10, 2]]) await place(t, dx, dz);
  await api('finishAll');
  log('outside territory:', await api('mine', h.x + 60, h.z + 60), 'inside:', await api('mine', h.x + 3, h.z + 3));
  await api('cam', h.x, h.z, 70, 0.8, 1.15); await sleep(1500); await shot('f1_territory.png');
  // 상인
  log('merchant', JSON.stringify(await api('merchant')));
  await api('coins', 300);
  for (let i = 0; i < 3; i++) log('buy', i, await api('buy', i));
  log('econ', JSON.stringify(await api('econ')));
  const ec = await api('econ');
  for (const k of Object.keys(ec.decos)) { const sp = await api('findSpot', k, h.x + 2, h.z + 7, 0); if (sp) log('deco', k, await api('placeDeco', k, sp[0], sp[1])); }
  // 카드
  for (let i = 0; i < 4; i++) log('draw', await api('draw'));
  await api('cam', h.x + 2, h.z + 6, 26, 0.7, 0.9); await sleep(1500); await shot('f2_merchant_deco.png');
  // 이벤트: 결혼식
  log('love', await api('forceLove'));
  await api('skipTo', 0.15); await api('speed', 2);
  await sleep(6000);
  await api('cam', h.x, h.z + 6, 24, 0.6, 0.8); await sleep(3000); await shot('f3_wedding.png');
  log('news', JSON.stringify((await api('news')).slice(0, 6)));
  await sleep(12000);
  log('birth q', await api('forceEvent', 'birth'));
  await sleep(9000); await shot('f4_birth.png');
  await sleep(8000);
  log('funeral q', await api('forceEvent', 'funeral'));
  await sleep(9000); await shot('f5_funeral.png');
  await sleep(8000);
  // 봉화
  await api('coins', 0);
  const bsp = await place('beacon', 4, -12);
  log('beacon', await api('beacon'));
  await sleep(5000);
  await api('cam', bsp ? bsp[0] : h.x, bsp ? bsp[1] : h.z, 28, 0.7, 0.75); await sleep(4000); await shot('f6_beacon.png');
  log('econ', JSON.stringify(await api('econ')));
  log('stats', JSON.stringify(await api('stats')));
  log('news', JSON.stringify(await api('news')));
  log('rival', JSON.stringify(await api('rivalBlds')));
} catch (e) { errs.push('test: ' + (e.stack || e)); try { await shot('fail.png'); } catch (e2) { /* */ } }
log('errors', errs.length ? '\n' + errs.slice(0, 20).join('\n') : 0);
await b.close(); await srv.close();
