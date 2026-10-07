// Embedding: run the game inside iframes on a different origin.
//   1. sandbox="allow-scripts" (opaque origin), game server WITHOUT CORS headers (plain static host)
//   2. sandbox="allow-scripts" (opaque origin), game server WITH Access-Control-Allow-Origin: *
//   3. sandbox="allow-scripts allow-same-origin" cross-origin (itch.io-style), no CORS
//   4. plain cross-origin iframe (no sandbox)
//   node tools/test/review_robust_iframe.mjs
import { launch, start, sleep, startCors, startHost, newPage, writeJSON, OUT } from './review_robust_lib.mjs';

const plain = await start(0, { prefix: '/fv/' });
const cors = await startCors(0, '/fv/');
const browser = await launch();
const results = {};

const cases = [
  { name: 'sandbox_scripts_noCORS', sandbox: 'allow-scripts', srv: plain },
  { name: 'sandbox_scripts_CORS', sandbox: 'allow-scripts', srv: cors },
  { name: 'sandbox_scripts_sameorigin', sandbox: 'allow-scripts allow-same-origin', srv: plain },
  { name: 'crossorigin_nosandbox', sandbox: null, srv: plain },
];

for (const c of cases) {
  const src = c.srv.url + 'index.html';
  const html = `<!doctype html><html><body style="margin:0;background:#333;height:3000px"><p style="color:#fff;margin:4px">host page</p>
<iframe id="g" ${c.sandbox !== null ? `sandbox="${c.sandbox}"` : ''} src="${src}" style="border:0;width:390px;height:780px" allow="autoplay"></iframe></body></html>`;
  const host = await startHost(html);
  const { page, ctx, log } = await newPage(browser, { viewport: { width: 420, height: 820 } });
  const r = { sandbox: c.sandbox, cors: c.srv === cors };
  try {
    await page.goto(host.url, { waitUntil: 'load' });
    let frame = null;
    for (let i = 0; i < 100 && !frame; i++) { frame = page.frames().find((f) => f.url().includes('/fv/index.html')); if (!frame) await sleep(100); }
    // wait for title or give up after 25 s
    const t0 = Date.now();
    let booted = false;
    while (Date.now() - t0 < 25000) {
      booted = await frame.evaluate(() => !!(window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'))).catch(() => false);
      if (booted) break;
      await sleep(250);
    }
    r.titleReached = booted;
    r.frameState = await frame.evaluate(() => ({
      origin: self.origin, fvDefined: !!window.__FV, phaser: typeof Phaser,
      loadingVisible: !!document.getElementById('fv-loading') && getComputedStyle(document.getElementById('fv-loading')).opacity,
      errorBox: document.getElementById('fv-error') && document.getElementById('fv-error').style.display + ' ' + document.getElementById('fv-error').textContent,
      lsAccess: (() => { try { localStorage.getItem('x'); return 'ok'; } catch (e) { return 'throws ' + e.name; } })(),
    })).catch((e) => 'eval failed: ' + e.message);
    if (booted) {
      const el = await page.$('#g');
      const b = await el.boundingBox();
      await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height * 0.6);
      let inGame = false;
      for (let i = 0; i < 80 && !inGame; i++) { inGame = await frame.evaluate(() => !!(window.__FV.state && window.__FV.game.scene.isActive('UI'))).catch(() => false); if (!inGame) await sleep(250); }
      r.gameStarted = inGame;
      if (inGame) {
        await sleep(1500);
        r.game = await frame.evaluate(async () => {
          const FV = window.__FV, g = FV.game;
          FV.give(40);
          const n = FV.where('hire_fisherman'); FV.teleport(n.x, n.y);
          const f0 = g.loop.frame; while (g.loop.frame - f0 < 200 && !FV.state().done.includes('hire_fisherman')) await new Promise((r) => setTimeout(r, 50));
          FV.save();
          return { coins: FV.state().coins, hired: FV.state().done.includes('hire_fisherman'), audioKeys: g.cache.audio.getKeys().length, ctx: g.sound.context && g.sound.context.state, playing: g.sound.sounds.filter((s) => s.isPlaying).map((s) => s.key), saved: (() => { try { return !!localStorage.getItem('frostVillage.save.v1'); } catch (e) { return 'no storage (' + e.name + ')'; } })() };
        }).catch((e) => 'eval failed ' + e.message);
      }
    }
    if (r.gameStarted) {
      // keyboard play inside an embed: do arrow keys / space scroll the host page?
      const el = await page.$('#g'); const bb = await el.boundingBox();
      await page.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2);
      const y0 = await page.evaluate(() => scrollY);
      const p0 = await frame.evaluate(() => ({ x: Math.round(window.__FV.scene.player.x), y: Math.round(window.__FV.scene.player.y) }));
      for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowDown', { delay: 120 });
      await page.keyboard.press('Space');
      await sleep(400);
      r.keyboardInEmbed = { hostScrollYBefore: y0, hostScrollYAfter: await page.evaluate(() => scrollY), playerBefore: p0, playerAfter: await frame.evaluate(() => ({ x: Math.round(window.__FV.scene.player.x), y: Math.round(window.__FV.scene.player.y) })) };
    }
    await page.screenshot({ path: `${OUT}/iframe_${c.name}.jpg`, type: 'jpeg', quality: 60 });
  } catch (e) { r.error = e.message.split('\n')[0]; }
  r.errors = [...new Set(log.errors)].slice(0, 6);
  r.failedReq = log.failedReq.slice(0, 6);
  r.warnings = [...new Set(log.warnings)].slice(0, 4);
  results[c.name] = r;
  console.log(c.name, JSON.stringify(r).slice(0, 1600));
  await ctx.close();
  await host.close();
}
writeJSON('iframe_results.json', results);
await browser.close(); await plain.close(); await cors.close();
