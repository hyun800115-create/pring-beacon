// Which requests fail during a normal boot? (prints requestfailed / >=400 responses)
import { newPage, bootToGame, launch, start, sleep } from './review_robust_lib.mjs';
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser);
const fails = [];
page.on('requestfailed', (r) => fails.push(r.url().replace(srv.url, '') + ' :: ' + (r.failure() && r.failure().errorText) + ' :: ' + r.resourceType()));
await bootToGame(page, srv.url + 'index.html');
await sleep(2000);
console.log('failed', fails.length); console.log(fails.slice(0, 40).join('\n'));
console.log('errors', log.errors.length, log.errors.slice(0, 5).join('\n'));
console.log('warnings', [...new Set(log.warnings)].join('\n'));
console.log('all console', log.all.filter((x) => !x.startsWith('log')).slice(0, 20).join('\n'));
await browser.close(); await srv.close();
