// 봄날의 행진 — 윈도우용 앱(Electron) 시작점.
// 게임 파일(www 폴더)을 'app://game/' 이라는 앱 전용 주소로 보여 준다.
//   - 설치판: 게임 파일은 설치 폴더의 resources/www
//   - 개발 중: 저장소/.cache/app-pc/www (tools/build/build_app.mjs 가 만든다)
// 저장(localStorage)은 사용자 폴더(%APPDATA%\봄날의 행진)에 남아서 앱을 껐다 켜도 이어진다.
'use strict';

const { app, BrowserWindow, protocol, shell, Menu, session, dialog, ipcMain, screen } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

const SCHEME = 'app';
const HOST = 'game';
const START_URL = `${SCHEME}://${HOST}/index.html`;

// ---------------------------------------------------------------- 명령줄 선택 사항
// --www=<폴더>       : 다른 게임 파일 폴더 쓰기 (시험용)
// --user-data=<폴더> : 저장 폴더 바꾸기 (시험용, 진짜 저장을 건드리지 않게)
// --devtools         : 개발자 도구 열기
// 환경 변수 SM_HIDDEN=1 : 창을 화면에 한 번도 띄우지 않고 돌린다 (자동 시험용 — 컴퓨터 쓰는 사람 화면을 가리지 않게)
const HIDDEN = process.env.SM_HIDDEN === '1';
const argOf = (name) => {
  const a = process.argv.find((s) => s.startsWith(`--${name}=`));
  return a ? a.slice(name.length + 3) : null;
};
const WWW = path.resolve(argOf('www') || process.env.SM_WWW
  || (app.isPackaged ? path.join(process.resourcesPath, 'www') : path.join(__dirname, '..', '..', '..', '.cache', 'app-pc', 'www')));
const userData = argOf('user-data') || process.env.SM_USER_DATA;
if (userData) app.setPath('userData', path.resolve(userData));

// 그래픽카드를 꼭 쓰게 (3D 게임이라 소프트웨어 그리기는 너무 느리다), 노트북은 좋은 쪽 그래픽카드로
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('force_high_performance_gpu');
// 첫 화면부터 소리가 나게
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
// 숨긴 창이어도 게임이 쉬지 않고 그려지게 (자동 시험용)
if (HIDDEN) {
  app.commandLine.appendSwitch('disable-renderer-backgrounding');
  app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');
  app.commandLine.appendSwitch('disable-background-timer-throttling');
  app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');
}

/** 알림 창: 숨김 모드에서는 창 대신 글로만 남긴다 */
function alertBox(msg) {
  if (HIDDEN) console.error('[봄날의 행진] ' + msg.replace(/\n/g, ' '));
  else dialog.showErrorBox('봄날의 행진', msg);
}

// 앱 전용 주소는 앱이 준비되기 전에 '진짜 웹 주소처럼' 등록해야 fetch·저장(localStorage)이 된다
protocol.registerSchemesAsPrivileged([
  { scheme: SCHEME, privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true } },
]);

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.wasm': 'application/wasm',
  '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.txt': 'text/plain; charset=utf-8',
};

/** app://game/<경로> → www 폴더의 파일 (www 밖으로는 못 나간다) */
async function serve(request) {
  let url;
  try { url = new URL(request.url); } catch (e) { return new Response('잘못된 주소', { status: 400 }); }
  if (url.host !== HOST) return new Response('없는 주소', { status: 404 });
  // 잘못된 %글자(예: %ZZ)가 든 주소는 풀다가 오류가 나므로, 앱 쪽 오류 대신 '잘못된 주소'로 답한다
  let rel;
  try { rel = decodeURIComponent(url.pathname); } catch (e) { return new Response('잘못된 주소', { status: 400 }); }
  if (!rel || rel.endsWith('/')) rel += 'index.html';
  const fp = path.resolve(WWW, '.' + rel);
  if (fp !== WWW && !fp.startsWith(WWW + path.sep)) return new Response('막힌 주소', { status: 403 });
  try {
    const st = await fs.promises.stat(fp);
    if (!st.isFile()) return new Response('없는 파일', { status: 404 });
    const data = await fs.promises.readFile(fp);
    return new Response(data, {
      status: 200,
      headers: { 'content-type': MIME[path.extname(fp).toLowerCase()] || 'application/octet-stream', 'content-length': String(data.length), 'cache-control': 'no-cache' },
    });
  } catch (e) {
    return new Response('없는 파일', { status: 404 });
  }
}

