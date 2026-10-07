// Pad payment persistence with frame-based waits:
//  A. upgrade pad keeps the previous level's full price as "paid" in the save -> discount after reload
//  B. reload in the middle of an unlock payment (coins + paid conserved?)
//  C. standing on an upgrade pad keeps buying level after level (standT not reset on rearm)
//   node tools/test/review_robust_pads.mjs
import { newPage, bootToGame, launch, start, sleep, waitFor, tapStart, writeJSON } from './review_robust_lib.mjs';

const srv = await start(0, { prefix: '/fv/' });
const URL = srv.url + 'index.html';
const browser = await launch();
const KEY = 'frostVillage.save.v1';
const out = {};
const hide = (page) => page.evaluate(() => { const g = window.__FV.game; for (const k of ['Game', 'UI']) g.scene.getScene(k).cameras.main.setVisible(false); });
const reboot = async (page) => {
  await page.reload({ waitUntil: 'load' });
  await waitFor(page, () => window.__FV && window.__FV.game && window.__FV.game.scene.isActive('Title'), 90000);
  await sleep(300); await tapStart(page);
  await waitFor(page, () => window.__FV.state && window.__FV.game.scene.isActive('UI'), 90000);
  await hide(page);
};
const FR = `const W = (n, cond) => new Promise((res) => { const g = window.__FV.game, f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= n || (cond && cond())) { clearInterval(iv); res(g.loop.frame - f0); } }, 10); });`;

// ---------------- A
{
  const { page, ctx, log } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  out.upgradeStalePaid = await page.evaluate(new Function(`return (async () => { ${FR}
    const FV = window.__FV, gs = FV.scene;
    FV.unlockAll();
    FV.give(60 - FV.state().coins);
    const pad = FV.where('up_capacity');
    FV.teleport(pad.x, pad.y);
    await W(2000, () => FV.state().upgrades.capacity >= 1);
    const lvl = FV.state().upgrades.capacity;
    const savedRightAfter = JSON.parse(localStorage.getItem('frostVillage.save.v1')).progress.paid;
    FV.teleport(pad.x + 250, pad.y + 150);
    await W(120);
    FV.save();
    const savedLater = JSON.parse(localStorage.getItem('frostVillage.save.v1')).progress.paid;
    const p = gs.progress.upPads.capacity;
    return { lvl, coinsLeft: FV.state().coins, savedPaidRightAfterUpgrade: savedRightAfter, savedPaidAfterStepOff: savedLater, padInMemory: { cost: p.cost, paid: p.paid } };
  })()`));
  await reboot(page);
  out.upgradeStalePaid.afterReload = await page.evaluate(() => { const p = window.__FV.scene.progress.upPads.capacity; return { level: window.__FV.state().upgrades.capacity, cost: p.cost, paid: p.paid, remaining: p.remaining, label: p.costText.text, coins: window.__FV.state().coins }; });
  out.upgradeStalePaid.errors = log.errors;
  console.log('upgradeStalePaid', JSON.stringify(out.upgradeStalePaid));
  await ctx.close();
}

// ---------------- B
{
  const res = [];
  for (const target of [150, 400]) {
    const { page, ctx } = await newPage(browser);
    const save = { v: 1, coins: 1000, progress: { done: { hire_fisherman: true, zone_forest: true, hire_lumberjack: true, zone_farm: true, hire_farmer: true, zone_mine: true, hire_miner: true }, paid: {}, up: {} }, stations: {}, market: { stock: {}, cash: 0 }, trade: { stock: {}, cash: 0 }, player: { x: 900, y: 1150, stack: [] } };
    await page.addInitScript(([k, v]) => { if (!sessionStorage.getItem('__seeded')) { sessionStorage.setItem('__seeded', '1'); localStorage.setItem(k, v); } }, [KEY, JSON.stringify(save)]);
    await bootToGame(page, URL, { fresh: false });
    await hide(page);
    const m = await page.evaluate(new Function('target', `return (async () => { ${FR}
      const FV = window.__FV, pad = FV.scene.progress.pads.zone_hunt;
      FV.teleport(pad.x, pad.y);
      await W(3000, () => pad.paid >= target);
      return { coins: FV.state().coins, paid: pad.paid, sum: FV.state().coins + pad.paid };
    })()`), target);
    await reboot(page);
    const after = await page.evaluate(() => { const FV = window.__FV, p = FV.scene.progress.pads.zone_hunt; return { coins: FV.state().coins, paid: p ? p.paid : 'done', pos: [FV.state().player.x, FV.state().player.y], padPos: p && [p.x, p.y] }; });
    res.push({ target, atReload: m, afterReload: after, conserved: after.coins + after.paid === 1000 });
    await ctx.close();
  }
  out.reloadDuringPayment = res;
  console.log('reloadDuringPayment', JSON.stringify(res));
}

// ---------------- C
{
  const { page, ctx } = await newPage(browser);
  await bootToGame(page, URL);
  await hide(page);
  out.upgradeKeepsBuying = await page.evaluate(new Function(`return (async () => { ${FR}
    const FV = window.__FV; FV.unlockAll(); FV.give(5000);
    const pad = FV.where('up_speed'); FV.teleport(pad.x, pad.y);
    const g = FV.game, t0 = g.loop.frame; const log = [];
    let last = FV.state().upgrades.speed;
    await W(1500, () => { const l = FV.state().upgrades.speed; if (l !== last) { log.push({ level: l, frame: g.loop.frame - t0, coins: FV.state().coins }); last = l; } return l >= 4; });
    return { levelsBoughtWithoutLeavingPad: log, finalCoins: FV.state().coins };
  })()`));
  console.log('upgradeKeepsBuying', JSON.stringify(out.upgradeKeepsBuying));
  await ctx.close();
}
writeJSON('pads_results.json', out);
await browser.close(); await srv.close();
