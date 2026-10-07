// 봄날의 행진 (3D) 플레이 링크용 묶음 만들기.
//   node tools/build/build_play3d.mjs [출력폴더]   (기본: 저장소/.cache/dist3d)
// 결과: index.html(본문만) + game.js(코드+three.js 한 파일) + assets(소리·땅·감정) + assets3d(GLB: 그림 WebP, 모양 meshopt 압축)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { textureCompress, meshopt, dedup, prune } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, '..', '.cache', 'dist3d'));
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

await build({
  entryPoints: [path.join(ROOT, 'src', 'main.js')], bundle: true, format: 'esm', minify: true,
  target: ['es2020'], outfile: path.join(OUT, 'game.js'), logLevel: 'warning', nodePaths: [path.join(ROOT, 'node_modules')],
});

const css = fs.readFileSync(path.join(ROOT, 'src', 'ui', 'hud.css'), 'utf8').replace(/url\(\.\.\/\.\.\/assets\//g, 'url(assets/');
let html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const title = html.match(/<title>[\s\S]*?<\/title>/)[0];
const body = html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>')).replace('<script type="module" src="src/main.js"></script>', '<script type="module" src="game.js"></script>');
fs.writeFileSync(path.join(OUT, 'index.html'), `${title}\n<style>\n${css}\n</style>\n<script>window.__SM_GLB = '.glb.wasm';</script>\n${body.trim()}\n`);

const copy = (rel) => { const s = path.join(ROOT, rel); if (fs.existsSync(s)) fs.cpSync(s, path.join(OUT, rel), { recursive: true }); };
for (const f of ['assets/ground/ground_snow.png', 'assets/ground/ground_dirt.png', 'assets/ground/ground_rock.png', 'assets/ground/ground_plaza.png',
  'assets/emotes/emotes.png', 'assets/emotes/emotes.json', 'assets/characters/portrait_player.png']) copy(f);
for (const f of fs.readdirSync(path.join(ROOT, 'assets', 'audio'))) if (f.endsWith('.mp3') || f.endsWith('.ogg')) copy('assets/audio/' + f);

// GLB 압축
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
let before = 0, after = 0;
for (const dir of ['chars', 'props', 'buildings']) {   // 가구는 건물 안에 이미 들어 있음
  const src = path.join(ROOT, 'assets3d', dir);
  if (!fs.existsSync(src)) continue;
  fs.mkdirSync(path.join(OUT, 'assets3d', dir), { recursive: true });
  for (const f of fs.readdirSync(src)) {
    const sp = path.join(src, f), dp = path.join(OUT, 'assets3d', dir, f.endsWith('.glb') ? f + '.wasm' : f);   // 서버가 .glb 를 안 받아서 이름만 바꿈
    if (f.endsWith('.json')) { fs.copyFileSync(sp, dp); continue; }
    if (!f.endsWith('.glb')) continue;
    const doc = await io.read(sp);
    // 주민(동작 있음)은 모양 압축을 하지 않는다: 압축이 관절 크기 값을 바꾸면 동작이 그걸 덮어써서 모양이 깨진다
    if (dir === 'chars') await doc.transform(dedup());
    else await doc.transform(dedup(), prune(), textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 82, resize: [1024, 1024] }), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
    fs.writeFileSync(dp, await io.writeBinary(doc));   // 이름이 .wasm 이라도 GLB(바이너리)로 쓴다
    before += fs.statSync(sp).size; after += fs.statSync(dp).size;
  }
}
const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else files.push(path.relative(OUT, p).split(path.sep).join('/')); } };
walk(OUT);
const size = files.reduce((a, f) => a + fs.statSync(path.join(OUT, f)).size, 0);
fs.writeFileSync(path.join(OUT, 'files.json'), JSON.stringify(files.filter((f) => f !== 'index.html' && f !== 'files.json').map((p) => ({ path: p }))));
console.log(`[build3d] GLB ${(before / 1048576).toFixed(1)}MB → ${(after / 1048576).toFixed(1)}MB, 전체 ${files.length}개 ${(size / 1048576).toFixed(1)}MB → ${OUT}`);
