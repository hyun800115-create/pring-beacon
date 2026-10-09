// 봄날의 행진 — 윈도우 PC 앱(설치판·바로 실행판) 만들기.
//   node tools/build/build_app.mjs            게임 파일 묶기 + 아이콘 + 설치 파일·바로 실행 파일까지
//   node tools/build/build_app.mjs --www-only 게임 파일 묶기(+아이콘)만 (앱 시험용, 빠름)
//   node tools/build/build_app.mjs --no-compress  GLB 압축 없이 그대로 복사
// 결과:
//   저장소/.cache/app-pc/www/        완전한 게임 파일 한 벌 (index.html + game.js + hud.css + assets + assets3d)
//   저장소/.cache/app-pc/build/      설치 파일용 아이콘 (icon.ico)
//   저장소/.cache/release/           봄날의행진-설치-<판>.exe, 봄날의행진-바로실행-<판>.exe, win-unpacked/
// 앱 코드는 game/app/pc (main.js, package.json). 처음 한 번은 game/app/pc 에서 npm install.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { build } from 'esbuild';
import { NodeIO, Logger } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { textureCompress, meshopt, dedup, prune } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');            // game/
const REPO = path.resolve(ROOT, '..');                  // 저장소
const APP = path.join(ROOT, 'app', 'pc');
const CACHE = path.join(REPO, '.cache');
const BASE = path.join(CACHE, 'app-pc');
const OUT = path.join(BASE, 'www');
const GLB_CACHE = path.join(BASE, 'glb-cache');          // 압축한 GLB 를 다시 쓰기 (원본이 안 바뀌면)
const RES = path.join(BASE, 'build');
const RELEASE = path.join(CACHE, 'release');
const args = process.argv.slice(2);
const wwwOnly = args.includes('--www-only');
const compress = !args.includes('--no-compress');
const t0 = Date.now();
const say = (...a) => console.log('[app]', ...a);
const mb = (n) => (n / 1048576).toFixed(1) + 'MB';

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(GLB_CACHE, { recursive: true });
fs.mkdirSync(RES, { recursive: true });

// ---------------------------------------------------------------- 1. 코드 묶기 (three.js 까지 한 파일)
await build({
  entryPoints: [path.join(ROOT, 'src', 'main.js')], bundle: true, format: 'esm', minify: true,
  target: ['chrome130'], outfile: path.join(OUT, 'game.js'), logLevel: 'warning', nodePaths: [path.join(ROOT, 'node_modules')],
  legalComments: 'none',
});
const code = fs.readFileSync(path.join(OUT, 'game.js'), 'utf8');

