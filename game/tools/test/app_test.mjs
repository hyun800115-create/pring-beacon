// PC 앱(Electron) 시험: 앱을 진짜로 켜서 게임이 뜨는지, 모델·소리 파일을 다 읽는지, 몇 가지 지어 보고,
// 창 크기·F11 전체 화면·바깥 링크 막기·저장(localStorage)이 앱을 껐다 켜도 남는지 확인한다.
//   node tools/test/app_test.mjs [출력폴더] [--dev | --exe <앱.exe> | --portable | --installer] [--show]
//     기본: 저장소/.cache/release/win-unpacked 의 앱(있으면), 없으면 --dev (game/app/pc 의 electron + main.js)
//     --installer: 설치 파일을 설치하지 않고 7-Zip 으로 속만 풀어서(바탕 화면·시작 메뉴를 건드리지 않게) 안의 앱으로 시험
//     창은 화면에 띄우지 않는다 (SM_HIDDEN=1 — 컴퓨터 쓰는 사람을 방해하지 않게). --show 를 주면 보이는 창으로.
//   먼저: node tools/build/build_app.mjs (--www-only 면 --dev 로만 시험)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { _electron as electron } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const REPO = path.resolve(ROOT, '..');
const APP = path.join(ROOT, 'app', 'pc');
const args = process.argv.slice(2);
const OUT = path.resolve(args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--exe') || path.join(REPO, '.cache', 'app-pc', args.includes('--installer') ? 'test-installer' : 'test'));
fs.mkdirSync(OUT, { recursive: true });
const USER = path.join(REPO, '.cache', 'app-pc', 'test-userdata');   // 진짜 저장을 건드리지 않게 시험용 저장 폴더
fs.rmSync(USER, { recursive: true, force: true });

const SHOW = args.includes('--show');
// 앱에 넘겨줄 환경: 숨김 모드
const ENV = Object.assign({}, process.env, SHOW ? {} : { SM_HIDDEN: '1' });
delete ENV.ELECTRON_RUN_AS_NODE;
const REL = path.join(REPO, '.cache', 'release');

let exe = args.includes('--exe') ? path.resolve(args[args.indexOf('--exe') + 1]) : null;
let installerInfo = null;
// ---------------------------------------------------------------- --installer: 설치 파일 속 확인 (설치는 하지 않는다 — 바탕 화면·시작 메뉴·등록 정보를 건드리지 않게)
if (args.includes('--installer')) {
  const { spawnSync } = await import('node:child_process');
  const inst = fs.readdirSync(REL).map((f) => path.join(REL, f)).find((f) => /설치.*\.exe$/.test(f));
  if (!inst) { console.error('[app_test] 설치 파일이 없어요. 먼저 build_app.mjs'); process.exit(1); }
  // 설치 파일 겉(NSIS) 목록은 온전한 7-Zip(7z-x64.exe + dll), 속 앱 풀기는 7za 로
  const zNsis = path.join(APP, 'node_modules', 'electron-winstaller', 'vendor', '7z-x64.exe');
  const z7a = path.join(REPO, '.cache', 'electron-builder', '7zip@1.0.0', '7zip-win-x64-a34pt', 'bin', '7za.exe');
  const zx = [z7a, zNsis].find((f) => fs.existsSync(f));
  if (!zx) { console.error('[app_test] 7-Zip 을 찾지 못했어요'); process.exit(1); }
  const X = path.join(REPO, '.cache', 'app-pc', 'installer-check');
  fs.rmSync(X, { recursive: true, force: true }); fs.mkdirSync(X, { recursive: true });
  const run = (z, a) => spawnSync(z, a, { encoding: 'utf8', windowsHide: true, maxBuffer: 64 << 20 });
  const list = fs.existsSync(zNsis) ? (run(zNsis, ['l', '-tNsis', inst]).stdout || '') : '';
  const appDir = path.join(X, 'app');
  run(zx, ['x', inst, '-o' + appDir, '-y']);   // 설치 파일 안에 묻힌 앱 묶음(7z)을 바로 푼다
  const nested = path.join(appDir, '$PLUGINSDIR', 'app-64.7z');   // (온전한 7-Zip 이 NSIS 겉으로 풀었을 때)
  if (fs.existsSync(nested)) run(zx, ['x', nested, '-o' + appDir, '-y']);
  const has = (rel) => fs.existsSync(path.join(appDir, rel));
  installerInfo = {
    installer: path.basename(inst), mb: +(fs.statSync(inst).size / 1048576).toFixed(1),
    nsis: /Type = Nsis/.test(list), app64: /\$PLUGINSDIR\\app-64\.7z/.test(list), uninstaller: /Uninstall SpringMarch\.exe/.test(list),
    exe: has('SpringMarch.exe'), asar: has('resources/app.asar'), www: has('resources/www/index.html'), game: has('resources/www/game.js'),
    glbs: has('resources/www/assets3d/buildings') ? fs.readdirSync(path.join(appDir, 'resources/www/assets3d/buildings')).filter((f) => f.endsWith('.glb')).length : 0,
  };
  console.log('[app_test] 설치 파일 속:', JSON.stringify(installerInfo));
  if (!installerInfo.exe || !installerInfo.www) { console.error('[app_test] 설치 파일 안에 앱이나 게임 파일이 없어요'); process.exit(1); }
  exe = path.join(appDir, 'SpringMarch.exe');
}
if (!exe && !args.includes('--dev')) {
  const unpacked = path.join(REPO, '.cache', 'release', 'win-unpacked');
  if (fs.existsSync(unpacked)) { const f = fs.readdirSync(unpacked).find((x) => /\.exe$/i.test(x) && !/uninstall/i.test(x)); if (f) exe = path.join(unpacked, f); }
}
const mode = installerInfo ? 'installer' : exe ? 'packed' : 'dev';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);
const errs = [];
let quiet = false;   // 일부러 실패시키는 시험 중에는 오류를 세지 않는다
let closing = false; // 앱을 끄는 중 (그래픽 연결이 먼저 끊겼다는 알림은 끄는 중에는 정상)
const result = { mode, exe: exe || 'electron game/app/pc', hidden: !SHOW, installer: installerInfo, checks: {} };
const check = (name, ok, info) => { result.checks[name] = { ok: !!ok, info }; log(ok ? '  ✔' : '  ✘', name, info !== undefined ? JSON.stringify(info) : ''); };
if (installerInfo) {
  check('설치 파일: NSIS 설치기 + 앱 묶음 + 지우기 프로그램', installerInfo.nsis && installerInfo.app64 && installerInfo.uninstaller, installerInfo);
  check('설치 파일 속 앱·게임 파일', installerInfo.exe && installerInfo.asar && installerInfo.www && installerInfo.game && installerInfo.glbs > 10, installerInfo.glbs);
}

