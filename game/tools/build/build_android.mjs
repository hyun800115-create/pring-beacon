// 봄날의 행진 — 안드로이드 앱(APK) 만들기.
//
//   node tools/build/build_android.mjs              www 만들기 → 안드로이드 프로젝트 정리 → 디버그·출시용 APK → .cache/release/
//   node tools/build/build_android.mjs --web-only   www(휴대폰에 들어갈 게임 묶음)만 만들기
//   node tools/build/build_android.mjs --setup      자바(JDK 21)·안드로이드 도구가 없으면 .cache 에 내려받아 설치 (새 PC 용)
//   옵션: --no-release  서명한 출시용 APK 건너뛰기,  --clean  www 를 지우고 처음부터 (모델 압축도 다시)
//
// 설치물은 모두 저장소 안 .cache 에만 둔다 (컴퓨터 설정은 건드리지 않음):
//   .cache/jdk (자바), .cache/android-sdk (안드로이드 도구), .cache/gradle (빌드 도구 창고),
//   .cache/android-keystore (출시용 서명 열쇠 — 절대 저장소에 올리지 않음), 결과물은 .cache/release/
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { NodeIO, Logger } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { textureCompress, meshopt, dedup, prune } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GAME = path.resolve(HERE, '..', '..');                 // game/
const REPO = path.resolve(GAME, '..');                       // 저장소 뿌리
const CACHE = path.join(REPO, '.cache');
const APP = path.join(GAME, 'app', 'android');               // Capacitor 껍데기
const WWW = path.join(APP, 'www');
const NATIVE = path.join(APP, 'android');                    // 안드로이드 프로젝트 (cap add 로 생김)
const RELEASE = path.join(CACHE, 'release');
const KEYDIR = path.join(CACHE, 'android-keystore');
const T = {
  jdk: path.join(CACHE, 'jdk'), sdk: path.join(CACHE, 'android-sdk'), gradle: path.join(CACHE, 'gradle'),
};
const args = new Set(process.argv.slice(2));
const APP_ID = 'kr.springmarch.game';
const APP_NAME = '봄날의 행진';
const PKG = JSON.parse(fs.readFileSync(path.join(APP, 'package.json'), 'utf8'));
const VERSION = PKG.version || '0.1.0';
const say = (...a) => console.log('[android]', ...a);
const mb = (n) => (n / 1048576).toFixed(1) + 'MB';

// 빌드할 때만 쓰는 환경 (컴퓨터 전체 설정은 바꾸지 않는다)
const ENV = Object.assign({}, process.env, {
  JAVA_HOME: T.jdk, ANDROID_HOME: T.sdk, ANDROID_SDK_ROOT: T.sdk, GRADLE_USER_HOME: T.gradle,
  ANDROID_USER_HOME: path.join(T.sdk, '.user'),   // 디버그 서명 열쇠 등도 .cache 안에 (사용자 폴더 ~/.android 를 안 씀)
  PATH: [path.join(T.jdk, 'bin'), path.join(T.sdk, 'platform-tools'), process.env.PATH || process.env.Path || ''].join(path.delimiter),
});
delete ENV.Path;

function run(cmd, cmdArgs, cwd, opts = {}) {
  say('>', cmd, cmdArgs.join(' '));
  // .bat/.cmd 는 cmd.exe 로 돌려야 한다 (node 24 규칙)
  const isBat = /\.(bat|cmd)$/i.test(cmd) || cmd === 'npx' || cmd === 'npm';
  // windowsHide: 검은 명령 창이 대표님 화면에 뜨지 않게 (백그라운드에서 돌릴 때 특히)
  const r = isBat
    ? spawnSync('cmd.exe', ['/d', '/s', '/c', [cmd, ...cmdArgs].map((a) => (/[\s&|<>^]/.test(a) ? `"${a}"` : a)).join(' ')], { cwd, env: ENV, stdio: opts.input ? ['pipe', 'inherit', 'inherit'] : 'inherit', input: opts.input, windowsVerbatimArguments: true, windowsHide: true })
    : spawnSync(cmd, cmdArgs, { cwd, env: ENV, stdio: opts.input ? ['pipe', 'inherit', 'inherit'] : 'inherit', input: opts.input, windowsHide: true });
  if (r.status !== 0 && !opts.ok) throw new Error(`명령이 실패했어요 (${r.status}): ${cmd} ${cmdArgs.join(' ')}`);
  return r.status;
}

