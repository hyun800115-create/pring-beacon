// 3D 페이지 스크린샷: node tools/test/shot3d.mjs <페이지?쿼리> <출력.png> [기다릴ms] [--gpu]
import { start } from './serve.mjs';
import { launch } from './pw.mjs';
import { chromium } from 'playwright';
const [pg, out, wait] = process.argv.slice(2);
const gpu = process.argv.includes('--gpu');
const srv = await start(0);
const b = gpu ? await chromium.launch({ headless: true, args: ['--ignore-gpu-blocklist', '--use-angle=d3d11', '--enable-gpu'] }) : await launch();
const page = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e.stack || e))); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
await page.goto(srv.url + pg);
try { await page.waitForFunction(() => window.__ready, null, { timeout: 60000 }); } catch (e) { errs.push('not ready'); }
await new Promise((r) => setTimeout(r, Number(wait || 1500)));
await page.screenshot({ path: out });
console.log('errors', errs.slice(0, 10));
await b.close(); await srv.close();
