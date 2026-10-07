// Review helper (read-only): boots the game once and runs a scenario module.
//   node tools/test/review_visual_run.mjs <scenario.mjs> [--vp 390x844] [--fresh] [--title] [--lang en] [--dpr 2] [--debug]
// scenario.mjs exports default async ({ page, shot, sleep, ev, log, vp }) => {}
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const has = (k) => args.includes(k);
const scen = (await import(pathToFileURL(path.resolve(args[0])).href)).default;
const OUT = opt('--out', '/tmp/fv_review/visual');
const vp = opt('--vp', '390x844').split('x').map(Number);
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const url = srv.url + 'index.html' + (has('--debug') ? '?debug=1' : '');
const isMobile = !has('--desktop');
const { page, log } = await openPage(browser, url, { viewport: { width: vp[0], height: vp[1] }, dpr: Number(opt('--dpr', '2')), isMobile, hasTouch: isMobile, locale: opt('--lang', 'ko') === 'en' ? 'en-US' : 'ko-KR' });
const ev = (fn, a) => page.evaluate(fn, a);
const shot = async (name, o = {}) => { const p = path.join(OUT, name + '.jpg'); await page.screenshot({ path: p, type: 'jpeg', quality: 82, ...o }); console.log('shot', p); return p; };
try {
  if (has('--fresh')) { await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } }); await page.reload({ waitUntil: 'load' }); }
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 40000);
  await sleep(700);
  if (!has('--title')) {
    await tapStart(page);
    await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 30000);
    await sleep(800);
  }
  await scen({ page, shot, sleep, ev, log, vp, waitFor });
} catch (e) {
  console.log('ERROR', e.stack || e.message);
  await shot('zz_error').catch(() => {});
}
console.log('errors:', JSON.stringify(log.errors.slice(0, 10), null, 1));
await browser.close();
await srv.close();