/** 바깥 인터넷 주소는 게임 창 대신 기본 브라우저로 연다 (http/https 만) */
function openOutside(u) {
  try {
    const p = new URL(u).protocol;
    if (p === 'http:' || p === 'https:') shell.openExternal(u);
  } catch (e) { /* 이상한 주소는 무시 */ }
}

let win = null;
let crashes = 0;

// ---------------------------------------------------------------- 전체 화면 켜기/끄기
// 숨김 모드에서는 진짜 전체 화면을 쓰면 윈도우가 창을 억지로 보여 주므로(전체 화면을 끌 때),
// 창 크기를 모니터 크기로 바꾸는 '흉내 전체 화면'을 쓴다. 키 처리·게임 화면 크기 바뀜은 똑같이 시험된다.
const fakeFull = new Map();   // 창 번호 → 전체 화면 전 창 크기·위치 (바깥 테두리 포함)
function isFull(w) { return HIDDEN ? fakeFull.has(w.id) : w.isFullScreen(); }
function setFull(w, on) {
  if (!w || w.isDestroyed()) return;
  if (!HIDDEN) { w.setFullScreen(on); return; }
  if (on && !fakeFull.has(w.id)) {
    fakeFull.set(w.id, w.getBounds());
    w.setContentBounds(screen.getDisplayMatching(w.getBounds()).bounds);
  } else if (!on && fakeFull.has(w.id)) {
    w.setBounds(fakeFull.get(w.id));
    fakeFull.delete(w.id);
  }
}
function toggleFull(w) { if (w && !w.isDestroyed()) setFull(w, !isFull(w)); }
global.smIsFullScreen = isFull;   // 시험에서 읽는다

// ---------------------------------------------------------------- 창 크기·위치 기억 (다음에 켤 때 그대로)
const stateFile = () => path.join(app.getPath('userData'), 'window.json');
function loadWinState() {
  try {
    const s = JSON.parse(fs.readFileSync(stateFile(), 'utf8'));
    const b = s && s.bounds;
    if (!b || !(b.width > 200 && b.height > 200)) return null;
    // 모니터를 떼었을 때처럼 화면 밖이면 쓰지 않는다
    const seen = screen.getAllDisplays().some((d) => { const a = d.workArea; return b.x < a.x + a.width - 80 && b.x + b.width > a.x + 80 && b.y >= a.y - 20 && b.y < a.y + a.height - 80; });
    return seen ? s : null;
  } catch (e) { return null; }
}
function saveWinState() {
  if (!win || win.isDestroyed()) return;
  const bounds = fakeFull.get(win.id) || win.getNormalBounds();   // 흉내 전체 화면 중이면 그 전 크기
  try { fs.writeFileSync(stateFile(), JSON.stringify({ bounds, maximized: win.isMaximized(), fullscreen: isFull(win) })); } catch (e) { /* 못 써도 괜찮다 */ }
}

