// 휴대폰 비슷한 조건 성능: CPU 4배 느리게 + 844x390 화면 + 화면 배율 3 (이 PC 그래픽카드 사용)
import { start } from './serve.mjs';
import { chromium } from 'playwright';
const srv = await start(0);
const b = await chromium.launch({ headless: false, args: ['--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.argv[2] || 4) });
const errs = []; page.on('pageerror', (e) => errs.push(String(e)));
const t0 = Date.now();
await page.goto(srv.url + 'index.html');
await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 300000 });
console.log('load sec', ((Date.now() - t0) / 1000).toFixed(1));
const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
const st = await api('start'); await api('settle', st.x + 6, st.z - 6, 0.3); await api('finishAll');
const h = await api('hall');
for (const [t, dx, dz] of [['house', -9, 3], ['house', -8, -6], ['tavern', 6, 10], ['woodcutter', 12, -6], ['farm', -4, 14], ['bakery', 14, 6]]) { const sp = await api('findSpot', t, h.x + dx, h.z + dz, 0); if (sp) await api('build', t, sp[0], sp[1], 0); }
await api('finishAll');
for (const d of [30, 60]) {
  await api('cam', h.x, h.z, d, 0.8, 0.8);
  await new Promise((r) => setTimeout(r, 8000));
  console.log('dist', d, JSON.stringify(await page.evaluate(() => { const g = window.__SM.game; return { fps: Math.round(g.fps), dpr: g.stage.renderer.getPixelRatio(), calls: g.stage.renderer.info.render.calls }; })));
}
await page.screenshot({ path: '../.cache/shots/mobile.png' });
console.log('errors', errs.slice(0, 5));
await b.close(); await srv.close();
