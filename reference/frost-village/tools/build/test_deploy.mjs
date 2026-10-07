// Frost Village — deployment tests (GitHub Pages sub-path + claude.ai Artifact host emulation).
//
//   node frost-village/tools/build/build_artifact.mjs        (build dist/artifact first)
//   node frost-village/tools/build/test_deploy.mjs [mode ...] [--quick]
//
// Modes (default: every mode except `sandbox`):
//   pages        serve the whole repo like GitHub Pages (https://<user>.github.io/nurient/) and open
//                /nurient/frost-village/ — proves every URL is relative (no '/...' paths).
//   standalone   dist/artifact wrapped in the host skeleton, opened directly (no frame, no CSP).
//   sandbox      host emulation: wrapper page on origin A embeds origin B in
//                <iframe sandbox="allow-scripts"> (opaque origin) + strict CSP; no CORS headers.
//                WORST CASE, EXPECTED TO FAIL with the normal build (every XHR is blocked) and so
//                not part of the default run; the --inline build is the answer (sandbox-inline).
//   sandbox-cors same, but the file server answers with Access-Control-Allow-Origin: *.
//   sameorigin   same frame + CSP but sandbox="allow-scripts allow-same-origin" (artifact has its
//                own origin, so XHR/fetch to its own files is same-origin and localStorage works).
//   raw          dist/artifact/index.html served as-is (body-only file, quirks mode) e.g. `npx serve`.
//   sandbox-inline  like sandbox (opaque origin, CSP, no CORS) but for the --inline build
//                (dist/artifact_inline): every asset embedded in script packs, no XHR at all.
//
// Every mode: boot -> title -> tap -> village -> first loop (net -> grill -> shelf -> customers pay
// -> cash) -> save + reload check; collects page errors, console errors, failed requests, CSP
// violations, placeholder (missing asset) warnings, audio unlock state. Screenshots go to
// frost-village/dist/deploy_test/<mode>_*.jpg. Exit code 0 = every mode passed.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch, sleep, walkTo } from '../test/pw.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FV = path.resolve(HERE, '..', '..');              // frost-village/
const REPO = path.resolve(FV, '..');                     // repo root (GitHub Pages site root)
const DIST = path.join(FV, 'dist', 'artifact');
const DIST_INLINE = path.join(FV, 'dist', 'artifact_inline');
const SHOTS = path.join(FV, 'dist', 'deploy_test');
fs.mkdirSync(SHOTS, { recursive: true });

const argv = process.argv.slice(2);
const QUICK = argv.includes('--quick');
const ALL = ['pages', 'standalone', 'sandbox', 'sandbox-cors', 'sameorigin', 'raw', 'sandbox-inline'];
const MODES = argv.filter((a) => !a.startsWith('--'));
const run = MODES.length ? MODES : ALL.filter((m) => m !== 'sandbox');

const CSP = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self'; style-src 'self' 'unsafe-inline'";
// What the host wraps the body-only page in (charset + viewport with viewport-fit=cover + small reset).
const SKELETON_HEAD = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px/1.4 system-ui,sans-serif;background:#faf9f7}img{max-width:100%}[hidden]{display:none!important}</style></head><body>\n';
const SKELETON_TAIL = '\n</body></html>';

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg',
  '.css': 'text/css', '.md': 'text/markdown; charset=utf-8', '.webmanifest': 'application/manifest+json', '.svg': 'image/svg+xml',
};