// ------------------------------------------------------------------ 1) 도구 준비
async function download(url, dest) {
  say('내려받는 중:', url);
  const r = await fetch(url, { redirect: 'follow' });
  if (!r.ok) throw new Error('내려받기 실패 ' + r.status + ' ' + url);
  fs.writeFileSync(dest, Buffer.from(await r.arrayBuffer()));
  say('  →', mb(fs.statSync(dest).size));
}
const sha256 = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
// 윈도우에 들어 있는 tar(bsdtar)는 zip 도 푼다 (Git Bash 의 GNU tar 는 못 풂)
function unzip(zip, dir) { fs.mkdirSync(dir, { recursive: true }); run(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe'), ['-xf', zip, '-C', dir], dir); }

async function setupTools() {
  const tmp = path.join(CACHE, 'android-dl');
  fs.mkdirSync(tmp, { recursive: true });
  if (!fs.existsSync(path.join(T.jdk, 'bin', 'java.exe'))) {
    // 자바 21 (Eclipse Temurin, 공식 Adoptium) — 받은 파일의 지문(sha256)을 공식 값과 맞춰 본다
    const meta = await (await fetch('https://api.adoptium.net/v3/assets/latest/21/hotspot?os=windows&architecture=x64&image_type=jdk&vendor=eclipse')).json();
    const pk = meta[0].binary.package;
    const zip = path.join(tmp, pk.name);
    await download(pk.link, zip);
    if (sha256(zip) !== pk.checksum) throw new Error('JDK 파일 지문이 맞지 않아요');
    const x = path.join(tmp, 'x_jdk'); fs.rmSync(x, { recursive: true, force: true }); unzip(zip, x);
    fs.rmSync(T.jdk, { recursive: true, force: true });
    fs.renameSync(path.join(x, fs.readdirSync(x)[0]), T.jdk);
  }
  const sdkm = path.join(T.sdk, 'cmdline-tools', 'latest', 'bin', 'sdkmanager.bat');
  if (!fs.existsSync(sdkm)) {
    // 안드로이드 명령줄 도구 — 공식 내려받기 쪽에서 지금 파일 이름과 지문을 읽는다
    const page = await (await fetch('https://developer.android.com/studio')).text();
    const name = (page.match(/commandlinetools-win-\d+_latest\.zip/) || [])[0];
    if (!name) throw new Error('안드로이드 도구 파일 이름을 찾지 못했어요');
    const i = page.indexOf(name); const sum = (page.slice(i, i + 800).match(/[0-9a-f]{64}/) || [])[0];
    const zip = path.join(tmp, name);
    await download('https://dl.google.com/android/repository/' + name, zip);
    if (sum && sha256(zip) !== sum) throw new Error('안드로이드 도구 파일 지문이 맞지 않아요');
    const x = path.join(tmp, 'x_ct'); fs.rmSync(x, { recursive: true, force: true }); unzip(zip, x);
    fs.mkdirSync(path.join(T.sdk, 'cmdline-tools'), { recursive: true });
    fs.renameSync(path.join(x, 'cmdline-tools'), path.join(T.sdk, 'cmdline-tools', 'latest'));
  }
  const need = ['platform-tools', 'platforms;android-35', 'build-tools;35.0.0', 'build-tools;34.0.0'];
  const have = (p) => fs.existsSync(path.join(T.sdk, ...p.split(';')));
  if (need.some((p) => !have(p))) {
    run(sdkm, ['--sdk_root=' + T.sdk, '--licenses'], T.sdk, { input: 'y\n'.repeat(30) });   // 라이선스 동의 (대표님이 허락함)
    run(sdkm, ['--sdk_root=' + T.sdk, ...need], T.sdk);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}

function checkTools() {
  const miss = [];
  if (!fs.existsSync(path.join(T.jdk, 'bin', 'java.exe'))) miss.push('자바(JDK) → ' + T.jdk);
  if (!fs.existsSync(path.join(T.sdk, 'platforms', 'android-35'))) miss.push('안드로이드 도구 → ' + T.sdk);
  return miss;
}

// ------------------------------------------------------------------ 2) www (휴대폰 안에 들어갈 게임 묶음)
async function buildWeb() {
  if (args.has('--clean')) fs.rmSync(WWW, { recursive: true, force: true });
  fs.mkdirSync(WWW, { recursive: true });
  const keep = new Set();   // 이번에 만든 파일 (남은 옛 파일은 마지막에 지움)
  const put = (rel) => { keep.add(rel.split(path.sep).join('/')); return path.join(WWW, rel); };

  // 코드 + three.js 를 한 파일로
  await build({
    entryPoints: [path.join(GAME, 'src', 'main.js')], bundle: true, format: 'esm', minify: true,
    target: ['es2020', 'chrome89'], outfile: put('game.js'), logLevel: 'warning', nodePaths: [path.join(GAME, 'node_modules')],
  });

  // 완전한 HTML 문서 (가져오기 지도 없음, CSS 는 안에 넣음)
  const css = fs.readFileSync(path.join(GAME, 'src', 'ui', 'hud.css'), 'utf8').replace(/url\((['"]?)\.\.\/\.\.\/assets\//g, 'url($1assets/');
  let html = fs.readFileSync(path.join(GAME, 'index.html'), 'utf8');
  const must = (re, to, what) => { if (!re.test(html)) throw new Error('index.html 에서 ' + what + ' 을(를) 못 찾았어요'); html = html.replace(re, to); };
  must(/<script type="importmap">[\s\S]*?<\/script>\s*/, '', '가져오기 지도');
  // (휴대폰 화면 배치·손가락 짓기는 본판 hud.css·main.js 가 직접 맡는다)
  must(/<link rel="stylesheet" href="src\/ui\/hud\.css">/, () => `<style>\n${css}\n</style>`, 'hud.css 연결');
  must(/<script type="module" src="src\/main\.js"><\/script>/, () => `<script>\n${APP_HELPER}\n</script>\n<script type="module" src="game.js"></script>`, 'main.js 연결');
  if (!/viewport-fit=cover/.test(html)) html = html.replace(/<meta name="viewport" content="([^"]*)">/, '<meta name="viewport" content="$1, viewport-fit=cover">');
  if (!/^<!doctype html>/i.test(html.trim())) html = '<!doctype html>\n' + html;
  fs.writeFileSync(put('index.html'), html);

  // 그림·소리
  const copy = (rel) => { const s = path.join(GAME, rel); if (!fs.existsSync(s)) return; if (fs.statSync(s).isDirectory()) { for (const f of fs.readdirSync(s)) copy(path.join(rel, f)); return; } const d = put(rel); fs.mkdirSync(path.dirname(d), { recursive: true }); fs.copyFileSync(s, d); };
  copy('assets/ground'); copy('assets/emotes');
  for (const f of fs.readdirSync(path.join(GAME, 'assets', 'characters'))) if (/^portrait_player.*\.png$/.test(f)) copy('assets/characters/' + f);
  for (const f of fs.readdirSync(path.join(GAME, 'assets', 'audio'))) if (/\.(mp3|ogg|json)$/.test(f)) copy('assets/audio/' + f);

  // 3D 모델: 소품·건물은 그림 WebP + 모양 압축(meshopt), 주민(동작 있음)은 겹친 것만 정리. 이름은 그대로 .glb
  await MeshoptEncoder.ready;
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
  let before = 0, after = 0, redo = 0;
  for (const dir of ['chars', 'props', 'buildings']) {   // 가구는 건물 GLB 안에 이미 들어 있음
    const src = path.join(GAME, 'assets3d', dir);
    if (!fs.existsSync(src)) continue;
    fs.mkdirSync(path.join(WWW, 'assets3d', dir), { recursive: true });
    for (const f of fs.readdirSync(src)) {
      const sp = path.join(src, f);
      if (f.endsWith('.json')) { fs.copyFileSync(sp, put(path.join('assets3d', dir, f))); continue; }
      if (!f.endsWith('.glb')) continue;
      const dp = put(path.join('assets3d', dir, f));
      before += fs.statSync(sp).size;
      // 원본이 그대로면 지난번 압축 결과를 다시 쓴다 (빠름)
      if (!fs.existsSync(dp) || fs.statSync(dp).mtimeMs < fs.statSync(sp).mtimeMs) {
        const doc = await io.read(sp);
        doc.setLogger(new Logger(Logger.Verbosity.WARN));   // 정리 기록은 감춤
        // 주민은 모양 압축을 하지 않는다: 관절 크기 값이 바뀌면 동작이 모양을 깨뜨린다 (플레이 링크에서 겪음)
        if (dir === 'chars') await doc.transform(dedup());
        else await doc.transform(dedup(), prune(), textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 82, resize: [1024, 1024] }), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
        fs.writeFileSync(dp, await io.writeBinary(doc));
        redo++;
      }
      after += fs.statSync(dp).size;
    }
  }
  // 이번에 안 만든 옛 파일 지우기
  const walk = (d, out = []) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p, out); else out.push(path.relative(WWW, p).split(path.sep).join('/')); } return out; };
  for (const f of walk(WWW)) if (!keep.has(f)) fs.rmSync(path.join(WWW, f));
  const files = walk(WWW);
  const size = files.reduce((a, f) => a + fs.statSync(path.join(WWW, f)).size, 0);
  say(`www: 파일 ${files.length}개 ${mb(size)} (모델 ${mb(before)} → ${mb(after)}, 새로 압축 ${redo}개) → ${WWW}`);
}

// 앱 도우미 (www/index.html 안에 들어감): 앱이 뒤로 가면 소리를 멈추고 저장, 돌아오면 소리 다시 켜기.
// 안드로이드 쪽(MainActivity)이 'sm-app-pause' / 'sm-app-resume' 신호를 보낸다. 브라우저에서는 화면 숨김 신호로 같은 일을 한다.
const APP_HELPER = `(function () {
  var paused = false;
  function game() { try { return window.__SM && window.__SM.game; } catch (e) { return null; } }
  function save() {
    var g = game(), s = g && g.saver; if (!s) return;
    // 저장 팀의 자동 저장(게임 준비가 끝난 뒤에만 저장함)을 먼저 쓴다 — 이어하기 화면에서 빈 마을로 덮어쓰지 않게
    try { if (typeof s.autoSave === 'function') s.autoSave('hide'); else if (typeof s.saveNow === 'function') s.saveNow('app'); else if (typeof s.save === 'function') s.save(); } catch (e) { /* 저장 실패는 조용히 */ }
  }
  function pause() {
    var g = game(), c = g && g.audio && g.audio.ctx;
    if (c && c.state === 'running') { try { c.suspend(); paused = true; } catch (e) {} }
    save();
  }
  function resume() {
    var g = game(), c = g && g.audio && g.audio.ctx;
    if (c && paused) { try { c.resume(); } catch (e) {} }
    paused = false;
  }
  window.__smApp = { pause: pause, resume: resume, android: /; wv\\)/.test(navigator.userAgent) };
  window.addEventListener('sm-app-pause', pause);
  window.addEventListener('sm-app-resume', resume);
  document.addEventListener('visibilitychange', function () { if (document.hidden) pause(); else resume(); });
})();`;

// ------------------------------------------------------------------ 3) 안드로이드 프로젝트 정리
function edit(file, fn) { const s = fs.readFileSync(file, 'utf8'); const t = fn(s); if (t !== s) { fs.writeFileSync(file, t); say('고침:', path.relative(APP, file)); } }

async function prepareNative() {
  if (!fs.existsSync(path.join(NATIVE, 'app', 'build.gradle'))) run('npx', ['cap', 'add', 'android'], APP);
  const main = path.join(NATIVE, 'app', 'src', 'main');
  const javaDir = path.join(main, 'java', ...APP_ID.split('.'));

  // 화면: 가로 고정(뒤집기 허용), 하드웨어 가속, 한국어 이름
  edit(path.join(main, 'AndroidManifest.xml'), (s) => {
    s = s.replace(/<application\b(?![^>]*hardwareAccelerated)/, '<application\n        android:hardwareAccelerated="true"');
    s = s.replace(/<activity\b(?![^>]*screenOrientation)/, '<activity\n            android:screenOrientation="sensorLandscape"\n            android:resizeableActivity="false"');
    return s;
  });
  edit(path.join(main, 'res', 'values', 'strings.xml'), (s) => s
    .replace(/<string name="app_name">[^<]*<\/string>/, `<string name="app_name">${APP_NAME}</string>`)
    .replace(/<string name="title_activity_main">[^<]*<\/string>/, `<string name="title_activity_main">${APP_NAME}</string>`));
  edit(path.join(main, 'res', 'values', 'styles.xml'), (s) => s.replace(
    /(<style name="AppTheme\.NoActionBar"[^>]*>)(?![\s\S]*?sm-black)/,
    '$1\n        <!-- sm-black: 화면 가장자리(카메라 구멍 옆)는 검은색 -->\n        <item name="android:windowBackground">@android:color/black</item>'));

  // 앱 몸통: 전체 화면(위·아래 막대 숨김), 화면 꺼짐 막기, 뒤로 가기 물어보기, 소리 멈춤·저장 신호, .glb 종류 알려주기
  fs.writeFileSync(path.join(javaDir, 'MainActivity.java'), MAIN_ACTIVITY);
  fs.writeFileSync(path.join(javaDir, 'GameWebViewClient.java'), WEB_CLIENT);

  // 버전·출시용 서명 (열쇠 정보는 저장소 밖 파일에서 읽는다)
  edit(path.join(NATIVE, 'app', 'build.gradle'), (s) => {
    s = s.replace(/versionCode \d+/, `versionCode ${versionCode(VERSION)}`).replace(/versionName "[^"]*"/, `versionName "${VERSION}"`);
    // 서명 부분은 표시(시작·끝) 사이를 통째로 바꾼다 (다시 돌려도 한 번만 들어감)
    const a = s.indexOf(SIGN_START);
    if (a < 0) return s.trimEnd() + '\n\n' + GRADLE_SIGNING.trim() + '\n';
    const b = s.indexOf(SIGN_END, a);   // 끝 표시가 없으면(옛 판) 파일 끝까지가 서명 부분
    return s.slice(0, a).trimEnd() + '\n\n' + GRADLE_SIGNING.trim() + '\n' + (b >= 0 ? s.slice(b + SIGN_END.length).replace(/^\r?\n/, '') : '');
  });
  // 한글 폴더 이름(C:\\시라이스) 때문에 안드로이드 빌드 도구가 멈추지 않도록
  edit(path.join(NATIVE, 'gradle.properties'), (s) => (s.includes('android.overridePathCheck') ? s : s.trimEnd() + '\n\n# 저장소 폴더 이름이 한글이라 경로 검사를 끈다\nandroid.overridePathCheck=true\n'));

  await makeIcons(path.join(main, 'res'));
}

const versionCode = (v) => { const [a, b, c] = v.split('.').map((n) => parseInt(n, 10) || 0); return a * 10000 + b * 100 + c || 1; };

const SIGN_START = '// ---- 봄날의 행진: 출시용 서명 ----', SIGN_END = '// ---- 봄날의 행진: 서명 끝 ----';
const GRADLE_SIGNING = `
${SIGN_START}
// 열쇠는 저장소 밖(.cache/android-keystore)에만 있다. build_android.mjs 가 SM_KEYSTORE_PROPS 로 그 위치를 알려준다.
// 열쇠가 없으면 출시용 APK 는 서명 없이 만들어진다(설치 불가) — 디버그 APK 는 언제나 설치 가능.
def smKeyProps = new Properties()
def smKeyPath = System.getenv('SM_KEYSTORE_PROPS')
if (smKeyPath != null && new File(smKeyPath).exists()) { new File(smKeyPath).withReader('UTF-8') { smKeyProps.load(it) } }
android {
    signingConfigs {
        if (smKeyProps['storeFile']) {
            smRelease {
                storeFile file(smKeyProps['storeFile'])
                storePassword smKeyProps['storePassword']
                keyAlias smKeyProps['keyAlias']
                keyPassword smKeyProps['keyPassword']
            }
        }
    }
    buildTypes {
        release {
            if (smKeyProps['storeFile']) signingConfig signingConfigs.smRelease
        }
    }
}
${SIGN_END}
`;

const MAIN_ACTIVITY = `package ${APP_ID};

import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AlertDialog;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;

// 봄날의 행진 앱 몸통 (build_android.mjs 가 만든다 — 고치려면 그 파일을 고칠 것)
public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 노는 동안 화면이 꺼지지 않게
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideBars();
        // .glb(3D 모델) 파일 종류를 알려주는 길잡이
        if (bridge != null) bridge.setWebViewClient(new GameWebViewClient(bridge));
        // 뒤로 가기: 바로 꺼지지 않고 물어본다
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle("봄날의 행진")
                    .setMessage("게임을 끝낼까요?")
                    .setPositiveButton("끝내기", (d, w) -> signal("sm-app-pause", () -> finish()))   // 저장이 끝난 뒤에 닫는다
                    .setNegativeButton("계속하기", (d, w) -> hideBars())
                    .setOnCancelListener((d) -> hideBars())
                    .show();
            }
        });
    }

    // 위쪽 상태 막대·아래쪽 버튼 막대 숨기기 (화면 가장자리를 쓸어 넘기면 잠깐 보임)
    private void hideBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat c = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        c.hide(WindowInsetsCompat.Type.systemBars());
        c.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    // 게임 화면에 신호 보내기 (소리 멈춤·저장 / 다시 켜기)
    private void signal(String name) {
        signal(name, null);
    }

    // after: 게임 쪽 처리(저장 등)가 끝난 뒤 할 일
    private void signal(String name, Runnable after) {
        if (bridge == null || bridge.getWebView() == null) {
            if (after != null) after.run();
            return;
        }
        bridge.getWebView().evaluateJavascript("try{window.dispatchEvent(new Event('" + name + "'))}catch(e){};1", after == null ? null : (v) -> after.run());
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideBars();
    }

    @Override
    public void onResume() {
        super.onResume();
        hideBars();
        if (bridge != null && bridge.getWebView() != null) bridge.getWebView().onResume();
        signal("sm-app-resume");
    }

    @Override
    public void onPause() {
        signal("sm-app-pause");
        WebView w = bridge != null ? bridge.getWebView() : null;
        if (w != null) w.onPause();
        super.onPause();
    }
}
`;

const WEB_CLIENT = `package ${APP_ID};

import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeWebViewClient;

// 앱 안 작은 서버가 모르는 파일 종류를 알려준다 (.glb = 3D 모델, .json, .ogg)
public class GameWebViewClient extends BridgeWebViewClient {

    public GameWebViewClient(Bridge bridge) {
        super(bridge);
    }

    @Override
    public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
        WebResourceResponse r = super.shouldInterceptRequest(view, request);
        if (r == null) return null;
        String p = request.getUrl().getPath();
        if (p == null) return r;
        if (p.endsWith(".glb")) r.setMimeType("model/gltf-binary");
        else if (p.endsWith(".json") && r.getMimeType() == null) r.setMimeType("application/json");
        else if (p.endsWith(".ogg") && r.getMimeType() == null) r.setMimeType("audio/ogg");
        return r;
    }
}
`;

// ------------------------------------------------------------------ 아이콘·첫 화면 그림 (주인공 얼굴)
async function makeIcons(res) {
  const portrait = path.join(GAME, 'assets', 'characters', 'portrait_player_512.png');
  // 머리와 어깨만 잘라 쓴다 (원본 512: 인물이 가운데, 흔드는 손 포함)
  const face = await sharp(portrait).extract({ left: 96, top: 52, width: 320, height: 320 }).png().toBuffer();
  const bg = (w, h, round) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe4ff"/><stop offset="0.62" stop-color="#d9f0c4"/><stop offset="1" stop-color="#a9db8c"/></linearGradient></defs>
    ${round === 'circle' ? `<circle cx="${w / 2}" cy="${h / 2}" r="${w / 2}" fill="url(#g)"/>` : round ? `<rect width="${w}" height="${h}" rx="${w * 0.22}" fill="url(#g)"/>` : `<rect width="${w}" height="${h}" fill="url(#g)"/>`}
    ${[[0.18, 0.22, 0.035], [0.82, 0.18, 0.03], [0.86, 0.6, 0.025], [0.12, 0.66, 0.028]].map(([x, y, r]) => `<circle cx="${x * w}" cy="${y * h}" r="${r * w}" fill="#ffc2d4" opacity="0.9"/>`).join('')}
  </svg>`);
  const legacy = { mdpi: 48, hdpi: 72, xhdpi: 96, xxhdpi: 144, xxxhdpi: 192 };
  for (const [d, n] of Object.entries(legacy)) {
    const dir = path.join(res, 'mipmap-' + d); fs.mkdirSync(dir, { recursive: true });
    const f = Math.round(n * 0.9), off = Math.round((n - f) / 2);
    const fg = await sharp(face).resize(f, f).png().toBuffer();
    for (const [name, round] of [['ic_launcher.png', true], ['ic_launcher_round.png', 'circle']]) {
      // 바탕 모양(둥근 네모·원) 밖으로 얼굴이 삐져나오지 않게 다시 깎는다
      const shape = round === 'circle' ? `<circle cx="${n / 2}" cy="${n / 2}" r="${n / 2}"/>` : `<rect width="${n}" height="${n}" rx="${n * 0.22}"/>`;
      const mask = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${n}" height="${n}">${shape}</svg>`);
      const img = await sharp(bg(n, n, round)).composite([{ input: fg, left: off, top: off + Math.round(n * 0.04) }]).png().toBuffer();
      await sharp(img).composite([{ input: mask, blend: 'dest-in' }]).png().toFile(path.join(dir, name));
    }
    // 새 방식(적응형) 아이콘 앞그림: 108dp 중 가운데 66dp 안전 구역에 얼굴
    const N = Math.round(n * 108 / 48), F = Math.round(N * 0.64);
    const fg2 = await sharp(face).resize(F, F).png().toBuffer();
    await sharp({ create: { width: N, height: N, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
      .composite([{ input: fg2, left: Math.round((N - F) / 2), top: Math.round((N - F) / 2 + N * 0.025) }]).png().toFile(path.join(dir, 'ic_launcher_foreground.png'));
  }
  // 적응형 아이콘 뒷그림: 하늘→새싹 그라데이션
  fs.mkdirSync(path.join(res, 'drawable'), { recursive: true });
  fs.writeFileSync(path.join(res, 'drawable', 'sm_icon_bg.xml'), `<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient android:angle="270" android:startColor="#BFE4FF" android:centerColor="#D9F0C4" android:endColor="#A9DB8C" android:type="linear" />
</shape>
`);
  const adaptive = `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/sm_icon_bg"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
`;
  fs.mkdirSync(path.join(res, 'mipmap-anydpi-v26'), { recursive: true });
  fs.writeFileSync(path.join(res, 'mipmap-anydpi-v26', 'ic_launcher.xml'), adaptive);
  fs.writeFileSync(path.join(res, 'mipmap-anydpi-v26', 'ic_launcher_round.xml'), adaptive);

  // 첫 화면(앱 켤 때 잠깐): 게임 불러오기 화면과 같은 색 + 주인공
  for (const d of fs.readdirSync(res)) {
    const f = path.join(res, d, 'splash.png');
    if (!d.startsWith('drawable') || !fs.existsSync(f)) continue;
    const { width: w, height: h } = await sharp(f).metadata();
    const s = Math.round(Math.min(w, h) * 0.8);
    const kid = await sharp(portrait).resize(s, s).png().toBuffer();
    const back = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef4fb"/><stop offset="1" stop-color="#d6e2f0"/></linearGradient></defs><rect width="${w}" height="${h}" fill="url(#g)"/></svg>`);
    const out = await sharp(back).composite([{ input: kid, left: Math.round((w - s) / 2), top: Math.round((h - s) / 2) }]).png().toBuffer();
    const small = await sharp(out).png({ palette: true, quality: 95, compressionLevel: 9 }).toBuffer();   // 색 수 줄여 가볍게
    fs.writeFileSync(f, small.length < out.length ? small : out);
  }
  say('아이콘·첫 화면 그림 만듦');
}

// ------------------------------------------------------------------ 4) 출시용 서명 열쇠 (처음 한 번)
// properties 파일은 한글을 \uXXXX 로 적어야 자바가 바르게 읽는다 (경로 C:\시라이스 때문)
const propEsc = (s) => s.replace(/[^\x20-\x7e]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
function ensureKeystore() {
  const props = path.join(KEYDIR, 'keystore.properties');
  const jks = path.join(KEYDIR, 'springmarch-release.jks');
  // (잃어버리면 같은 앱으로 업데이트를 못 한다 — 이 폴더는 백업, 저장소에는 절대 올리지 않는다)
  const write = (pass) => fs.writeFileSync(props, `# Spring March release signing key. Back up this folder. Never commit it.\nstoreFile=${propEsc(jks.split(path.sep).join('/'))}\nstorePassword=${pass}\nkeyAlias=springmarch\nkeyPassword=${pass}\n`);
  if (fs.existsSync(props)) {
    const txt = fs.readFileSync(props, 'utf8');
    if (/[^\x00-\x7e]/.test(txt)) write((txt.match(/^storePassword=(.*)$/m) || [])[1].trim());   // 옛 판(한글 그대로) 고치기
    return props;
  }
  fs.mkdirSync(KEYDIR, { recursive: true });
  const pass = crypto.randomBytes(18).toString('base64').replace(/[^A-Za-z0-9]/g, 'x');
  run(path.join(T.jdk, 'bin', 'keytool.exe'), ['-genkeypair', '-keystore', jks, '-storetype', 'PKCS12', '-alias', 'springmarch', '-keyalg', 'RSA', '-keysize', '2048',
    '-validity', '10000', '-storepass', pass, '-keypass', pass, '-dname', 'CN=Spring March, O=Spring March, C=KR'], KEYDIR);
  write(pass);   // 경로는 / 로 쓴다 (properties 파일에서 \ 는 특수 문자)
  say('출시용 서명 열쇠를 만들었어요:', KEYDIR);
  return props;
}

// ------------------------------------------------------------------ 실행
const t0 = Date.now();
if (args.has('--setup')) await setupTools();
await buildWeb();
if (!args.has('--web-only')) {
  const miss = checkTools();
  if (miss.length) { console.error('[android] 도구가 없어요:\n  ' + miss.join('\n  ') + '\n  → node tools/build/build_android.mjs --setup 으로 설치하세요'); process.exit(1); }
  await prepareNative();
  run('npx', ['cap', 'sync', 'android'], APP);
  const release = !args.has('--no-release');
  if (release) ENV.SM_KEYSTORE_PROPS = ensureKeystore();
  run(path.join(NATIVE, 'gradlew.bat'), ['--no-daemon', '--console=plain', 'assembleDebug', ...(release ? ['assembleRelease'] : [])], NATIVE);
  // 결과물: .cache/release/ 바로 아래 + 보관용 .cache/release/android/ (PC 설치판 빌드가 release/ 의 '봄날의행진-*' 를 지울 때를 대비)
  const KEEP = path.join(RELEASE, 'android');
  fs.mkdirSync(KEEP, { recursive: true });
  const outs = [['debug', path.join(NATIVE, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')]];
  if (release) outs.push(['release', path.join(NATIVE, 'app', 'build', 'outputs', 'apk', 'release', 'app-release.apk')]);
  for (const [kind, f] of outs) {
    if (!fs.existsSync(f)) { say('없음:', f); continue; }
    const name = `봄날의행진-${VERSION}-${kind}.apk`;
    fs.copyFileSync(f, path.join(KEEP, name));
    fs.copyFileSync(f, path.join(RELEASE, name));
    say(`완성 ${kind}: ${path.join(RELEASE, name)} (${mb(fs.statSync(f).size)}) — 보관본: ${path.join(KEEP, name)}`);
  }
}
say(`끝 (${((Date.now() - t0) / 1000).toFixed(0)}초)`);
