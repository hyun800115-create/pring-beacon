// Safety net for hand-edited balance.js values. A typo (0, a negative number, text, a missing
// line) must never make a pad that cannot be completed or freeze the game, so every value the
// code depends on is checked once at start-up; anything unusable is replaced by a safe value and
// reported in the browser console (F12) as "[balance.js] ...".

import { BALANCE } from './balance.js';

const DEFAULT_COST = 100;

function warn(path, was, now) {
  try { console.warn('[balance.js] ' + path + ' = ' + JSON.stringify(was) + ' is not usable, using ' + JSON.stringify(now) + ' instead'); } catch (e) { /* */ }
}

/** fix BALANCE[path] in place: number within [min, max] (optionally a whole number) */
function fixNum(obj, key, path, min, max, def, int) {
  if (!obj || typeof obj !== 'object') return;
  const v = obj[key];
  let n = v === undefined || v === null || v === '' ? NaN : (typeof v === 'number' ? v : Number(v));
  if (!Number.isFinite(n)) n = def;
  if (int) n = Math.round(n);
  n = Math.max(min, Math.min(max, n));
  if (n !== v) { if (!(v === undefined && OPTIONAL.has(path))) warn(path, v, n); obj[key] = n; }
}

// settings that older balance.js files may not have yet (filled in silently)
const OPTIONAL = new Set(['player.trashDelay', 'customers.shelfMax', 'trade.shelfMax', 'workers.porterCapacity']);

function fixList(arr, path, min, max, int) {
  if (!Array.isArray(arr)) return;
  for (let i = 0; i < arr.length; i++) fixNum(arr, i, path + '[' + i + ']', min, max, arr[i - 1] !== undefined ? arr[i - 1] : min, int);
}

