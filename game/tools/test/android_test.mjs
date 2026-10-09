// 안드로이드 앱 시험
//   cd game && PLAYWRIGHT_BROWSERS_PATH=../.cache/pw-browsers node tools/test/android_test.mjs [출력폴더] [--no-apk] [--no-web] [--swiftshader]
//   (창은 절대 띄우지 않는다: 숨은 크롬 + 진짜 그래픽카드 = pw.mjs 의 launchGpu)
// 1) APK 검사: 패키지 이름·앱 이름·SDK 버전·가로 화면·서명, APK 안에 게임 파일이 다 들어 있는지
// 2) www(휴대폰 안 게임 묶음)를 작은 서버로 열어 휴대폰 화면(844x390, 터치, 배율 3)으로 실제 플레이:
//    켜지는지, 정착·건설, 한 손가락 끌기(이동)·두 손가락 벌리기(확대), 저장소(localStorage) 유지, .glb 받기, 스크린샷,
//    휴대폰 배치(자원 14가지 모두 보임·분류 탭 한 줄·건물 값 보임·카드가 열리면 도구 막대 접기), 손가락 짓기(미리 보기 → 땅 누르기는 옮기기만 → ⟲ → ✔ 짓기)
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import zlib from 'node:zlib';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadPlaywright, launchGpu } from './pw.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GAME = path.resolve(HERE, '..', '..');
const REPO = path.resolve(GAME, '..');
const WWW = path.join(GAME, 'app', 'android', 'www');
const REL = path.join(REPO, '.cache', 'release');
const SDK = path.join(REPO, '.cache', 'android-sdk');
const argv = process.argv.slice(2);
const OUT = path.resolve(argv.find((a) => !a.startsWith('--')) || path.join(REPO, '.cache', 'shots', 'android'));
fs.mkdirSync(OUT, { recursive: true });
const flag = (f) => argv.includes(f);
let fails = 0;
const ok = (cond, msg) => { console.log((cond ? '  통과 ' : '  실패 ') + msg); if (!cond) fails++; return cond; };
const mb = (n) => (n / 1048576).toFixed(1) + 'MB';

// ------------------------------------------------------------------ zip(APK) 목록 읽기 (도구 없이)
function zipList(file) {
  const b = fs.readFileSync(file);
  let e = b.length - 22;
  while (e >= 0 && b.readUInt32LE(e) !== 0x06054b50) e--;
  const n = b.readUInt16LE(e + 10); let p = b.readUInt32LE(e + 16);
  const out = [];
  for (let i = 0; i < n; i++) {
    const method = b.readUInt16LE(p + 10), csize = b.readUInt32LE(p + 20), size = b.readUInt32LE(p + 24);
    const nl = b.readUInt16LE(p + 28), xl = b.readUInt16LE(p + 30), cl = b.readUInt16LE(p + 32), off = b.readUInt32LE(p + 42);
    out.push({ name: b.toString('utf8', p + 46, p + 46 + nl), method, csize, size, off });
    p += 46 + nl + xl + cl;
  }
  const read = (ent) => {   // 파일 하나 꺼내기
    const nl = b.readUInt16LE(ent.off + 26), xl = b.readUInt16LE(ent.off + 28), s = ent.off + 30 + nl + xl;
    const raw = b.subarray(s, s + ent.csize);
    return ent.method === 8 ? zlib.inflateRawSync(raw) : raw;
  };
  return { list: out, read };
}

function buildTools() {
  const d = path.join(SDK, 'build-tools');
  if (!fs.existsSync(d)) return null;
  const v = fs.readdirSync(d).sort().pop();
  return path.join(d, v);
}