/** small static server. opts: root, prefix, wrapIndex, csp, cors, ghRedirect, requests[] */
function serve(opts) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let u = decodeURIComponent((req.url || '/').split('?')[0]);
      opts.requests && opts.requests.push(u);
      const hdr = { 'cache-control': 'no-store' };
      if (opts.csp) hdr['content-security-policy'] = opts.csp;
      if (opts.cors) hdr['access-control-allow-origin'] = '*';
      if (opts.html) { res.writeHead(200, Object.assign(hdr, { 'content-type': TYPES['.html'] })); res.end(opts.html); return; }
      if (!u.startsWith(opts.prefix)) { res.writeHead(404, hdr); res.end('not found'); return; }
      u = '/' + u.slice(opts.prefix.length);
      let fp = path.join(opts.root, path.normalize(u));
      if (!fp.startsWith(opts.root)) { res.writeHead(403, hdr); res.end(); return; }
      let st = null;
      try { st = fs.statSync(fp); } catch (e) { /* 404 below */ }
      if (st && st.isDirectory()) {
        if (!u.endsWith('/')) { res.writeHead(301, Object.assign(hdr, { location: req.url.split('?')[0] + '/' })); res.end(); return; }  // GitHub Pages behaviour
        fp = path.join(fp, 'index.html');
        try { st = fs.statSync(fp); } catch (e) { st = null; }
      }
      if (!st || !st.isFile()) { res.writeHead(404, Object.assign(hdr, { 'content-type': 'text/plain' })); res.end('not found'); return; }
      const ext = path.extname(fp).toLowerCase();
      if (opts.wrapIndex && path.basename(fp) === 'index.html') {
        const body = SKELETON_HEAD + fs.readFileSync(fp, 'utf8') + SKELETON_TAIL;
        res.writeHead(200, Object.assign(hdr, { 'content-type': TYPES['.html'] })); res.end(body); return;
      }
      res.writeHead(200, Object.assign(hdr, { 'content-type': TYPES[ext] || 'application/octet-stream', 'content-length': st.size }));
      fs.createReadStream(fp).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => resolve({ port: server.address().port, close: () => new Promise((r) => { server.closeAllConnections && server.closeAllConnections(); server.close(r); }) }));
  });
}

const wrapperHtml = (src, sandbox) => `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>host</title><style>html,body{margin:0;height:100%;background:#262624}iframe{border:0;display:block;width:100%;height:100%}</style></head>
<body><iframe id="art" src="${src}" sandbox="${sandbox}" allow="fullscreen; autoplay; clipboard-write"></iframe></body></html>`;