export function checkBalance() {
  const B = BALANCE;
  if (!B || typeof B !== 'object') return;
  B.player = B.player || {};
  fixNum(B.player, 'speed', 'player.speed', 20, 2000, 255);
  fixNum(B.player, 'verticalFactor', 'player.verticalFactor', 0.2, 2, 0.74);
  fixNum(B.player, 'gatherRange', 'player.gatherRange', 10, 400, 78);
  fixNum(B.player, 'padDelay', 'player.padDelay', 0, 5, 0.5);
  fixNum(B.player, 'trashDelay', 'player.trashDelay', 0.1, 5, 0.6);
  fixNum(B.player, 'padItemInterval', 'player.padItemInterval', 0.01, 2, 0.075);
  fixNum(B.player, 'carryScale', 'player.carryScale', 0.1, 3, 0.62);
  fixNum(B, 'payDuration', 'payDuration', 0.1, 60, 1.6);
  fixNum(B, 'autosaveEvery', 'autosaveEvery', 1, 600, 5);
  // costs: whole coins, at least 1 (0 would make a pad that never completes)
  B.costs = B.costs || {};
  for (const k of ['hire_fisherman', 'zone_forest', 'hire_lumberjack', 'zone_farm', 'hire_farmer', 'zone_mine', 'hire_miner', 'zone_hunt', 'hire_hunter',
    'hire2_fisherman', 'hire2_lumberjack', 'hire2_farmer', 'hire2_miner', 'hire2_hunter']) fixNum(B.costs, k, 'costs.' + k, 1, 1e9, DEFAULT_COST, true);
  // prices: whole coins >= 1
  B.prices = B.prices || {};
  for (const k of ['item_fish_cooked', 'item_bread', 'item_meat_cooked', 'item_plank', 'item_ingot']) fixNum(B.prices, k, 'prices.' + k, 1, 1e6, 1, true);
  // upgrades: values >= something, costs whole >= 1, exactly values.length - 1 costs
  B.upgrades = B.upgrades || {};
  const UP = { capacity: { min: 1, max: 500, int: true, def: [6] }, speed: { min: 0.2, max: 5, int: false, def: [1] } };
  for (const kind in UP) {
    const u = B.upgrades[kind] = B.upgrades[kind] || {};
    if (!Array.isArray(u.values) || !u.values.length) { warn('upgrades.' + kind + '.values', u.values, UP[kind].def); u.values = UP[kind].def.slice(); }
    fixList(u.values, 'upgrades.' + kind + '.values', UP[kind].min, UP[kind].max, UP[kind].int);
    if (!Array.isArray(u.costs)) u.costs = [];
    fixList(u.costs, 'upgrades.' + kind + '.costs', 1, 1e9, true);
    while (u.costs.length < u.values.length - 1) { const c = (u.costs[u.costs.length - 1] || 100) * 2; warn('upgrades.' + kind + '.costs[' + u.costs.length + ']', undefined, c); u.costs.push(c); }
  }
  B.stations = B.stations || {};
  for (const id of ['grill', 'sawmill', 'bakery', 'smelter', 'smokehouse']) {
    const st = B.stations[id] = B.stations[id] || {};
    fixNum(st, 'time', 'stations.' + id + '.time', 0.05, 600, 1.2);
    fixNum(st, 'inputMax', 'stations.' + id + '.inputMax', 1, 500, 30, true);
    fixNum(st, 'outputMax', 'stations.' + id + '.outputMax', 1, 500, 36, true);
  }
  B.customers = B.customers || {};
  const C = B.customers;
  fixNum(C, 'spawnEvery', 'customers.spawnEvery', 0.3, 600, 2.6);
  fixNum(C, 'maxQueue', 'customers.maxQueue', 1, 30, 6, true);
  fixNum(C, 'wantMin', 'customers.wantMin', 1, 50, 1, true);
  fixNum(C, 'wantMax', 'customers.wantMax', C.wantMin, 50, 3, true);
  fixNum(C, 'wantMaxLate', 'customers.wantMaxLate', C.wantMin, 50, 5, true);
  fixNum(C, 'takeInterval', 'customers.takeInterval', 0.02, 10, 0.2);
  fixNum(C, 'speed', 'customers.speed', 20, 1000, 120);
  fixNum(C, 'shelfMax', 'customers.shelfMax', 1, 500, 40, true);
  B.trade = B.trade || {};
  fixNum(B.trade, 'buyInterval', 'trade.buyInterval', 0.02, 60, 0.28);
  fixNum(B.trade, 'shelfMax', 'trade.shelfMax', 1, 500, 40, true);
  B.workers = B.workers || {};
  fixNum(B.workers, 'speed', 'workers.speed', 20, 1000, 150);
  fixNum(B.workers, 'capacity', 'workers.capacity', 1, 100, 5, true);
  fixNum(B.workers, 'porterCapacity', 'workers.porterCapacity', 1, 100, 8, true);
  fixNum(B.workers, 'hunterRange', 'workers.hunterRange', 40, 1000, 230);
  B.workers.cyclesPerItem = B.workers.cyclesPerItem || {};
  for (const w of ['fisherman', 'lumberjack', 'farmer', 'miner', 'hunter']) fixNum(B.workers.cyclesPerItem, w, 'workers.cyclesPerItem.' + w, 1, 50, 1, true);
  B.camera = B.camera || {};
  fixNum(B.camera, 'zoom', 'camera.zoom', 0.5, 3, 1.2);
  fixNum(B.camera, 'lerp', 'camera.lerp', 0.01, 1, 0.12);
  B.cash = B.cash || {};
  fixNum(B.cash, 'pileVisualMax', 'cash.pileVisualMax', 1, 500, 48, true);
  fixNum(B.cash, 'collectInterval', 'cash.collectInterval', 0.005, 2, 0.03);
  B.start = B.start || {};
  fixNum(B.start, 'coins', 'start.coins', 0, 1e9, 0, true);
  fixNum(B.start, 'firstCustomers', 'start.firstCustomers', 0, C.maxQueue, 3, true);
  const R = B.resources = B.resources || {};
  R.tree = R.tree || {}; fixNum(R.tree, 'hp', 'resources.tree.hp', 1, 100, 3, true); fixNum(R.tree, 'regrow', 'resources.tree.regrow', 0.1, 600, 7);
  R.rock = R.rock || {}; fixNum(R.rock, 'hp', 'resources.rock.hp', 1, 100, 4, true); fixNum(R.rock, 'regrow', 'resources.rock.regrow', 0.1, 600, 9);
  R.wheat = R.wheat || {}; fixNum(R.wheat, 'growTime', 'resources.wheat.growTime', 0.1, 600, 8); fixNum(R.wheat, 'yield', 'resources.wheat.yield', 1, 100, 2, true);
  R.net = R.net || {}; fixNum(R.net, 'max', 'resources.net.max', 1, 50, 6, true); fixNum(R.net, 'refill', 'resources.net.refill', 0.05, 600, 1.1);
  const A = R.animal = R.animal || {};
  fixNum(A, 'deer', 'resources.animal.deer', 0, 20, 3, true); fixNum(A, 'boar', 'resources.animal.boar', 0, 20, 2, true);
  fixNum(A, 'hp', 'resources.animal.hp', 1, 100, 2, true); fixNum(A, 'meat', 'resources.animal.meat', 1, 50, 2, true);
  fixNum(A, 'respawn', 'resources.animal.respawn', 0.1, 600, 6);
}