// ---------------------------------------------------------------- 2. 화면 꾸밈(CSS) + 완전한 HTML 문서
const css = fs.readFileSync(path.join(ROOT, 'src', 'ui', 'hud.css'), 'utf8').replace(/url\((['"]?)\.\.\/\.\.\/assets\//g, 'url($1assets/');
// (좁은 창 배치·분류 칸 한 줄은 본판 hud.css 가 직접 맡는다 — 가로 1279 이하면 작은 배치)
fs.writeFileSync(path.join(OUT, 'hud.css'), css);
let html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
html = html.replace(/<script type="importmap">[\s\S]*?<\/script>\s*/, '');                     // three 는 game.js 안에 들어 있다
html = html.replace(/href="src\/ui\/hud\.css"/, 'href="hud.css"');
html = html.replace(/<script type="module" src="src\/main\.js"><\/script>/, '<script type="module" src="game.js"></script>');
// 앱 밖의 것은 아무것도 불러오지 않게 (보안), WebAssembly(모양 압축 풀기)는 허락
const csp = "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
  + "img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self' data: blob:; worker-src 'self' blob:; font-src 'self' data:";
html = html.replace('<meta charset="utf-8">', `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${csp}">`);
if (!/^<!doctype html>/i.test(html.trim())) html = '<!doctype html>\n' + html;
for (const must of ['game.js', 'hud.css']) if (!html.includes(must)) throw new Error('index.html 바꾸기 실패: ' + must);
if (html.includes('importmap') || html.includes('src/main.js')) throw new Error('index.html 에 개발용 줄이 남았어요');
fs.writeFileSync(path.join(OUT, 'index.html'), html);

// ---------------------------------------------------------------- 3. 그림·소리 복사
const copied = new Set();
const copy = (rel) => {
  const s = path.join(ROOT, rel);
  if (!fs.existsSync(s) || copied.has(rel)) return false;
  fs.mkdirSync(path.dirname(path.join(OUT, rel)), { recursive: true });
  fs.cpSync(s, path.join(OUT, rel), { recursive: true });
  copied.add(rel);
  return true;
};
const copyDir = (rel, test = () => true) => {
  const d = path.join(ROOT, rel);
  if (!fs.existsSync(d)) return;
  for (const f of fs.readdirSync(d)) if (fs.statSync(path.join(d, f)).isFile() && test(f)) copy(rel + '/' + f);
};
copyDir('assets/ground', (f) => /\.(png|webp|jpg|json)$/i.test(f));      // 땅·길 (계절 땅 그림도)
copyDir('assets/emotes');                                                 // 말풍선 감정
copyDir('assets/audio', (f) => /\.(mp3|ogg|wav|json)$/i.test(f));         // 소리
copyDir('assets/characters', (f) => /^portrait_player.*\.png$/i.test(f)); // 주인공 얼굴 (아이콘)
// 코드 안에 글자로 적힌 assets 경로도 빠짐없이 (다른 팀이 새 그림을 더해도 따라오게)
const missing = [];
for (const m of code.matchAll(/assets(?:3d)?\/[A-Za-z0-9_\-./]+\.(?:png|webp|jpg|json|mp3|ogg|wav|glb)/g)) {
  const rel = m[0];
  if (rel.startsWith('assets3d/')) continue;   // 3D 모델은 아래에서 통째로
  if (!copied.has(rel) && !copy(rel) && !fs.existsSync(path.join(OUT, rel))) missing.push(rel);
}
if (missing.length) say('코드에 있지만 파일이 없는 경로:', [...new Set(missing)].join(', '));

// ---------------------------------------------------------------- 4. 3D 모델 (이름은 .glb 그대로, 압축은 원본이 바뀔 때만 다시)
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder }).setLogger(new Logger(Logger.Verbosity.WARN));
let before = 0, after = 0, fresh = 0, reused = 0;
for (const dir of ['chars', 'props', 'buildings']) {   // 가구는 건물 GLB 안에 이미 들어 있다
  const src = path.join(ROOT, 'assets3d', dir);
  if (!fs.existsSync(src)) continue;
  fs.mkdirSync(path.join(OUT, 'assets3d', dir), { recursive: true });
  for (const f of fs.readdirSync(src)) {
    const sp = path.join(src, f), dp = path.join(OUT, 'assets3d', dir, f);
    if (!fs.statSync(sp).isFile()) continue;
    if (f.endsWith('.json')) { fs.copyFileSync(sp, dp); continue; }
    if (!f.endsWith('.glb')) continue;
    before += fs.statSync(sp).size;
    if (!compress) { fs.copyFileSync(sp, dp); after += fs.statSync(dp).size; continue; }
    const buf = fs.readFileSync(sp);
    const key = createHash('sha1').update(dir).update('|v2|').update(buf).digest('hex').slice(0, 16);
    const cp = path.join(GLB_CACHE, `${dir}__${f}.${key}`);
    if (fs.existsSync(cp)) { fs.copyFileSync(cp, dp); reused++; }
    else {
      const doc = await io.read(sp);
      // 주민·동물(동작 있음)은 모양 압축을 하지 않는다: 압축이 관절 크기 값을 바꾸면 동작이 덮어써서 모양이 깨진다
      if (dir === 'chars') await doc.transform(dedup());
      else await doc.transform(dedup(), prune(), textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 88, resize: [2048, 2048] }), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
      const outBuf = await io.writeBinary(doc);
      // 옛 캐시(같은 파일의 다른 판)는 지운다
      for (const old of fs.readdirSync(GLB_CACHE)) if (old.startsWith(`${dir}__${f}.`)) fs.rmSync(path.join(GLB_CACHE, old));
      fs.writeFileSync(cp, outBuf); fs.writeFileSync(dp, outBuf); fresh++;
    }
    after += fs.statSync(dp).size;
  }
}
say(`3D 모델 ${mb(before)} → ${mb(after)} (새로 압축 ${fresh}, 다시 씀 ${reused})`);

// ---------------------------------------------------------------- 5. 아이콘 (하늘색→봄풀색 둥근 판 위에 주인공 상반신 → .ico, 여러 크기 PNG 를 담는다)
const face = path.join(ROOT, 'assets', 'characters', fs.existsSync(path.join(ROOT, 'assets/characters/portrait_player_512.png')) ? 'portrait_player_512.png' : 'portrait_player.png');
const fm = await sharp(face).metadata();
const fk = fm.width / 512;   // 원본 그림 크기 비율 (512 기준으로 잡은 자르기 자리)
async function iconPng(s) {
  const rx = Math.round(s * 0.22);
  const plate = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">`
    + `<stop offset="0" stop-color="#a6d6ff"/><stop offset="1" stop-color="#e2f6cc"/></linearGradient></defs>`
    + `<rect width="${s}" height="${s}" rx="${rx}" fill="url(#g)"/></svg>`);
  const mask = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}"><rect width="${s}" height="${s}" rx="${rx}" fill="#fff"/></svg>`);
  // 작은 아이콘은 얼굴만 크게, 큰 아이콘은 손 흔드는 상반신
  const c = s <= 24 ? [150, 72, 212] : [96, 58, 316];
  const cs = Math.round(s * (s <= 24 ? 1 : 0.98));
  const ch = await sharp(face).extract({ left: Math.round(c[0] * fk), top: Math.round(c[1] * fk), width: Math.round(c[2] * fk), height: Math.round(c[2] * fk) })
    .resize(cs, cs, { kernel: 'lanczos3' }).png().toBuffer();
  const base = await sharp(plate).png().toBuffer();
  const withChar = await sharp(base).composite([{ input: ch, left: Math.round((s - cs) / 2), top: s - cs + Math.round(s * 0.04) }]).png().toBuffer();
  return sharp(withChar).composite([{ input: mask, blend: 'dest-in' }]).png().toBuffer();
}
const sizes = [256, 128, 64, 48, 32, 24, 16];
const pngs = [];
for (const s of sizes) pngs.push(await iconPng(s));
const head = Buffer.alloc(6 + 16 * sizes.length);
head.writeUInt16LE(0, 0); head.writeUInt16LE(1, 2); head.writeUInt16LE(sizes.length, 4);
let off = head.length;
sizes.forEach((s, i) => {
  const e = 6 + i * 16;
  head.writeUInt8(s >= 256 ? 0 : s, e); head.writeUInt8(s >= 256 ? 0 : s, e + 1);
  head.writeUInt8(0, e + 2); head.writeUInt8(0, e + 3); head.writeUInt16LE(1, e + 4); head.writeUInt16LE(32, e + 6);
  head.writeUInt32LE(pngs[i].length, e + 8); head.writeUInt32LE(off, e + 12);
  off += pngs[i].length;
});
const ico = Buffer.concat([head, ...pngs]);
fs.writeFileSync(path.join(RES, 'icon.ico'), ico);
fs.writeFileSync(path.join(OUT, 'icon.ico'), ico);                // 창 아이콘
fs.writeFileSync(path.join(RES, 'icon.png'), pngs[0]);

