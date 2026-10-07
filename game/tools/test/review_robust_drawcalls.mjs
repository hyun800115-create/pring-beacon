// Per-frame GPU work: draw calls, texture binds, texture uploads (texImage2D/texSubImage2D) in a few
// typical views (plaza at start, plaza with everything unlocked, zoomed-out overview).
//   node tools/test/review_robust_drawcalls.mjs
import { newPage, bootToGame, launch, start, sleep, writeJSON, OUT } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser, { viewport: { width: 390, height: 844 }, dpr: 1 });
await page.addInitScript(() => {
  const C = window.__GLC = { draw: 0, bind: 0, upload: 0, uploadPx: 0, frames: 0 };
  const patch = (proto) => {
    for (const m of ['drawElements', 'drawArrays']) { const o = proto[m]; proto[m] = function (...a) { C.draw++; return o.apply(this, a); }; }
    const b = proto.bindTexture; proto.bindTexture = function (...a) { C.bind++; return b.apply(this, a); };
    for (const m of ['texImage2D', 'texSubImage2D']) {
      const o = proto[m];
      proto[m] = function (...a) { C.upload++; const src = a.find((x) => x && typeof x === 'object' && 'width' in x && 'height' in x); if (src) C.uploadPx += src.width * src.height; else if (typeof a[3] === 'number' && typeof a[4] === 'number') C.uploadPx += a[3] * a[4]; return o.apply(this, a); };
    }
  };
  if (window.WebGLRenderingContext) patch(WebGLRenderingContext.prototype);
  if (window.WebGL2RenderingContext) patch(WebGL2RenderingContext.prototype);
});
await bootToGame(page, srv.url + 'index.html');
const measure = (label) => page.evaluate(async (label) => {
  const C = window.__GLC, g = window.__FV.game;
  await new Promise((r) => setTimeout(r, 1500));
  const s = { draw: C.draw, bind: C.bind, upload: C.upload, px: C.uploadPx, f: g.loop.frame };
  const f0 = g.loop.frame; while (g.loop.frame - f0 < 30) await new Promise((r) => setTimeout(r, 20));
  const n = g.loop.frame - s.f;
  return { label, frames: n, drawPerFrame: +((C.draw - s.draw) / n).toFixed(1), bindPerFrame: +((C.bind - s.bind) / n).toFixed(1), uploadsPerFrame: +((C.upload - s.upload) / n).toFixed(2), uploadKPxPerFrame: +((C.uploadPx - s.px) / n / 1000).toFixed(1), children: window.__FV.scene.children.length };
}, label);
const res = [];
res.push(await measure('start plaza (fresh)'));
await page.evaluate(() => { window.__FV.unlockAll(); const p = window.__FV.where('shelf'); window.__FV.teleport(p.x, p.y + 80); });
await sleep(3000);
res.push(await measure('plaza, everything unlocked'));
await page.evaluate(() => { const p = window.__FV.where('up_capacity'); window.__FV.give(5000); window.__FV.teleport(p.x, p.y); });
await sleep(400);
res.push(await measure('paying on upgrade pad (cost text + ring redraw)'));
await page.evaluate(() => { window.__FV.teleport(900, 1700); window.__FV.camera(900, 1300, 0.42); });
await sleep(1500);
res.push(await measure('overview zoom 0.42'));
for (const r of res) console.log(JSON.stringify(r));
writeJSON('drawcalls.json', { res, errors: log.errors });
await browser.close(); await srv.close();