async function testMode(browser, mode) {
  const t0 = Date.now();
  const servers = [];
  const requests = [];
  let url, frameSel = null;
  if (mode === 'pages') {
    const s = await serve({ root: REPO, prefix: '/nurient/', requests }); servers.push(s);
    url = `http://127.0.0.1:${s.port}/nurient/frost-village`;     // no trailing slash on purpose (301 like GitHub Pages)
  } else {
    const dist = mode === 'sandbox-inline' ? DIST_INLINE : DIST;
    if (!fs.existsSync(path.join(dist, 'index.html'))) throw new Error(path.relative(FV, dist) + ' missing: run tools/build/build_artifact.mjs' + (dist === DIST_INLINE ? ' --inline' : '') + ' first');
    const sandboxed = mode.startsWith('sandbox') || mode === 'sameorigin';
    const art = await serve({ root: dist, prefix: '/', wrapIndex: mode !== 'raw', csp: sandboxed ? CSP : null, cors: mode === 'sandbox-cors', requests });
    servers.push(art);
    if (sandboxed) {
      const sb = mode === 'sameorigin' ? 'allow-scripts allow-same-origin' : 'allow-scripts';
      const host = await serve({ html: wrapperHtml(`http://127.0.0.1:${art.port}/index.html`, sb) });   // different port = different origin
      servers.push(host);
      url = `http://localhost:${host.port}/`;
      frameSel = '#art';
    } else url = `http://127.0.0.1:${art.port}/index.html`;
  }

  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'ko-KR' });
  const page = await ctx.newPage();
  const log = { pageErrors: [], consoleErrors: [], warnings: [], failed: [], http: [], csp: [] };
  page.on('pageerror', (e) => log.pageErrors.push(String(e && e.stack ? e.stack.split('\n').slice(0, 9).join(' <- ') : e)));
  page.on('console', (m) => {
    const tx = m.text();
    if (/Content Security Policy|Refused to/i.test(tx)) log.csp.push(tx);
    if (m.type() === 'error') log.consoleErrors.push(tx.slice(0, 300));
    else if (m.type() === 'warning' && !/GPU stall|swiftshader|WebGL|AudioContext was not allowed/i.test(tx)) log.warnings.push(tx.slice(0, 300));
  });
  page.on('requestfailed', (r) => log.failed.push(r.url().replace(/^https?:\/\/[^/]+/, '') + ' ' + (r.failure() && r.failure().errorText)));
  page.on('response', (r) => { if (r.status() >= 400) log.http.push(r.status() + ' ' + r.url().replace(/^https?:\/\/[^/]+/, '')); });

  const results = [];
  const step = (name, ok, info = '') => { results.push({ name, ok, info }); console.log(`  [${mode}] ${ok ? 'ok  ' : 'FAIL'} ${name}${info ? '  — ' + info : ''}`); };
  const shot = (n) => page.screenshot({ path: path.join(SHOTS, `${mode}_${n}.jpg`), type: 'jpeg', quality: 80 }).catch(() => {});

  let F = page;   // the frame the game runs in
  const getFrame = async () => {
    if (!frameSel) return page.mainFrame();
    const h = await page.waitForSelector(frameSel, { timeout: 20000 });
    for (let i = 0; i < 100; i++) { const f = await h.contentFrame(); if (f && f.url().startsWith('http')) return f; await sleep(100); }
    throw new Error('iframe never navigated');
  };
  const ev = (fn, arg) => F.evaluate(fn, arg);
  const waitFor = (fn, timeout, arg) => F.waitForFunction(fn, arg, { timeout, polling: 150 });
  const st = () => ev(() => window.__FV.state());
  const where = (n) => ev((k) => window.__FV.where(k), n);
  const count = (s, type) => s.player.stack.filter((x) => x === type).length;
  const tapCanvas = async (fy = 0.6) => {
    const c = await F.waitForSelector('canvas', { timeout: 20000 });
    const b = await c.boundingBox();            // main-viewport coordinates, also for iframes
    await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height * fy);
  };
  const waitTitle = async () => {
    const t1 = Date.now();
    while (!(await ev(() => !!(window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'))).catch(() => false))) {
      if (log.pageErrors.length) throw new Error('page error before the title screen: ' + log.pageErrors[0].split(' <- ')[0]);
      if (Date.now() - t1 > 120000) throw new Error('title screen not reached in 120 s');
      await sleep(250);
    }
    return Date.now() - t1;
  };
  const startGame = async () => {             // tap the title (retry: a tap during the title intro can be missed)
    for (let i = 0; i < 4; i++) {
      await tapCanvas(0.6);
      const ok = await waitFor(() => window.__FV.state && window.__FV.game.scene.isActive('UI'), 12000).then(() => true, () => false);
      if (ok) return i + 1;
    }
    throw new Error('tap to start did not reach the village');
  };

  let fatal = null;
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    F = await getFrame();
    step('page loaded', true, F.url().replace(/^https?:\/\/[^/]+/, ''));
    const env = await ev(() => {
      let ls = 'ok'; try { window.localStorage.getItem('x'); } catch (e) { ls = 'throws ' + e.name; }
      return { origin: window.origin, ls, compat: document.compatMode, phaser: typeof Phaser !== 'undefined' && Phaser.VERSION };
    });
    step('environment', !!env.phaser, `origin=${env.origin} localStorage=${env.ls} mode=${env.compat} phaser=${env.phaser}`);

    await waitTitle();
    const loadMs = Date.now() - t0;
    await sleep(800);
    await shot('1_title');
    const assets = await ev(() => {
      const g = window.__FV.game;
      const tex = ['char_player', 'props_buildings', 'ui_title_bg', 'ground_snow', 'fx_particles'].filter((k) => !g.textures.exists(k));
      // (village music + ambience are loaded after the title, by the Game scene)
      const aud = ['bgm_title', 'sfx_coin'].filter((k) => !g.cache.audio.exists(k));
      return { missingTex: tex, missingAudio: aud, renderer: g.renderer.type === 2 ? 'WebGL' : 'Canvas', loadingGone: !document.getElementById('fv-loading'), errBox: (document.getElementById('fv-error') || {}).textContent || '' };
    });
    step('title screen + assets loaded', !assets.missingTex.length && !assets.missingAudio.length && assets.loadingGone && !assets.errBox,
      `${(loadMs / 1000).toFixed(1)} s, ${assets.renderer}${assets.missingTex.length ? ', MISSING textures ' + assets.missingTex.join(',') : ''}${assets.missingAudio.length ? ', MISSING audio ' + assets.missingAudio.join(',') : ''}${assets.errBox ? ', error box: ' + assets.errBox : ''}`);

    const taps = await startGame();
    await sleep(1500);
    await shot('2_village');
    let s = await st();
    const audio = await ev(() => { const sm = window.__FV.game.sound; return { locked: sm.locked, ctx: sm.context ? sm.context.state : 'html5', music: !!(sm.sounds || []).find((x) => x.key === 'bgm_village' && x.isPlaying) }; });
    step('tap to start -> village', s.market.queue > 0, `coins=${s.coins} queue=${s.market.queue} taps=${taps}`);
    {
      const ok = await waitFor(() => ['bgm_village', 'amb_wind', 'amb_sea', 'amb_fire'].every((k) => window.__FV.game.cache.audio.exists(k)), 30000).then(() => true).catch(() => false);
      step('village music + ambience loaded after the title', ok);
    }
    step('audio unlocked after tap', !audio.locked && (audio.ctx === 'running' || audio.ctx === 'html5'), JSON.stringify(audio));
    const warned = await ev(() => window.__FV.warnings());
    step('no placeholder art', warned.length === 0, warned.slice(0, 6).join(', '));

    // ---- first loop: net -> grill -> shelf -> customers pay -> cash
    await walkTo(F, await where('net'), { tol: 18, timeout: 15000 });
    await waitFor(() => { const s = window.__FV.state(); return s.player.stack.length >= Math.min(4, s.player.capacity); }, 30000).catch(() => {});
    s = await st();
    step('fishing at the net', count(s, 'item_fish_raw') >= 1, `raw=${count(s, 'item_fish_raw')} anim=${s.player.anim}`);
    if (!QUICK) {
      await walkTo(F, await where('grillIn'), { tol: 18, timeout: 15000 });
      await waitFor(() => window.__FV.state().player.stack.filter((x) => x === 'item_fish_raw').length === 0, 15000).catch(() => {});
      await waitFor(() => { const g = window.__FV.state().stations.grill; return g.in === 0 && g.out > 0; }, 30000).catch(() => {});
      await walkTo(F, await where('grillOut'), { tol: 18, timeout: 15000 });
      await waitFor(() => window.__FV.state().player.stack.some((x) => x === 'item_fish_cooked'), 15000).catch(() => {});
      await sleep(1500);
      s = await st();
      step('grilled fish picked up', count(s, 'item_fish_cooked') > 0, `cooked=${count(s, 'item_fish_cooked')}`);
      await shot('3_carry');
      await walkTo(F, await where('shelf'), { tol: 18, timeout: 15000 });
      await waitFor(() => window.__FV.state().player.stack.length === 0, 15000).catch(() => {});
      await waitFor(() => window.__FV.state().market.cash > 0, 40000).catch(() => {});
      s = await st();
      step('customers paid', s.market.cash > 0, `cash=${s.market.cash} stock=${s.market.stock}`);
      await walkTo(F, await where('cash'), { tol: 18, timeout: 15000 });
      await waitFor(() => window.__FV.state().coins > 0, 15000).catch(() => {});
      await sleep(1200);
      s = await st();
      step('coins collected', s.coins > 0, `coins=${s.coins}`);
      await shot('4_coins');
    }

    // ---- save + reload (persistence only expected where localStorage works)
    const before = (await st()).coins;
    await ev(() => window.__FV.save());
    await page.reload({ waitUntil: 'load' });
    F = await getFrame();
    await waitTitle();
    await sleep(800);
    await startGame();
    await sleep(800);
    const after = (await st()).coins;
    const lsWorks = env.ls === 'ok';
    step('reload', lsWorks ? after === before : true, `coins before=${before} after=${after} (${lsWorks ? 'progress should persist' : 'no localStorage: starts fresh, expected'})`);
  } catch (e) {
    fatal = e;
    step('run', false, String(e.message || e).split('\n')[0]);
    await shot('9_error');
  }

  // CSP noise from the host emulation itself is irrelevant; everything else counts.
  const errs = log.pageErrors.concat(log.consoleErrors);
  step('no page/console errors', errs.length === 0, errs.slice(0, 8).join(' | '));
  step('no failed requests', !log.failed.length && !log.http.length, log.failed.concat(log.http).slice(0, 8).join(' | '));
  if (log.csp.length) console.log(`  [${mode}] CSP: ${log.csp.slice(0, 4).join(' | ')}`);
  if (log.warnings.length) console.log(`  [${mode}] warnings (${log.warnings.length}): ${[...new Set(log.warnings)].slice(0, 6).join(' | ')}`);
  console.log(`  [${mode}] ${requests.length} requests, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  await ctx.close();
  for (const s of servers) await s.close();
  return { mode, ok: !fatal && results.every((r) => r.ok), results, log };
}

const browser = await launch();
const summary = [];
for (const m of run) {
  if (!ALL.includes(m)) { console.log('unknown mode ' + m); continue; }
  console.log(`\n=== ${m}`);
  try { summary.push(await testMode(browser, m)); } catch (e) { console.log(`  [${m}] CRASH ${e.message}`); summary.push({ mode: m, ok: false }); }
}
await browser.close();
console.log('\n=== summary');
for (const r of summary) console.log(`  ${r.ok ? 'PASS' : 'FAIL'}  ${r.mode}`);
console.log(`  screenshots: ${path.relative(process.cwd(), SHOTS)}`);
process.exit(summary.every((r) => r.ok) ? 0 : 1);
