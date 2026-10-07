// 봄날의 행진: 플레이 링크(Claude 아티팩트)용 묶음 만들기.
//   node tools/build/build_play.mjs [출력폴더]   (기본: 저장소/.cache/dist_play)
// 결과: index.html(본문만, 스타일 포함) + game.js(코드 한 파일) + lib/phaser.min.js + assets/**
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, '..', '.cache', 'dist_play'));

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });

await build({
  entryPoints: [path.join(ROOT, 'src', 'main.js')], bundle: true, format: 'iife', minify: true,
  target: ['es2020'], outfile: path.join(OUT, 'game.js'), logLevel: 'warning',
});

const css = fs.readFileSync(path.join(ROOT, 'src', 'ui', 'hud.css'), 'utf8');
let html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const title = html.match(/<title>[\s\S]*?<\/title>/)[0].replace('봄날의 행진 · 시제품', '봄날의 행진');
const body = html.slice(html.indexOf('<body>') + 6, html.indexOf('</body>'))
  .replace('<script type="module" src="src/main.js"></script>', '<script src="game.js"></script>');
html = `${title}\n<style>\n${css}\n</style>\n${body.trim()}\n`;
fs.writeFileSync(path.join(OUT, 'index.html'), html);

const copy = (rel) => {
  const src = path.join(ROOT, rel), dst = path.join(OUT, rel);
  fs.cpSync(src, dst, { recursive: true });
};
copy('lib/phaser.min.js');
copy('assets');

const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else files.push(path.relative(OUT, p).split(path.sep).join('/')); } };
walk(OUT);
const size = files.reduce((a, f) => a + fs.statSync(path.join(OUT, f)).size, 0);
fs.writeFileSync(path.join(OUT, 'files.json'), JSON.stringify(Object.fromEntries(files.filter((f) => f !== 'index.html' && f !== 'files.json').map((f) => [f, path.join(OUT, f)])), null, 1));
console.log(`[build] ${files.length}개 파일, ${(size / 1048576).toFixed(1)}MB → ${OUT}`);