// ---------------------------------------------------------------- 6. 정리
const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else files.push(p); } };
walk(OUT);
const total = files.reduce((a, f) => a + fs.statSync(f).size, 0);
say(`게임 파일 ${files.length}개 ${mb(total)} → ${OUT}`);

// ---------------------------------------------------------------- 7. 설치 파일·바로 실행 파일
if (!wwwOnly) {
  const builderCli = path.join(APP, 'node_modules', 'electron-builder', 'cli.js');
  if (!fs.existsSync(builderCli)) { console.error('[app] game/app/pc 에서 먼저 npm install 을 해 주세요'); process.exit(1); }
  // 지난번 PC 판 결과물만 지우기 (안드로이드 .apk 처럼 다른 팀의 결과물은 남긴다)
  if (fs.existsSync(RELEASE)) for (const f of fs.readdirSync(RELEASE)) {
    if (/^봄날의행진-(설치|바로실행)-.*\.(exe|exe\.blockmap)$/i.test(f) || /^(win-unpacked|builder-debug\.yml|builder-effective-config\.yaml|latest\.yml)$/.test(f)) fs.rmSync(path.join(RELEASE, f), { recursive: true, force: true });
  }
  const env = Object.assign({}, process.env, {
    ELECTRON_CACHE: path.join(CACHE, 'electron'), electron_config_cache: path.join(CACHE, 'electron'),
    ELECTRON_BUILDER_CACHE: path.join(CACHE, 'electron-builder'),
    CSC_IDENTITY_AUTO_DISCOVERY: 'false',       // 코드 서명 없음
  });
  say('설치 파일 만드는 중… (몇 분 걸려요)');
  const r = spawnSync(process.execPath, [builderCli, '--win', 'nsis', 'portable', '--x64', '--publish', 'never'], { cwd: APP, env, stdio: 'inherit' });
  if (r.status !== 0) { console.error('[app] 설치 파일 만들기 실패'); process.exit(r.status || 1); }
  for (const f of fs.readdirSync(RELEASE)) if (/^봄날의행진-.*\.exe$/i.test(f)) say(`  ${f}  ${mb(fs.statSync(path.join(RELEASE, f)).size)}`);
  say(`풀어 둔 앱: ${path.join(RELEASE, 'win-unpacked')}`);
}
say(`끝 (${((Date.now() - t0) / 1000).toFixed(0)}초)`);