function createWindow() {
  const iconPath = path.join(WWW, 'icon.ico');
  // 기본 1600x900, 화면이 그보다 작으면(노트북 등) 화면에 맞추고 최대화
  // 처음에는 주 모니터 한가운데 (모니터가 여러 개여도)
  const wa = screen.getPrimaryDisplay().workArea;
  const small = wa.width < 1600 || wa.height < 900;
  const minW = Math.min(1024, wa.width), minH = Math.min(600, wa.height);
  const saved = loadWinState();
  const w0 = Math.min(1600, wa.width), h0 = Math.min(900, wa.height);
  const b = saved ? saved.bounds : { width: w0, height: h0, x: Math.round(wa.x + (wa.width - w0) / 2), y: Math.round(wa.y + (wa.height - h0) / 2) };
  win = new BrowserWindow({
    x: b.x, y: b.y, width: Math.max(minW, b.width), height: Math.max(minH, b.height), minWidth: minW, minHeight: minH,
    title: '봄날의 행진',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    backgroundColor: '#dfe9f5',
    autoHideMenuBar: true,
    show: false,          // 다 불러온 뒤에 보여 준다 (숨김 모드에서는 끝까지 보여 주지 않는다)
    skipTaskbar: HIDDEN,  // 숨김 모드: 작업 표시줄에도 나오지 않게
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false,
      webSecurity: true, allowRunningInsecureContent: false,
      // 숨김 모드: 안 보이는 창이어도 쉬지 않고 그리기
      backgroundThrottling: !HIDDEN, paintWhenInitiallyHidden: true,
      // 숨김 모드: 한 번도 보여 주지 않은 창은 윈도우가 1초에 한 번만 그리게 해서, 화면 밖 그리기(오프스크린)로 그래픽카드에 초당 60번 그린다
      offscreen: HIDDEN,
    },
  });
  win.setMenuBarVisibility(false);
  // 최대화·전체 화면은 윈도우가 창을 보여 주므로 숨김 모드에서는 하지 않는다
  if (!HIDDEN) {
    if (saved ? saved.maximized : small) win.maximize();
    if (saved && saved.fullscreen) win.setFullScreen(true);
    win.once('ready-to-show', () => { win.show(); win.focus(); });
    // 혹시 'ready-to-show' 가 늦어도 창은 보이게
    setTimeout(() => { if (win && !win.isDestroyed() && !win.isVisible()) win.show(); }, 4000);
  }
  win.on('close', saveWinState);

  const wc = win.webContents;
  // F11 = 전체 화면 켜기/끄기, (개발 중) F12 = 개발자 도구
  wc.on('before-input-event', (e, input) => {
    if (input.type !== 'keyDown') return;
    if (input.key === 'F11' || (input.alt && input.key === 'Enter')) { toggleFull(win); e.preventDefault(); }
    else if (input.key === 'F12' && !app.isPackaged && !HIDDEN) { wc.toggleDevTools(); e.preventDefault(); }
  });
  // 새 창 열기 → 바깥 브라우저로, 게임 창은 다른 곳으로 이동하지 않는다
  wc.setWindowOpenHandler(({ url }) => { openOutside(url); return { action: 'deny' }; });
  wc.on('will-navigate', (e, url) => { if (!url.startsWith(`${SCHEME}://${HOST}/`)) { e.preventDefault(); openOutside(url); } });
  wc.on('will-redirect', (e, url) => { if (!url.startsWith(`${SCHEME}://${HOST}/`)) e.preventDefault(); });
  // Ctrl+휠 같은 화면 확대는 막는다 (게임 안 확대는 휠로)
  wc.on('zoom-changed', () => wc.setZoomFactor(1));
  wc.setVisualZoomLevelLimits(1, 1).catch(() => {});
  // 그리는 쪽이 멈추면 다시 불러온다 (세 번까지)
  wc.on('render-process-gone', (e, details) => {
    if (details.reason === 'clean-exit' || !win || win.isDestroyed()) return;
    if (++crashes <= 3) wc.loadURL(START_URL);
    else alertBox('게임이 계속 멈춰요. 앱을 다시 켜 주세요.');
  });

  win.on('closed', () => { session.defaultSession.flushStorageData(); win = null; });
  if (process.argv.includes('--devtools') && !HIDDEN) wc.openDevTools({ mode: 'detach' });
  if (HIDDEN) wc.setFrameRate(60);
  win.loadURL(START_URL);
}

// 같은 앱을 두 번 켜면 (저장이 엉키지 않게) 이미 켜진 창을 앞으로
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!win || HIDDEN) return;   // 숨김 모드에서는 창을 앞으로 꺼내지 않는다
    if (win.isMinimized()) win.restore();
    win.focus();
  });

  app.whenReady().then(() => {
    if (process.platform === 'win32') app.setAppUserModelId('com.springmarch.game');
    Menu.setApplicationMenu(null);
    protocol.handle(SCHEME, serve);
    // 게임 화면에서 오는 부탁 (우리 게임 주소에서 온 것만 듣는다)
    const fromGame = (e) => !!(e.senderFrame && e.senderFrame.url.startsWith(`${SCHEME}://${HOST}/`));
    ipcMain.on('sm:fullscreen', (e) => { const w = BrowserWindow.fromWebContents(e.sender); if (w && fromGame(e)) toggleFull(w); });
    ipcMain.on('sm:quit', (e) => { if (fromGame(e)) app.quit(); });
    // 카메라·마이크·위치 같은 권한은 모두 거절 (전체 화면만 허락)
    const ok = new Set(['fullscreen', 'clipboard-sanitized-write']);
    session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(ok.has(perm)));
    session.defaultSession.setPermissionCheckHandler((wc, perm) => ok.has(perm));
    if (!fs.existsSync(path.join(WWW, 'index.html'))) {
      alertBox(`게임 파일을 찾지 못했어요.\n${WWW}`);
      app.quit();
      return;
    }
    createWindow();
  });

  // 끄기 직전에 저장 내용을 디스크에 확실히 쓴다
  app.on('before-quit', () => { try { session.defaultSession.flushStorageData(); } catch (e) { /* 이미 닫힘 */ } });
  app.on('window-all-closed', () => app.quit());
}

// 다른 곳에서 만든 창(혹시 생기면)도 같은 규칙
app.on('web-contents-created', (e, contents) => {
  contents.on('will-attach-webview', (ev) => ev.preventDefault());
});
