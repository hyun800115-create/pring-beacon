// Quick screenshot helper for layout iteration.
//   node tools/test/shot.mjs out.png [--title] [--wait 1500] [--eval "__FV.unlockAll()"] [--vp 390x844] [--fresh]
//                                     [--cam x,y,zoom] [--debug] [--lang en]
import { start } from './serve.mjs';
import { launch, openPage, tapStart, sleep, waitFor } from './pw.mjs';

const args = process.argv.slice(2);
const out = args[0] || 'shot.png';
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const has = (k) => args.includes(k);

const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const vp = (opt('--vp', '390x844')).split('x').map(Number);
let url = srv.url + 'index.html' + (has('--debug') ? '?debug=1' : '');
const { page, log } = await openPage(browser, url, { viewport: { width: vp[0], height: vp[1] }, locale: opt('--lang', 'ko') === 'en' ? 'en-US' : 'ko-KR' });
try {
  if (has('--fresh')) await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* */ } });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 30000);
  await sleep(600);
  if (!has('--title')) {
    await tapStart(page);
    await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 20000);
    await sleep(800);
  }
  const ev = opt('--eval');
  if (ev) { const r = await page.evaluate(ev); if (r !== undefined) console.log('eval ->', JSON.stringify(r)); }
  const cam = opt('--cam');
  if (cam) { const [x, y, z] = cam.split(',').map(Number); await page.evaluate(([x, y, z]) => window.__FV.camera(x, y, z), [x, y, z]); }
  await sleep(Number(opt('--wait', '1200')));
  await page.screenshot({ path: out });
  console.log('saved', out);
} catch (e) {
  console.log('ERROR', e.message);
  await page.screenshot({ path: out }).catch(() => {});
}
console.log('errors:', JSON.stringify(log.errors, null, 1));
console.log('404s:', log.missing404.length, log.missing404.slice(0, 6).join('\n'));
const w = log.warnings.filter((x) => !/AudioContext|GPU stall|swiftshader|WebGL/i.test(x));
console.log('warnings:', w.length, w.slice(0, 12).join('\n'));
await browser.close();
await srv.close();