function checkApk() {
  console.log('\n[APK 검사]');
  // .cache/release/ 바로 아래가 기본, 없으면 보관용 .cache/release/android/ 에서 찾는다
  const found = new Map();
  for (const d of [path.join(REL, 'android'), REL]) if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) if (f.endsWith('.apk')) found.set(f, path.join(d, f));
  const apks = [...found.keys()].sort();
  if (!ok(apks.length > 0, 'APK 파일이 있다: ' + (apks.map((f) => path.relative(REL, found.get(f))).join(', ') || '없음'))) return;
  const bt = buildTools();
  for (const f of apks) {
    const apk = found.get(f);
    console.log(`\n ${f} (${mb(fs.statSync(apk).size)})`);
    if (bt) {
      const r = spawnSync(path.join(bt, 'aapt2.exe'), ['dump', 'badging', apk], { encoding: 'utf8', windowsHide: true });
      const s = r.stdout || '';
      fs.writeFileSync(path.join(OUT, f + '.badging.txt'), s);
      const pkg = (s.match(/package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'/) || []);
      ok(pkg[1] === 'kr.springmarch.game', `패키지 이름 ${pkg[1]} (버전 ${pkg[3]}, 번호 ${pkg[2]})`);
      const label = (s.match(/application-label:'([^']*)'/) || [])[1];
      ok(label === '봄날의 행진', `앱 이름 "${label}"`);
      const min = (s.match(/minSdkVersion:'(\d+)'/) || [])[1], tgt = (s.match(/targetSdkVersion:'(\d+)'/) || [])[1];
      ok(Number(min) >= 21 && Number(tgt) >= 34, `SDK 최소 ${min} / 목표 ${tgt}`);
      ok(/android\.hardware\.screen\.landscape/.test(s), '가로 화면 전용(screen.landscape)');
      ok(/launchable-activity: name='kr\.springmarch\.game\.MainActivity'/.test(s), '시작 화면 MainActivity');
      ok(/application-icon-\d+:'[^']+'/.test(s), '앱 아이콘 있음');
      const x = spawnSync(path.join(bt, 'aapt2.exe'), ['dump', 'xmltree', '--file', 'AndroidManifest.xml', apk], { encoding: 'utf8', windowsHide: true }).stdout || '';
      ok(/screenOrientation\(0x0101001e\)=6/.test(x), '화면 방향 = sensorLandscape(가로, 뒤집기 허용)');
      ok(/hardwareAccelerated\(0x010102d3\)=(true|\(type 0x12\)0xffffffff)/.test(x), '하드웨어 가속 켜짐');
      ok(!/usesCleartextTraffic\(0x010104ec\)=(true|\(type 0x12\)0xffffffff)/.test(x), '암호 없는 인터넷 연결(http) 꺼짐');
      // 서명 (apksigner 를 자바로 직접 돌린다 — .bat 은 한글 경로에서 깨짐)
      const sig = spawnSync(path.join(REPO, '.cache', 'jdk', 'bin', 'java.exe'), ['-jar', path.join(bt, 'lib', 'apksigner.jar'), 'verify', '--print-certs', apk], { encoding: 'utf8', windowsHide: true });
      const cn = ((sig.stdout || '').match(/certificate DN: (.*)/) || [])[1];
      ok(sig.status === 0, `서명 확인됨: ${cn || (sig.stderr || '').trim().split('\n')[0]}`);
      if (f.includes('release')) ok(/Spring March/.test(cn || ''), '출시용은 우리 열쇠(Spring March)로 서명됨');
    }
    // 안에 든 게임 파일
    const z = zipList(apk);
    const pub = z.list.filter((e) => e.name.startsWith('assets/public/'));
    const glb = pub.filter((e) => e.name.endsWith('.glb'));
    const has = (n) => pub.some((e) => e.name === 'assets/public/' + n);
    ok(has('index.html') && has('game.js'), `index.html·game.js 들어 있음 (게임 파일 ${pub.length}개, 풀면 ${mb(pub.reduce((a, e) => a + e.size, 0))})`);
    ok(glb.length > 50, `3D 모델 ${glb.length}개 (주민 ${glb.filter((e) => e.name.includes('/chars/')).length}, 소품 ${glb.filter((e) => e.name.includes('/props/')).length}, 건물 ${glb.filter((e) => e.name.includes('/buildings/')).length})`);
    ok(has('assets3d/props/index.json') && has('assets3d/buildings/index.json'), '모델 목록 파일(index.json) 들어 있음');
    ok(pub.some((e) => e.name.includes('assets/audio/') && e.name.endsWith('.ogg')), `소리 ${pub.filter((e) => e.name.includes('/audio/')).length}개`);
    ok(has('assets/ground/ground_snow.png') && has('assets/emotes/emotes.png'), '땅·감정 그림 들어 있음');
    // www 와 같은지 (최신 묶음이 들어갔는지)
    if (fs.existsSync(path.join(WWW, 'game.js'))) {
      const inApk = z.read(z.list.find((e) => e.name === 'assets/public/game.js'));
      ok(inApk.equals(fs.readFileSync(path.join(WWW, 'game.js'))), 'APK 안 game.js = 지금 www/game.js');
    }
    const html = z.read(z.list.find((e) => e.name === 'assets/public/index.html')).toString('utf8');
    ok(/^<!doctype html>/i.test(html.trim()) && /viewport-fit=cover/.test(html) && !/importmap/.test(html), 'index.html: 완전한 문서, viewport-fit=cover, 가져오기 지도 없음');
    const cfg = z.list.find((e) => e.name === 'assets/capacitor.config.json');
    if (ok(!!cfg, 'capacitor.config.json 들어 있음')) {
      const c = JSON.parse(z.read(cfg).toString('utf8'));
      ok(c.appId === 'kr.springmarch.game' && c.server && c.server.androidScheme === 'https' && c.android && c.android.allowMixedContent === false, `설정: ${c.appId}, https, 섞인 연결 막음`);
    }
    // 출시용은 자원 이름이 짧게 바뀌므로 그림 개수로 본다 (아이콘 자체는 위 badging 에서 확인)
    const pngs = z.list.filter((e) => /^res\/.*\.png$/.test(e.name)).length;
    ok(pngs >= 15, `그림 자원 ${pngs}개 (아이콘·첫 화면)`);
  }
}

// ------------------------------------------------------------------ www 를 휴대폰 화면으로 시험
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg', '.glb': 'model/gltf-binary', '.css': 'text/css' };
function serve(root) {
  return new Promise((res) => {
    const s = http.createServer((q, r) => {
      let u = decodeURIComponent(q.url.split('?')[0]); if (u.endsWith('/')) u += 'index.html';
      const f = path.join(root, path.normalize(u));
      if (!f.startsWith(root) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { r.writeHead(404); r.end(); return; }
      r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream', 'content-length': fs.statSync(f).size });
      fs.createReadStream(f).pipe(r);
    });
    s.listen(0, '127.0.0.1', () => res({ url: `http://127.0.0.1:${s.address().port}/`, close: () => new Promise((r) => s.close(r)) }));
  });
}

async function webTest() {
  console.log('\n[휴대폰 화면 시험 — www]');
  if (!ok(fs.existsSync(path.join(WWW, 'index.html')), 'www/index.html 있음 (없으면: node tools/build/build_android.mjs --web-only)')) return;
  const srv = await serve(WWW);
  // 창을 띄우지 않는다 (대표님 화면을 가리지 않게). 기본은 진짜 그래픽카드(D3D11)를 쓰는 숨은 크롬,
  // --swiftshader 를 주면 그래픽카드 없이 소프트웨어로 그린다 (느림, 그래픽카드 없는 PC 용)
  const b = flag('--swiftshader')
    ? await loadPlaywright().chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
    : await launchGpu();
  const ctx = await b.newContext({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; SM-S911N Build/UP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36' });
  const page = await ctx.newPage();
  const errs = [], bad = [];
  page.on('pageerror', (e) => errs.push(String(e.stack || e)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  page.on('response', (r) => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url()); });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const api = (f, ...a) => page.evaluate(([f2, a2]) => window.__SM.api[f2](...a2), [f, a]);
  try {
    const t0 = Date.now();
    await page.goto(srv.url + 'index.html');
    await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 240000 });
    ok(true, `게임이 켜짐 (${((Date.now() - t0) / 1000).toFixed(1)}초, window.__SM.api 있음)`);
    const info = await page.evaluate(() => ({ w: innerWidth, h: innerHeight, dpr: devicePixelRatio, gl: !!window.__SM.game.stage.renderer.getContext(), app: !!window.__smApp, rotate: getComputedStyle(document.getElementById('sm-rotate')).display }));
    ok(info.w === 844 && info.h === 390 && info.gl, `화면 ${info.w}x${info.h} 배율 ${info.dpr}, WebGL 켜짐`);
    ok(info.app, '앱 도우미(소리 멈춤·저장 신호) 들어 있음');
    ok(info.rotate === 'none', '가로 화면에서는 "돌려 주세요" 안내가 숨겨짐');
    // .glb 받기 (앱 안 서버처럼 model/gltf-binary)
    const g = await page.evaluate(async () => { const r = await fetch('assets3d/chars/' + Object.keys(window.__SM.game.lib.chars)[0] + '.glb'); const ab = await r.arrayBuffer(); return { ok: r.ok, magic: new TextDecoder().decode(new Uint8Array(ab, 0, 4)), type: r.headers.get('content-type') }; });
    ok(g.ok && g.magic === 'glTF', `.glb 받기: ${g.magic} (${g.type})`);
    await page.screenshot({ path: path.join(OUT, 'a1_start.png') });

    // 정착: 손가락으로 (앱 보정: 미리 보기 → 자리 누르기 → ✔ 짓기)
    const st = await api('start');
    const s0 = await page.evaluate(() => { const g = window.__SM.game; return { mode: g.mode, ghost: !!(g.ghost && g.ghost.visible), ok: !!document.querySelector('#hud .placebar button[data-a=ok]'), prompt: document.querySelector('#hud .prompt').textContent }; });
    ok(s0.mode === 'settle' && s0.ghost && s0.ok, `정착 화면: 누르기 전부터 마을회관 미리 보기가 보이고 ✔ 짓기 단추가 있음 (${s0.prompt})`);
    ok(!/Q·E/.test(s0.prompt), '정착 안내에 키보드(Q·E) 이야기가 없음');
    const sp0 = await page.evaluate(([x, z]) => window.__SM.game.stage.toScreen(x + 6, 0, z - 6), [st.x, st.z]);
    await page.touchscreen.tap(sp0.x, sp0.y); await sleep(500);
    const t1 = await page.evaluate(() => ({ mode: window.__SM.game.mode, hall: !!window.__SM.game.world.hall }));
    ok(t1.mode === 'settle' && !t1.hall, '땅을 한 번 누르면 미리 보기만 옮겨지고 아직 짓지 않음');
    const okBtn = async () => { const e = await page.$('#hud .placebar button[data-a=ok]'); if (!e) return false; const bb = await e.boundingBox(); await page.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2); return true; };
    await okBtn(); await sleep(800);
    const t2 = await page.evaluate(() => ({ mode: window.__SM.game.mode, hall: !!window.__SM.game.world.hall }));
    ok(t2.hall && t2.mode === 'view', '✔ 짓기를 누르면 마을회관 공사 시작');
    if (!t2.hall) { await page.evaluate(() => window.__SM.game.setMode('view')); await api('settle', st.x + 6, st.z - 6, 0.3); }
    await api('finishAll');
    await sleep(1500);   // 마을 온기(영토)는 다음 화면 몇 장 뒤에 계산된다
    const h = await api('hall');
    ok(!!h, '정착: 마을회관 지음');
    let built = 0;
    for (const [t, dx, dz] of [['house', -9, 3], ['house', -8, -6], ['woodcutter', 12, -6], ['farm', -4, 14], ['bakery', 14, 6]]) {
      const sp = await api('findSpot', t, h.x + dx, h.z + dz, 0);
      if (!sp) { console.log('  참고: 빈자리 없음', t); continue; }
      const r = await api('build', t, sp[0], sp[1], 0);
      if (typeof r !== 'string') built++; else console.log('  참고: 못 지음', t, r);
    }
    await api('finishAll');
    const s1 = await api('stats');
    ok(built >= 4, `건물 ${built}개 지음 → ${s1.blds.length}채, 주민 ${s1.people}명`);
    await api('cam', h.x, h.z, 34, 0.8, 0.85);
    await sleep(4000);
    await page.screenshot({ path: path.join(OUT, 'a2_village.png') });

    // 터치: 한 손가락 끌기(화면 이동), 두 손가락 벌리기(확대), 두 손가락 비틀기(회전)
    const cdp = await ctx.newCDPSession(page);
    const touch = async (type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y], i) => ({ x, y, id: i + 1, radiusX: 4, radiusY: 4, force: 1 })) });
    const goal = () => page.evaluate(() => { const g = window.__SM.game.stage.goal; return { tx: g.tx, tz: g.tz, dist: g.dist, yaw: g.yaw }; });
    const g0 = await goal();
    await touch('touchStart', [[420, 200]]);
    for (let i = 1; i <= 12; i++) { await touch('touchMove', [[420 - i * 15, 200 - i * 6]]); await sleep(16); }
    await touch('touchEnd', []);
    await sleep(300);
    const g1 = await goal();
    ok(Math.hypot(g1.tx - g0.tx, g1.tz - g0.tz) > 1, `한 손가락 끌기로 화면 이동 (${Math.hypot(g1.tx - g0.tx, g1.tz - g0.tz).toFixed(1)}m)`);
    await touch('touchStart', [[380, 200], [460, 200]]);
    for (let i = 1; i <= 12; i++) { await touch('touchMove', [[380 - i * 10, 200], [460 + i * 10, 200]]); await sleep(16); }
    await touch('touchEnd', []);
    await sleep(300);
    const g2 = await goal();
    ok(g2.dist < g1.dist * 0.8, `두 손가락 벌리기로 확대 (거리 ${g1.dist.toFixed(1)} → ${g2.dist.toFixed(1)})`);
    await touch('touchStart', [[380, 160], [460, 240]]);
    for (let i = 1; i <= 10; i++) { const a = Math.atan2(80, 80) + i * 0.06, r = Math.hypot(40, 40); await touch('touchMove', [[420 - Math.cos(a) * r, 200 - Math.sin(a) * r], [420 + Math.cos(a) * r, 200 + Math.sin(a) * r]]); await sleep(16); }
    await touch('touchEnd', []);
    await sleep(300);
    const g3 = await goal();
    ok(Math.abs(g3.yaw - g2.yaw) > 0.2, `두 손가락 비틀기로 회전 (${(g3.yaw - g2.yaw).toFixed(2)} 라디안)`);
    // 짧게 누르기(탭) — 건물·주민 고르기
    await touch('touchStart', [[422, 195]]); await sleep(60); await touch('touchEnd', []);
    await sleep(1500);
    await page.screenshot({ path: path.join(OUT, 'a3_touch.png') });
    // 정보 카드: 휴대폰 화면에서는 카드가 열린 동안 아래 도구 막대가 접히고(카드 단추가 잘리거나 탭을 잘못 누르지 않게), ✕ 로 닫으면 돌아온다
    const shown = (s) => page.evaluate((q) => { const e = document.querySelector(q); return !!e && getComputedStyle(e).display !== 'none'; }, s);
    if (!(await shown('#hud .card'))) await page.evaluate(() => { const g = window.__SM.game; g.hud.showBuilding(g.world.blds.find((b) => !b.ai && b.type === 'house' && b.state === 'active') || g.world.hall); });
    await sleep(400);
    const cardInfo = await page.$$eval('#hud .card button', (els) => els.map((e) => { const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return { t: e.textContent.trim().slice(0, 10), ok: r.bottom <= innerHeight && !!t && (t === e || e.contains(t)) }; }));
    ok(!(await shown('#hud .dock')) && cardInfo.length > 0 && cardInfo.every((c) => c.ok), `카드가 열리면 도구 막대가 접히고 카드 단추가 모두 눌림 (${cardInfo.map((c) => c.t + (c.ok ? '' : '✗')).join(', ')})`);
    await page.screenshot({ path: path.join(OUT, 'a3c_card.png') });
    const cx = await page.$eval('#hud .card .x', (e) => { const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
    await page.touchscreen.tap(cx[0], cx[1]); await sleep(400);
    ok(!(await shown('#hud .card')) && (await shown('#hud .dock')), '카드를 ✕ 로 닫으면 도구 막대가 다시 보임');

    // 아래 메뉴 버튼 터치 (건축 메뉴 열기 시도)
    const btns = await page.$$eval('#hud button, #hud .btn, #hud [data-tool]', (els) => els.filter((e) => e.offsetParent).slice(0, 40).map((e) => { const r = e.getBoundingClientRect(); return { t: (e.textContent || '').trim().slice(0, 12), x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height }; }));
    const offScreen = btns.filter((b) => b.x < 0 || b.y < 0 || b.x > 844 || b.y > 390);
    ok(btns.length > 0 && offScreen.length === 0, `화면 버튼 ${btns.length}개가 모두 화면 안에 있음`);
    const small = btns.filter((b) => Math.min(b.w, b.h) < 28);
    if (small.length) console.log('  참고: 손가락으로 누르기 작은 버튼(28px 미만):', small.map((b) => `${b.t || '?'}(${Math.round(b.w)}x${Math.round(b.h)})`).join(', '));
    // 휴대폰 화면 배치 (앱 보정): 분류 탭이 한 줄, 자원이 모두 보임 (상인이 와서 위쪽 단추가 늘어난 상태, 물건 14가지 세 자리 수)
    const catH = await page.$$eval('#hud .cat', (els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
    ok(catH.length > 0 && Math.max(...catH) <= 34, `분류 탭 글자가 한 줄 (높이 ${Math.max(...catH)}px)`);
    const keepStock = await page.evaluate(() => Object.assign({}, window.__SM.game.world.stock));
    await page.evaluate(async () => { const g = window.__SM.game; for (const k of Object.keys(g.hud.chips)) g.world.stock[k] = Math.max(g.world.stock[k] || 0, 123); if (!g.econ.merchant) await g.econ.arrive(); });
    await sleep(900);
    const chips = await page.evaluate(() => {
      const box = (e) => e.getBoundingClientRect();
      const st2 = document.querySelector('#hud .stock'), all = [...st2.children].filter((c) => getComputedStyle(c).display !== 'none');
      const clip = (q) => { let p = st2; while (p && p.id !== 'hud') { const cs = getComputedStyle(p); const r = box(p); if (cs.overflowX !== 'visible' && (q.left < r.left - 1 || q.right > r.right + 1)) return true; p = p.parentElement; } return q.left < 0 || q.right > innerWidth || q.bottom > innerHeight; };
      const hidden = all.filter((c) => clip(box(c))).map((c) => c.title);
      const s = box(st2), others = ['.clock', '.right'].map((k) => box(document.querySelector('#hud .top ' + k)));
      const overlap = others.some((o) => o.left < s.right - 1 && s.left < o.right - 1 && o.top < s.bottom - 1 && s.top < o.bottom - 1);
      return { n: all.length, hidden, overlap };
    });
    ok(chips.n >= 14 && chips.hidden.length === 0 && !chips.overlap, `자원 ${chips.n}가지가 모두 보임` + (chips.hidden.length ? ' — 잘림: ' + chips.hidden.join(', ') : '') + (chips.overlap ? ' — 위쪽 줄과 겹침' : ''));
    await page.screenshot({ path: path.join(OUT, 'a3b_stock.png') });
    await page.evaluate((s) => { const w = window.__SM.game.world; for (const k of Object.keys(w.stock)) w.stock[k] = 0; Object.assign(w.stock, s); }, keepStock);

    // 손가락으로 짓기: 분류 탭(생산) → 건물 단추(값이 보임) → 미리 보기가 바로 보임 → 땅 누르기(옮기기만) → 돌리기 → ✔ 짓기
    const center = async (sel) => page.$eval(sel, (e) => { const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }).catch(() => null);
    const tab = await page.$$eval('#hud button.cat', (els) => { const e = els.find((x) => /생\s*산/.test(x.textContent)); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
    if (ok(!!tab, '분류 탭 "생산" 있음')) {
      await page.touchscreen.tap(tab[0], tab[1]); await sleep(400);
      const costs = await page.$$eval('#hud .tool .co', (els) => els.map((e) => ({ t: e.textContent, h: e.getBoundingClientRect().height })));
      ok(costs.length > 0 && costs.every((c) => c.h > 4), `건물 단추에 값이 보임 (${costs.map((c) => c.t).slice(0, 3).join(' / ')} …)`);
      const tool = await center('#hud button.tool[data-m^="build:"]');
      if (ok(!!tool, '건물 단추 있음')) {
        await page.touchscreen.tap(tool[0], tool[1]); await sleep(600);
        const b0 = await page.evaluate(() => { const g = window.__SM.game; return { mode: g.mode, ghost: !!(g.ghost && g.ghost.visible), pn: document.querySelector('#hud .placebar .pn').textContent, prompt: document.querySelector('#hud .prompt').textContent }; });
        ok(/^build:/.test(b0.mode), `건물 단추를 누르면 짓기 상태: ${b0.mode}`);
        ok(b0.ghost, '짓기 상태가 되자마자 미리 보기(바닥 색·정문 화살표)가 보임');
        ok(!!b0.pn && /✔/.test(b0.prompt), `돌리기 줄에 값 "${b0.pn}", 안내 "${b0.prompt}"`);
        await page.screenshot({ path: path.join(OUT, 'a4_menu.png') });
        const n0 = (await api('stats')).blds.length;
        const type = b0.mode.slice(6);
        const sp = await api('findSpot', type, h.x + 10, h.z - 10, 0);
        if (ok(!!sp, '빈자리 찾음')) {
          await api('cam', sp[0], sp[1], 32, null, null); await sleep(1200);
          const scr = await page.evaluate(([x, z]) => window.__SM.game.stage.toScreen(x, 0, z), sp);
          await page.touchscreen.tap(scr.x, scr.y); await sleep(500);
          const g1 = await page.evaluate(() => { const g = window.__SM.game; return { n: g.world.blds.length, x: g.ghost.position.x, z: g.ghost.position.z, rot: g.ghost.rotation.y, ok: !!(g.ghost.userData.ok && g.ghost.userData.ok.ok) }; });
          ok(g1.n === n0 && Math.hypot(g1.x - sp[0], g1.z - sp[1]) < 1, `땅을 한 번 누르면 미리 보기만 그 자리로 (아직 ${g1.n}채, ${g1.ok ? '초록=지을 수 있음' : '빨강'})`);
          // 화면을 손가락으로 조금 끈 뒤 돌리기 → 미리 보기는 제자리에서 돈다
          await touch('touchStart', [[300, 120]]);
          for (let i = 1; i <= 6; i++) { await touch('touchMove', [[300 + i * 8, 120]]); await sleep(16); }
          // 손가락을 잠깐 멈췄다 뗀다 (빨리 튕기듯 떼면 크롬이 '미끄러짐'을 만들고, 그걸 멈추는 다음 누르기는 단추 누르기로 치지 않음)
          await sleep(250); await touch('touchMove', [[348, 120]]); await sleep(250);
          await touch('touchEnd', []); await sleep(400);
          const rl = await center('#hud .placebar button[data-a=l]');
          await page.touchscreen.tap(rl[0], rl[1]); await sleep(300);
          const g2 = await page.evaluate(() => { const g = window.__SM.game; return { x: g.ghost.position.x, z: g.ghost.position.z, rot: g.ghost.rotation.y }; });
          ok(Math.abs(g2.rot - g1.rot) > 0.1 && Math.hypot(g2.x - g1.x, g2.z - g1.z) < 0.6, `⟲ 돌리기: 미리 보기가 제자리에서 돎 (${(g2.rot - g1.rot).toFixed(2)} 라디안)`);
          await page.screenshot({ path: path.join(OUT, 'a4b_preview.png') });
          await okBtn(); await sleep(700);
          let n1 = (await api('stats')).blds.length;
          if (n1 === n0) {   // 돌려서 자리가 안 맞으면 처음 방향으로 돌려 다시
            const rr = await center('#hud .placebar button[data-a=r]'); await page.touchscreen.tap(rr[0], rr[1]); await sleep(300);
            await okBtn(); await sleep(700); n1 = (await api('stats')).blds.length;
          }
          ok(n1 === n0 + 1, `✔ 짓기로 건물 놓기 (${n0} → ${n1}채)`);
          await page.screenshot({ path: path.join(OUT, 'a4c_placed.png') });
        }
        await page.evaluate(() => window.__SM.game.setMode('view'));
      }
    }

    // 조금 놀게 두기 (시간 빠르게)
    await api('speed', 3);
    await sleep(10000);
    const s2 = await api('stats');
    ok(s2.fps > 0, `10초 돌림: 초당 ${s2.fps}장, 그리기 ${s2.draws}번, 주민 ${s2.people}명, 일감 ${s2.tasks}`);
    await api('speed', 1);
    await api('cam', h.x, h.z, 30, 0.8, 0.8);
    await sleep(2500);
    await page.screenshot({ path: path.join(OUT, 'a5_play.png') });

    // 앱이 뒤로 갈 때(홈 버튼): 소리 멈춤 신호가 문제없이 처리되는지
    await page.evaluate(() => { window.dispatchEvent(new Event('sm-app-pause')); window.dispatchEvent(new Event('sm-app-resume')); });
    ok(true, '뒤로 감/돌아옴 신호 처리됨');

    // 저장소 유지 (앱을 껐다 켜도 남는지 — 같은 주소에서 새로 열기)
    await page.evaluate(() => localStorage.setItem('sm_android_test', 'kept'));
    // 앱이 뒤로 갈 때 신호(sm-app-pause) → 저장되는지
    const mine = () => page.evaluate(() => window.__SM.game.world.blds.filter((b) => !b.ai).length);
    const before = await page.evaluate(() => { const o = {}; for (const k of Object.keys(localStorage)) o[k] = (localStorage.getItem(k) || '').length; return o; });
    const snap = await page.evaluate(() => JSON.stringify(Object.keys(localStorage).filter((k) => k !== 'sm_android_test').map((k) => localStorage.getItem(k))));
    await page.evaluate(() => window.dispatchEvent(new Event('sm-app-pause')));
    const snap2 = await page.evaluate(() => JSON.stringify(Object.keys(localStorage).filter((k) => k !== 'sm_android_test').map((k) => localStorage.getItem(k))));
    const keys = await page.evaluate(() => Object.keys(localStorage).filter((k) => k !== 'sm_android_test'));
    ok(keys.length > 0 && snap2 !== snap, `뒤로 갈 때 저장됨 (저장 열쇠: ${keys.join(', ') || '없음'}, ${Object.entries(before).map(([k, v]) => k + ' ' + v + '자').join(', ')})`);
    const nMine = await mine();
    await page.evaluate(() => window.dispatchEvent(new Event('sm-app-resume')));
    await page.reload();
    const cont = page.locator('button', { hasText: '이어하기' });
    await Promise.race([cont.first().waitFor({ timeout: 240000 }), page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 240000 })]).catch(() => {});
    const kept = await page.evaluate(() => localStorage.getItem('sm_android_test'));
    ok(kept === 'kept', '새로 열어도 저장소(localStorage) 남음');
    await page.evaluate(() => localStorage.removeItem('sm_android_test'));
    await sleep(800);
    await page.screenshot({ path: path.join(OUT, 'a6_reopen.png') });
    if (await cont.count()) {
      const bb = await cont.first().boundingBox();
      await page.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2);
      await page.waitForFunction(() => window.__SM && window.__SM.api, null, { timeout: 240000 });
      await sleep(1500);
      const n2 = await mine();
      ok(n2 === nMine, `"이어하기"로 마을이 돌아옴 (우리 건물 ${nMine} → ${n2}채)`);
      await page.screenshot({ path: path.join(OUT, 'a7_continued.png') });
    } else ok(false, '"이어하기" 단추가 나오지 않음');
  } catch (e) {
    ok(false, '시험 중 오류: ' + (e.stack || e));
  }
  const realErrs = errs.filter((e) => !/favicon/.test(e));
  ok(realErrs.length === 0, `페이지 오류 ${realErrs.length}개` + (realErrs.length ? '\n    ' + realErrs.slice(0, 5).join('\n    ') : ''));
  ok(bad.length === 0, `못 받은 파일 ${bad.length}개` + (bad.length ? '\n    ' + bad.slice(0, 8).join('\n    ') : ''));
  await b.close(); await srv.close();
}

if (!flag('--no-apk')) checkApk();
if (!flag('--no-web')) await webTest();
console.log(`\n결과: ${fails ? '실패 ' + fails + '개' : '모두 통과'} — 스크린샷: ${OUT}`);
process.exit(fails ? 1 : 0);