const api = (page, f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);

/** 윈도우에게 직접 물어보기: 이 이름의 프로그램 중 화면에 보이는 창이 있는 것 (숨김 시험 확인용, 파워셸도 창 없이) */
async function visibleWindows(name) {
  const { spawnSync } = await import('node:child_process');
  const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
    `Get-Process -Name '${name}' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | ForEach-Object { "$($_.Id) $($_.MainWindowTitle)" }`],
  { encoding: 'utf8', windowsHide: true });
  return (r.stdout || '').split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
}

// ---------------------------------------------------------------- --portable: 바로 실행판(.exe 하나)을 켜서 게임이 뜨는지 짧게 본다
if (args.includes('--portable')) {
  const rel = path.join(REPO, '.cache', 'release');
  const pexe = fs.readdirSync(rel).map((f) => path.join(rel, f)).find((f) => /바로실행.*\.exe$/.test(f));
  result.mode = 'portable'; result.exe = pexe;
  log(`[app_test] portable: ${pexe}`);
  const { spawn } = await import('node:child_process');
  const { chromium } = await import('playwright');
  const port = 9300 + Math.floor(Math.random() * 500);
  const t0 = Date.now();
  // 바로 실행판은 임시 폴더에 풀고 진짜 앱을 켠다 → 개발자 연결 구멍(포트)으로 붙어서 본다
  const child = spawn(pexe, [`--user-data=${USER}`, `--remote-debugging-port=${port}`], { stdio: 'ignore', env: ENV, windowsHide: true });
  let exited = null; child.on('exit', (c) => { exited = c; });
  let browser = null, page = null;
  try {
    while (!browser && Date.now() - t0 < 120000) { try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`); } catch (e) { await sleep(1000); } }
    if (!browser) throw new Error('바로 실행판이 2분 안에 뜨지 않음');
    while (!page && Date.now() - t0 < 120000) { page = browser.contexts().flatMap((c) => c.pages()).find((x) => x.url().startsWith('app://game/')); if (!page) await sleep(500); }
    page.on('pageerror', (e) => errs.push('pageerror: ' + (e.stack || e)));
    page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 180000 });
    result.bootSec = +((Date.now() - t0) / 1000).toFixed(1);
    check('바로 실행판이 켜지고 게임이 뜸', true, `${result.bootSec}초 (풀기 포함)`);
    if (!SHOW) { const osWins = await visibleWindows('SpringMarch'); check('바로 실행판 창이 화면에 안 보임 (윈도우 확인)', osWins.length === 0, osWins); }
    const st = await api(page, 'start');
    await api(page, 'settle', st.x + 6, st.z - 6, 0.3); await api(page, 'finishAll');
    await sleep(1500);
    const n0 = (await api(page, 'stats')).blds.filter((b) => b.includes('active')).length;
    const h = await api(page, 'hall');
    const built = [];
    for (const [t, dx, dz] of [['house', -9, 3], ['house', -8, -6], ['woodcutter', 10, -4]]) { const sp = await api(page, 'findSpot', t, h.x + dx, h.z + dz, 0); if (sp) { await api(page, 'build', t, sp[0], sp[1], 0); built.push(t); } else log('  자리 없음', t); }
    await api(page, 'finishAll');
    await api(page, 'cam', h.x, h.z + 2, 40, 0.75, 1.0);
    await sleep(4000);
    await page.screenshot({ path: path.join(OUT, 'p1_portable.png') }); log('  shot p1_portable.png');
    { const fpsS = []; for (let i = 0; i < 5; i++) { await sleep(1000); fpsS.push(await page.evaluate(() => window.__SM.game.fps)); } result.fps = Math.round(fpsS.reduce((a, b) => a + b, 0) / fpsS.length); }
    const s = await api(page, 'stats');
    const n1 = s.blds.filter((b) => b.includes('active')).length;
    check('바로 실행판에서 새로 지어짐', built.length >= 2 && n1 >= n0 + built.length, { 전: n0, 후: n1, 지음: built, 목록: s.blds });
    log('  fps', result.fps);
    // 게임 안에서 앱 끄기 (window.smApp.quit) → 바로 실행판도 따라 끝나야 한다
    await page.evaluate(() => window.smApp.quit()).catch(() => {});
    for (let i = 0; i < 40 && exited === null; i++) await sleep(500);
    check('게임 안에서 끄기 → 앱이 끝남', exited !== null, exited);
  } catch (e) { errs.push('test: ' + (e.stack || e)); try { if (page) await page.screenshot({ path: path.join(OUT, 'p_fail.png') }); } catch (e2) { /* */ } }
  if (exited === null) try { child.kill(); } catch (e) { /* */ }
  const bad = Object.entries(result.checks).filter(([, v]) => !v.ok).map(([k]) => k);
  result.errors = errs; result.failed = bad;
  fs.writeFileSync(path.join(OUT, 'result_portable.json'), JSON.stringify(result, null, 2));
  log(`[app_test] portable 확인 ${Object.keys(result.checks).length - bad.length}/${Object.keys(result.checks).length} 통과`, bad.length ? '실패: ' + bad.join(', ') : '');
  log('errors', errs.length ? '\n' + errs.slice(0, 20).join('\n') : 0);
  process.exit(bad.length || errs.length ? 1 : 0);
}

const electronPath = () => createRequire(path.join(APP, 'package.json'))('electron');
async function launch(tag) {
  const opts = exe
    ? { executablePath: exe, args: [`--user-data=${USER}`] }
    : { executablePath: electronPath(), args: [APP, `--user-data=${USER}`], cwd: APP };
  const app = await electron.launch(Object.assign({ timeout: 120000, env: ENV }, opts));
  curApp = app;
  const page = await app.firstWindow({ timeout: 120000 });
  page.on('pageerror', (e) => quiet || errs.push(`[${tag}] pageerror: ` + (e.stack || e)));
  page.on('console', (m) => { if (m.type() === 'error' && !quiet) errs.push(`[${tag}] console: ` + m.text()); });
  app.process().stderr.on('data', (d) => { const s = String(d); if (closing && /GPU state invalid|command_buffer_proxy/i.test(s)) return;
    if (/error/i.test(s) && !/DevTools|Autofill|GPU process|gpu_init|cache_util|disk_cache/i.test(s)) { errs.push(`[${tag}] main: ` + s.trim().slice(0, 300)); log('  [앱 오류 출력]', s.trim().slice(0, 200)); } });
  return { app, page };
}
let curApp = null;
/** 화면 찍기: 보통 방법이 안 되면(숨긴 창) 앱 쪽에서 창 속을 찍는다 */
const shot = async (page, n) => {
  const fp = path.join(OUT, n);
  try {
    await page.screenshot({ path: fp, timeout: 15000 });
  } catch (e) {
    if (!curApp) throw e;
    const b64 = await curApp.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].webContents.capturePage(undefined, { stayHidden: true })).toPNG().toString('base64'));
    fs.writeFileSync(fp, Buffer.from(b64, 'base64'));
    n += ' (앱 쪽에서 찍음)';
  }
  log('  shot', n);
};

/** 저장 팀의 "이어하기?" 창이 뜨면 이어하기를 누른다 (없으면 그냥 넘어감) */
async function passContinue(page, wantContinue) {
  const t0 = Date.now(), clicks = [];
  while (Date.now() - t0 < 180000) {
    const st = await page.evaluate(() => {
      if (window.__SM && window.__SM.api) return 'ready';
      for (const m of document.querySelectorAll('.smsv, .modal')) if (m.offsetParent !== null && m.querySelector('button')) return 'modal:' + m.innerText.replace(/\s+/g, ' ').slice(0, 120);
      return 'wait';
    }).catch(() => 'wait');
    if (st === 'ready') return clicks.length ? clicks : null;
    if (st.startsWith('modal:')) {
      const txt = st.slice(6);
      if (!clicks.length) await shot(page, `a_continue_${wantContinue ? 'yes' : 'no'}.png`);
      const clicked = await page.evaluate((yes) => {
        const bs = [...document.querySelectorAll('.smsv button, .modal button')].filter((x) => x.offsetParent !== null);
        const b = bs.find((x) => (yes ? /이어/ : /지우고|새로|처음/).test(x.textContent)) || bs[yes ? 0 : bs.length - 1];
        if (!b) return null; b.click(); return b.textContent.trim();
      }, wantContinue);
      log('  이어하기 창:', txt, '→ 누름:', clicked);
      await sleep(500);
      if (clicked) clicks.push({ text: txt, clicked });
    }
    await sleep(300);
  }
  throw new Error('게임이 3분 안에 뜨지 않음');
}

let app1, app2, p;
try {
  // ================================================================ 1회차: 켜서 놀아 보기
  log(`[app_test] ${mode}: ${result.exe}`);
  const t0 = Date.now();
  ({ app: app1, page: p } = await launch('1'));
  await p.waitForLoadState('domcontentloaded');
  check('앱 주소', p.url().startsWith('app://game/'), p.url());
  await passContinue(p, false);
  await p.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 180000 });
  result.bootSec = +((Date.now() - t0) / 1000).toFixed(1);
  log('  부팅', result.bootSec, '초');
  const win = await app1.evaluate(({ BrowserWindow, app, screen }) => {
    const w = BrowserWindow.getAllWindows()[0];
    const d = screen.getDisplayMatching(w.getBounds());
    return { display: { id: d.id, size: d.size, scale: d.scaleFactor, hz: d.displayFrequency, primary: d.id === screen.getPrimaryDisplay().id, n: screen.getAllDisplays().length }, bounds: w.getContentBounds(), outer: w.getBounds(), min: w.getMinimumSize(), title: w.getTitle(), menu: w.isMenuBarVisible(), visible: w.isVisible(), userData: app.getPath('userData'), name: app.getName(), version: app.getVersion(), packed: app.isPackaged };
  });
  log('  창', JSON.stringify(win));
  result.window = win;
  check('창 크기 1600x900 (주 모니터)', Math.abs(win.outer.width - 1600) <= 2 && Math.abs(win.outer.height - 900) <= 2 && win.display.primary, win.outer);
  check('최소 크기 1024x600', win.min[0] === 1024 && win.min[1] === 600, win.min);
  check('창 제목', win.title === '봄날의 행진', win.title);
  check('메뉴 줄 없음', !win.menu);
  if (!SHOW) check('창이 화면에 안 보임 (숨김 시험)', !win.visible, win.visible);
  check('시험용 저장 폴더', path.resolve(win.userData) === path.resolve(USER), win.userData);
  check('앱 이름·판', win.name === '봄날의 행진' && win.version === '0.1.0', win.name + ' ' + win.version);

  // 파일 읽기: 모델·소리·그림이 앱 주소로 다 읽히는지 (없는 파일·바깥 경로는 일부러 실패시킨다)
  quiet = true;
  const files = await p.evaluate(async () => {
    const g = window.__SM.game, lib = g.lib;
    const r = {};
    r.chars = Object.keys(lib.chars).length;
    r.props = Object.values(lib.props).filter(Boolean).length;
    r.propsNull = Object.entries(lib.props).filter(([, v]) => !v).map(([k]) => k);
    r.bldIndex = Object.keys(lib.index.buildings).length;
    r.blds = Object.values(lib.blds).filter(Boolean).length;
    const head = async (u) => { try { const x = await fetch(u); const b = new Uint8Array(await x.arrayBuffer()); return { ok: x.ok, status: x.status, n: b.length, type: x.headers.get('content-type'), magic: String.fromCharCode(...b.slice(0, 4)) }; } catch (e) { return { ok: false, err: String(e) }; } };
    r.glb = await head('assets3d/buildings/hall.glb');
    r.mp3 = await head('assets/audio/sfx_click.mp3');
    r.json = await head('assets3d/props/index.json');
    r.png = await head('assets/ground/ground_snow.png');
    r.miss = await head('assets/없는파일.png');
    r.escape = await head('../../main.js');
    // 잘못된 %글자가 든 주소 → 앱 쪽 오류 없이 400 '잘못된 주소'
    r.bad1 = await head('app://game/%E0%A4%A.png');
    r.bad2 = await head('assets/%ZZ.png');
    r.audio = Object.keys((g.audio && g.audio.buf) || {}).length;
    r.wasm = typeof WebAssembly === 'object';
    r.bridge = !!(window.smApp && window.smApp.pc);
    return r;
  });
  await sleep(300); quiet = false;
  check('앱 다리(window.smApp)', files.bridge);
  log('  파일', JSON.stringify(files));
  check('주민 모델', files.chars >= 10, files.chars);
  // 원본에도 없는 이름(예: 일부러 비워 둔 'season_hidden')은 묶기 문제가 아니므로 빼고 본다
  const propsLost = files.propsNull.filter((k) => fs.existsSync(path.join(ROOT, 'assets3d', 'props', k + '.glb')));
  check('소품 모델 (빠진 것 없음)', files.props > 20 && propsLost.length === 0, { n: files.props, missing: propsLost, 원본에도없음: files.propsNull.filter((k) => !propsLost.includes(k)) });
  check('건물 모델 전부', files.blds === files.bldIndex && files.blds > 0, `${files.blds}/${files.bldIndex}`);
  check('GLB 읽기', files.glb.ok && files.glb.magic === 'glTF', files.glb);
  check('소리 읽기', files.mp3.ok && files.mp3.n > 1000 && /audio/.test(files.mp3.type), files.mp3);
  check('없는 파일은 404', !files.miss.ok);
  check('www 밖으로 못 나감', !files.escape.ok || files.escape.n === 0, files.escape);
  check('잘못된 %글자 주소는 400 (앱 오류 없음)', files.bad1.status === 400 && files.bad2.status === 400, { a: files.bad1.status || files.bad1.err, b: files.bad2.status || files.bad2.err });

  // ---------------------------------------------------------------- 놀아 보기
  const st = await api(p, 'start');
  await api(p, 'settle', st.x + 6, st.z - 6, 0.3);
  await api(p, 'finishAll');
  await sleep(1500);
  const h = await api(p, 'hall');
  const built = [];
  for (const [t, dx, dz, rot] of [['house', -9, 3, 0], ['house', -8, -6, 0.4], ['woodcutter', 10, -4, 0], ['farm', -2, 13, 0], ['bakery', 9, 8, -0.3], ['well', 3, 6, 0]]) {
    const sp = await api(p, 'findSpot', t, h.x + dx, h.z + dz, rot);
    if (!sp) { log('  자리 없음', t); continue; }
    const r = await api(p, 'build', t, sp[0], sp[1], rot);
    built.push(t + (typeof r === 'string' ? ':' + r : ''));
  }
  log('  지음', built.join(', '));
  await api(p, 'road', [[h.x, h.z + 4], [h.x - 5, h.z + 6], [h.x - 9, h.z + 8]]);
  await api(p, 'road', [[h.x + 2, h.z + 4], [h.x + 8, h.z + 5]], 'gravel');
  await api(p, 'finishAll');
  await api(p, 'speed', 2);
  await sleep(6000);
  await api(p, 'speed', 1);
  await api(p, 'cam', h.x, h.z + 2, 46, 0.75, 1.0);
  await sleep(2500);
  await shot(p, 'a1_village.png');
  await api(p, 'cam', h.x - 4, h.z + 3, 22, 0.5, 0.75);
  await sleep(2500);
  await shot(p, 'a2_close.png');
  // 초당 화면 수 (안정된 뒤 몇 번 재서 평균)
  const fpsS = [];
  for (let i = 0; i < 6; i++) { await sleep(1000); fpsS.push(await p.evaluate(() => window.__SM.game.fps)); }
  result.fps = Math.round(fpsS.reduce((a, b) => a + b, 0) / fpsS.length);
  const stats = await api(p, 'stats');
  result.stats = { people: stats.people, blds: stats.blds.length, draws: stats.draws, tris: stats.tris };
  log('  fps', result.fps, JSON.stringify(result.stats));
  check('건물이 지어짐', stats.blds.filter((b) => b.includes('active')).length >= 4, stats.blds);
  check('주민', stats.people > 0, stats.people);
  const gpu = await p.evaluate(() => { const gl = window.__SM.game.stage.renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); });
  result.gpu = gpu; log('  그래픽', gpu);

  // ---------------------------------------------------------------- F11 전체 화면
  const w0 = await p.evaluate(() => [innerWidth, innerHeight]);
  await p.keyboard.press('F11');
  let w1 = w0;
  for (let i = 0; i < 25 && w1[0] === w0[0]; i++) { await sleep(200); w1 = await p.evaluate(() => [innerWidth, innerHeight, window.__SM.game.stage.renderer.domElement.clientWidth]); }
  await sleep(800);
  w1 = await p.evaluate(() => [innerWidth, innerHeight, window.__SM.game.stage.renderer.domElement.clientWidth]);
  const fs1 = await app1.evaluate(({ BrowserWindow }) => global.smIsFullScreen(BrowserWindow.getAllWindows()[0]));
  if (fs1) await shot(p, 'a3_fullscreen.png');
  await p.keyboard.press('F11'); await sleep(2000);
  const fs2 = await app1.evaluate(({ BrowserWindow }) => global.smIsFullScreen(BrowserWindow.getAllWindows()[0]));
  const w2 = await p.evaluate(() => [innerWidth, innerHeight]);
  check('F11 전체 화면 켜기/끄기', fs1 && !fs2, { on: fs1, off: fs2, size: [w0, w1, w2] });
  check('전체 화면에서 게임 화면도 커짐', w1[0] > w0[0] && w1[2] === w1[0] && w2[0] === w0[0], { 창: w0, 전체: w1, 다시: w2 });
  // 소리: 키를 누르면 소리가 풀린다 → 소리 파일을 다 읽고 풀었는지
  await p.keyboard.press('KeyA');
  let nAudio = 0;
  for (let i = 0; i < 20 && nAudio < 13; i++) { await sleep(300); nAudio = await p.evaluate(() => Object.keys(window.__SM.game.audio.buf).length); }
  check('소리 파일 풀기 (배경음+효과음 13개)', nAudio >= 13, nAudio);

  // ---------------------------------------------------------------- 좁은 창: 가장 작게(1024x600)·노트북 배율(1097, 1152, 1280)로 줄여도
  // 위쪽 막대 버튼이 화면 안에 있고, 창고 칸은 한두 줄, 아래 분류 칸 글자는 한 줄
  {
    const topLook = () => p.evaluate(() => {
      const vw = innerWidth;
      const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
      const off = [...document.querySelectorAll('#hud .top button, #hud .top .right > *')].filter(vis)
        .filter((e) => { const b = e.getBoundingClientRect(); return b.right > vw + 1 || b.left < -1; }).map((e) => e.textContent.trim().slice(0, 12));
      const stock = document.querySelector('#hud .stock'), chip = document.querySelector('#hud .stock .chip');
      const cats = [...document.querySelectorAll('#hud .cat')].filter(vis);
      const dock = document.querySelector('#hud .dock').getBoundingClientRect();
      return {
        vw, vh: innerHeight, off: [...new Set(off)],
        stockH: stock ? Math.round(stock.getBoundingClientRect().height) : 0, chipH: chip ? Math.round(chip.getBoundingClientRect().height) : 0,
        catH: Math.round(Math.max(0, ...cats.map((e) => e.getBoundingClientRect().height))), nCats: cats.length,
        dockIn: dock.left >= -1 && dock.right <= vw + 1,
      };
    });
    const b0 = await app1.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].getBounds());
    const wide = await topLook();
    const narrow = [];
    for (const [ww, hh] of [[500, 300], [1097, 617], [1152, 700], [1280, 720]]) {
      await app1.evaluate(({ BrowserWindow }, [a, b]) => BrowserWindow.getAllWindows()[0].setContentSize(a, b), [ww, hh]);
      let m = null;
      for (let i = 0; i < 15; i++) { await sleep(200); m = await topLook(); if (ww < 1024 ? m.vw === 1024 : m.vw === ww) break; }
      await sleep(500); m = await topLook();
      m.want = [ww, hh];
      m.ok = m.off.length === 0 && m.dockIn && m.catH <= wide.catH + 2 && (!m.chipH || m.stockH <= m.chipH * 2 + 16);
      narrow.push(m);
      if (ww === 500) await shot(p, 'a5_min_size.png');
      if (ww === 1152) await shot(p, 'a6_width_1152.png');
    }
    await app1.evaluate(({ BrowserWindow }, b) => BrowserWindow.getAllWindows()[0].setBounds(b), b0);
    for (let i = 0; i < 15; i++) { await sleep(200); if ((await p.evaluate(() => innerWidth)) === wide.vw) break; }
    await sleep(500);
    result.narrow = { wide, narrow };
    check('가장 작은 창은 1024x600 에서 막힘', narrow[0].vw === 1024 && narrow[0].vh === 600, [narrow[0].vw, narrow[0].vh]);
    check('좁은 창에서도 위쪽 버튼이 화면 안·창고 칸 한두 줄·분류 칸 한 줄', narrow.every((m) => m.ok),
      narrow.map((m) => ({ 폭: m.vw, 밖: m.off, 창고높이: m.stockH, 분류높이: m.catH, 아래칸안: m.dockIn })));
  }

  // ---------------------------------------------------------------- 바깥 링크: 새 창 대신 기본 브라우저로 (시험에서는 진짜로 열지 않게 가로챔)
  const stub = await app1.evaluate(({ shell }) => { try { global.__opened = []; shell.openExternal = async (u) => { global.__opened.push(u); }; return String(shell.openExternal).includes('__opened'); } catch (e) { return false; } });
  if (stub) {
    quiet = true;
    await p.evaluate(() => { window.open('https://example.com/a', '_blank'); const a = document.createElement('a'); a.href = 'https://example.com/b'; a.target = '_blank'; document.body.appendChild(a); a.click(); a.remove(); window.open('file:///C:/Windows/notepad.exe'); });
    await sleep(800);
    const ext = await app1.evaluate(({ BrowserWindow }) => ({ wins: BrowserWindow.getAllWindows().length, opened: global.__opened }));
    check('바깥 링크는 브라우저로, 새 창 없음, file 은 막음', ext.wins === 1 && ext.opened.length === 2 && ext.opened.every((u) => u.startsWith('https://')), ext);
    const nav = await p.evaluate(() => { location.href = 'https://example.com/c'; return true; }).catch(() => 'err');
    await sleep(800);
    quiet = false;
    check('게임 창은 바깥 주소로 이동 안 함', p.url().startsWith('app://game/'), { url: p.url(), nav });
  } else log('  (바깥 링크 시험 건너뜀: 가로채기 실패)');

  // ---------------------------------------------------------------- 같은 앱을 한 번 더 켜면: 새 창 없이 바로 꺼지고, 켜져 있던 창이 앞으로
  {
    const { spawn } = await import('node:child_process');
    const cmd = exe || electronPath();
    const ch = spawn(cmd, exe ? [`--user-data=${USER}`] : [APP, `--user-data=${USER}`], { stdio: 'ignore', env: ENV, windowsHide: true });
    const code = await new Promise((res) => { const t = setTimeout(() => { try { ch.kill(); } catch (e) { /* */ } res('timeout'); }, 20000); ch.on('exit', (c) => { clearTimeout(t); res(c); }); });
    const wins = await app1.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length);
    check('두 번 켜도 창은 하나 (저장 엉킴 방지)', code !== 'timeout' && wins === 1, { 두번째: code, 창: wins });
  }
  // 전체 화면 켜고 끄기·두 번 켜기를 거친 뒤에도 창이 화면에 나오지 않았는지
  if (!SHOW) {
    const vis = await app1.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().map((w) => w.isVisible()));
    check('시험 내내 창이 화면에 안 나옴', vis.every((v) => !v), vis);
    const osWins = await visibleWindows(exe ? path.basename(exe, '.exe') : 'electron');
    check('윈도우가 봐도 화면에 보이는 게임 창 없음', osWins.length === 0, osWins);
  }

  // ---------------------------------------------------------------- 저장: 시험 값을 쓰고 앱 끄기
  const mark = { n: 42, t: Date.now(), txt: '봄날의 행진 저장 시험' };
  await p.evaluate((m) => localStorage.setItem('sm_app_test', JSON.stringify(m)), mark);
  result.keys1 = await p.evaluate(() => Object.keys(localStorage));
  log('  저장 칸', JSON.stringify(result.keys1));
  // 저장 팀이 만든 저장이 있으면 지금 한 번 저장해 둔다 (훅이 있을 때만)
  result.gameSave = await p.evaluate(async () => { const a = window.__SM.api; for (const k of ['save', 'saveNow', 'saveGame']) if (typeof a[k] === 'function') { try { await a[k](); return k; } catch (e) { return k + ':' + e; } } return null; });
  log('  게임 저장 훅', result.gameSave);
  // 저장한 뒤에 하나 더 지어 두고 그냥 창을 닫는다 → 닫을 때 자동 저장되면 다음에 이 건물도 있어야 한다
  let nBlds1 = null;
  if (result.gameSave) {
    const sp = await api(p, 'findSpot', 'house', h.x + 14, h.z - 12, 0);
    if (sp) { await api(p, 'build', 'house', sp[0], sp[1], 0); await api(p, 'finishAll'); }
    await sleep(800);
    nBlds1 = (await api(p, 'stats')).blds.length;
    log('  닫기 전 건물 수', nBlds1);
  }
  await sleep(500);
  closing = true; await app1.close(); app1 = null; await sleep(1000); closing = false;
  log('  앱 끔');
  check('창 크기·위치 기억 파일', fs.existsSync(path.join(USER, 'window.json')), fs.existsSync(path.join(USER, 'window.json')) ? JSON.parse(fs.readFileSync(path.join(USER, 'window.json'), 'utf8')) : null);

  // ================================================================ 2회차: 다시 켜서 저장 확인
  ({ app: app2, page: p } = await launch('2'));
  await p.waitForLoadState('domcontentloaded');
  const back = await p.evaluate(() => localStorage.getItem('sm_app_test'));
  check('앱을 다시 켜도 저장이 남음', back && JSON.parse(back).t === mark.t && JSON.parse(back).txt === mark.txt, back);
  result.keys2 = await p.evaluate(() => Object.keys(localStorage));
  const cont = await passContinue(p, true);
  result.continueDialog = cont;
  await p.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 180000 });
  await sleep(3000);
  const st2 = await api(p, 'stats');
  result.after = { people: st2.people, blds: st2.blds.length, day: st2.day };
  log('  다시 켠 뒤', JSON.stringify(result.after), cont ? '(이어하기)' : '(새 게임)');
  if (cont) check('이어하기로 마을이 돌아옴', st2.blds.length >= 4 && st2.people > 0, result.after);
  if (cont && nBlds1 != null) check('창을 닫을 때 자동 저장 (마지막 건물까지)', st2.blds.length === nBlds1, { 닫기전: nBlds1, 다시켬: st2.blds.length });
  const h2 = await api(p, 'hall');
  if (h2) await api(p, 'cam', h2.x, h2.z + 2, 46, 0.75, 1.0);
  await sleep(2500);
  await shot(p, 'a4_relaunch.png');
} catch (e) {
  errs.push('test: ' + (e.stack || e));
  try { if (p) await p.screenshot({ path: path.join(OUT, 'fail.png') }); } catch (e2) { /* */ }
}
closing = true;
for (const a of [app1, app2]) if (a) try { await a.close(); } catch (e) { /* */ }
result.errors = errs;
const bad = Object.entries(result.checks).filter(([, v]) => !v.ok).map(([k]) => k);
result.failed = bad;
fs.writeFileSync(path.join(OUT, `result_${mode}.json`), JSON.stringify(result, null, 2));
log(`[app_test] ${mode} 확인 ${Object.keys(result.checks).length - bad.length}/${Object.keys(result.checks).length} 통과`, bad.length ? '실패: ' + bad.join(', ') : '');
log('errors', errs.length ? '\n' + errs.slice(0, 30).join('\n') : 0);
process.exit(bad.length || errs.length ? 1 : 0);
