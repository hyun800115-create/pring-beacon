// Save / settings persistence. Every localStorage access is wrapped in try/catch
// (private mode, sandboxed iframes and full quotas must never crash the game).

export const SAVE_KEY = 'frostVillage.save.v1';
export const SETTINGS_KEY = 'frostVillage.settings.v1';

function getStore() {
  try { return window.localStorage || null; } catch (e) { return null; }
}

export function readJSON(key) {
  try {
    const st = getStore();
    if (!st) return null;
    const raw = st.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) { return null; }
}

export function writeJSON(key, obj) {
  try {
    const st = getStore();
    if (!st) return false;
    st.setItem(key, JSON.stringify(obj));
    return true;
  } catch (e) { return false; }
}

export function removeKey(key) {
  try { const st = getStore(); if (st) st.removeItem(key); } catch (e) { /* ignore */ }
}

export const SAVE_VERSION = 1;
export const BACKUP_KEY = 'frostVillage.save.backup';
export const BAD_KEY = 'frostVillage.save.v1.bad';

const ITEMS = ['item_fish_raw', 'item_fish_cooked', 'item_log', 'item_plank', 'item_wheat', 'item_bread', 'item_ore', 'item_ingot', 'item_meat_raw', 'item_meat_cooked'];
const FOODS = ['item_fish_cooked', 'item_bread', 'item_meat_cooked'];
const GOODS = ['item_plank', 'item_ingot'];

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
/** finite number (numeric strings accepted) or `d` */
const num = (v, d) => {
  const n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN);
  return Number.isFinite(n) ? n : d;
};
const count = (v, max = 1e9) => Math.max(0, Math.min(max, Math.floor(num(v, 0))));
const flags = (v) => { const o = {}; if (isObj(v)) for (const k in v) if (v[k] === true) o[k] = true; return o; };
const counts = (v, keys) => { const o = {}; if (isObj(v)) for (const k of keys || Object.keys(v)) if (k in v) o[k] = count(v[k], 1e7); return o; };

// Migrations from older save versions: MIGRATE[v] turns a version-v save into version v+1.
const MIGRATE = {
  // 0: (s) => ({ ...s, v: 1 }),
};

/**
 * Validate a loaded save so a corrupted or hand-edited value can never brick the game:
 * every number is finite and in range, lists are lists, unknown item types are dropped.
 */
export function sanitizeSave(raw) {
  if (!isObj(raw)) return null;
  const s = {};
  s.v = SAVE_VERSION;
  s.coins = count(raw.coins, 1e12);
  const pr = isObj(raw.progress) ? raw.progress : {};
  const up = isObj(pr.up) ? pr.up : {};
  s.progress = {
    done: flags(pr.done),
    paid: counts(pr.paid),
    up: { capacity: count(up.capacity, 99), speed: count(up.speed, 99) },
    celebrated: pr.celebrated === true,
    hints: flags(pr.hints),
    seen: flags(pr.seen),
  };
  s.stations = {};
  if (isObj(raw.stations)) for (const id in raw.stations) { const st = raw.stations[id]; if (isObj(st)) s.stations[id] = { i: count(st.i, 1000), o: count(st.o, 1000) }; }
  const shop = (o, types) => (isObj(o) ? { stock: counts(o.stock, types), cash: count(o.cash, 1e9) } : null);
  s.market = shop(raw.market, FOODS);
  s.trade = shop(raw.trade, GOODS);
  const p = isObj(raw.player) ? raw.player : {};
  const x = num(p.x, NaN), y = num(p.y, NaN);
  s.player = {
    x: Number.isFinite(x) ? x : undefined,
    y: Number.isFinite(y) ? y : undefined,
    stack: Array.isArray(p.stack) ? p.stack.filter((k) => typeof k === 'string' && ITEMS.indexOf(k) >= 0).slice(0, 200) : [],
  };
  return s;
}

export const Save = {
  /** the saved game (sanitized), or null for a fresh start. Other versions are migrated or backed up first. */
  load() {
    let s = readJSON(SAVE_KEY);
    if (!s || typeof s !== 'object') return null;
    let v = typeof s.v === 'number' ? s.v : -1;
    while (v !== SAVE_VERSION && MIGRATE[v]) { try { s = MIGRATE[v](s); v = s.v; } catch (e) { break; } }
    if (v !== SAVE_VERSION) {
      // unknown / future version: keep a copy (once) before the next autosave overwrites it
      try { const st = getStore(); if (st && !st.getItem(BACKUP_KEY)) st.setItem(BACKUP_KEY, st.getItem(SAVE_KEY)); } catch (e) { /* ignore */ }
      return null;
    }
    return sanitizeSave(s);
  },
  write(state) {
    // "Start over" on the crash card: the page is reloading and the crashed game's autosave
    // (pagehide / visibilitychange) must not put the old progress back
    if (typeof window !== 'undefined' && window.__FV_NO_SAVE) return false;
    const ok = writeJSON(SAVE_KEY, Object.assign({ v: SAVE_VERSION, t: Date.now() }, state));
    this.lastWriteOk = ok;
    return ok;
  },
  lastWriteOk: true,
  clear() { removeKey(SAVE_KEY); },
  /** move a save that crashed the game aside (kept for debugging) */
  quarantine() {
    try { const st = getStore(); if (!st) return; const raw = st.getItem(SAVE_KEY); if (raw) st.setItem(BAD_KEY, raw); st.removeItem(SAVE_KEY); } catch (e) { /* ignore */ }
  },
};

export const Settings = {
  data: { sound: true, music: true, lang: null },
  load() {
    const s = readJSON(SETTINGS_KEY);
    if (s && typeof s === 'object' && !Array.isArray(s)) {
      this.data.sound = s.sound !== false;
      this.data.music = s.music !== false;
      this.data.lang = s.lang === 'ko' || s.lang === 'en' ? s.lang : null;
    }
    return this.data;
  },
  save() { writeJSON(SETTINGS_KEY, this.data); },
};
