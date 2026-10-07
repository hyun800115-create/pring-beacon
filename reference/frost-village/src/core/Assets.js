// Asset registry (CONTRACT §2). Reads the six manifest fragments, queues their files,
// creates animations and resolves every lookup — falling back to generated placeholder
// textures (one console.warn per missing key) so the game never crashes on missing art.

import { Placeholders } from './Placeholders.js';

export const FRAGMENTS = ['characters', 'props', 'fx', 'ui', 'ground', 'audio'];
const BASE = 'assets/';

// Defaults used when the characters manifest (or a key in it) is missing.
const HUMAN_ANIMS = {
  idle: { frames: 4, fps: 6, repeat: -1 }, walk: { frames: 8, fps: 12, repeat: -1 },
  carry_idle: { frames: 4, fps: 6, repeat: -1 }, carry_walk: { frames: 8, fps: 12, repeat: -1 },
};
const CHAR_DEFAULTS = {
  player: { anims: Object.assign({}, HUMAN_ANIMS, { chop: { frames: 8, fps: 14, repeat: -1, impactFrame: 5 }, mine: { frames: 8, fps: 14, repeat: -1, impactFrame: 5 }, harvest: { frames: 6, fps: 10, repeat: -1, impactFrame: 3 } }) },
  fisherman: { anims: Object.assign({}, HUMAN_ANIMS, { work: { frames: 8, fps: 14, repeat: -1, impactFrame: 4 } }) },
  lumberjack: { anims: Object.assign({}, HUMAN_ANIMS, { work: { frames: 8, fps: 14, repeat: -1, impactFrame: 5 } }) },
  farmer: { anims: Object.assign({}, HUMAN_ANIMS, { work: { frames: 8, fps: 14, repeat: -1, impactFrame: 4 } }) },
  miner: { anims: Object.assign({}, HUMAN_ANIMS, { work: { frames: 8, fps: 14, repeat: -1, impactFrame: 5 } }) },
  hunter: { anims: Object.assign({}, HUMAN_ANIMS, { work: { frames: 8, fps: 14, repeat: -1, impactFrame: 5 } }) },
  villager_a: { anims: { idle: HUMAN_ANIMS.idle, walk: HUMAN_ANIMS.walk, carry_walk: HUMAN_ANIMS.carry_walk, happy: { frames: 6, fps: 10, repeat: -1 } } },
  villager_b: { anims: { idle: HUMAN_ANIMS.idle, walk: HUMAN_ANIMS.walk, carry_walk: HUMAN_ANIMS.carry_walk, happy: { frames: 6, fps: 10, repeat: -1 } } },
  villager_c: { anims: { idle: HUMAN_ANIMS.idle, walk: HUMAN_ANIMS.walk, carry_walk: HUMAN_ANIMS.carry_walk, happy: { frames: 6, fps: 10, repeat: -1 } } },
  deer: { kind: 'animal', shadow: [56, 22], headTop: -56, anims: { idle: { frames: 4, fps: 6, repeat: -1 }, walk: { frames: 8, fps: 12, repeat: -1 } } },
  boar: { kind: 'animal', shadow: [62, 26], headTop: -43, anims: { idle: { frames: 4, fps: 6, repeat: -1 }, walk: { frames: 8, fps: 12, repeat: -1 } } },
};
const COMMON_CHAR = {
  frameSize: [128, 128], anchor: [0.5, 0.8125], dirs: ['S', 'SE', 'E', 'NE', 'N'], mirror: { SW: 'SE', W: 'E', NW: 'NE' },
  frameName: '{anim}_{dir}_{i}', shadow: [46, 18], headTop: -84, kind: 'human',
  carryPoint: { S: [0, -31, false], SE: [12, -34, false], E: [17, -40, false], NE: [12, -46, true], N: [0, -48, true] },
};

export const Assets = {
  m: { atlases: {}, images: {}, spritesheets: {}, characters: {}, sprites: {}, nineSlice: {}, audio: {}, audioGroups: {} },
  fragments: {},
  game: null,
  warned: new Set(),
  cache: new Map(),
  failed: new Set(),
  charCache: {},

  // ---------- loading ----------
  queueManifests(load) {
    for (const f of FRAGMENTS) load.json('manifest_' + f, BASE + f + '/manifest.json');
  },

  mergeManifests(jsonCache) {
    for (const f of FRAGMENTS) {
      const j = jsonCache.exists('manifest_' + f) ? jsonCache.get('manifest_' + f) : null;
      this.fragments[f] = !!j;
      if (!j || typeof j !== 'object') continue;
      const m = this.m;
      for (const a of j.atlases || []) if (a && a.key) m.atlases[a.key] = a;
      for (const a of j.images || []) if (a && a.key) m.images[a.key] = a;
      for (const a of j.spritesheets || []) if (a && a.key) m.spritesheets[a.key] = a;
      Object.assign(m.characters, j.characters || {});
      Object.assign(m.sprites, j.sprites || {});
      Object.assign(m.nineSlice, j.nineSlice || {});
      Object.assign(m.audio, j.audio || {});
      Object.assign(m.audioGroups, j.audioGroups || {});
    }
  },

  queueAssets(load, opts = {}) {
    const m = this.m;
    for (const k in m.atlases) { const a = m.atlases[k]; if (a.png && a.json) load.atlas(k, BASE + a.png, BASE + a.json); }
    for (const k in m.images) { const a = m.images[k]; if (a.png) load.image(k, BASE + a.png); }
    for (const k in m.spritesheets) {
      const a = m.spritesheets[k];
      if (a.png && a.frameWidth) load.spritesheet(k, BASE + a.png, { frameWidth: a.frameWidth, frameHeight: a.frameHeight || a.frameWidth, endFrame: a.frameCount ? a.frameCount - 1 : -1 });
    }
    if (opts.audio !== false) this.queueAudio(load, opts.musicFilter);
  },

  queueAudio(load, filter) {
    const m = this.m;
    for (const k in m.audio) {
      const a = m.audio[k];
      if (filter && !filter(k, a)) continue;
      const files = (a.files || []).map((f) => BASE + f);
      if (files.length) load.audio(k, files);
    }
  },

  /** in-game music & ambience load after the title (in the Game scene) so the title appears sooner */
  isDeferredAudio(key) { return /^(bgm_village|amb_)/.test(key); },

  /**
   * a file failed to load. Audio: Phaser picks the first format the browser can play (ogg) and does
   * not try the next one, so retry once with the remaining URLs (mp3) before giving up.
   */
  onLoadError(file, load) {
    if (!file || !file.key) return;
    const a = file.type === 'audio' && this.m.audio[file.key];
    this.retried = this.retried || new Set();
    if (a && load && !this.retried.has(file.key)) {
      const url = String(file.url || file.src || '');
      const rest = (a.files || []).map((f) => BASE + f).filter((f) => url.indexOf(f) < 0 && !url.endsWith(f));
      if (rest.length) { this.retried.add(file.key); try { load.audio(file.key, rest); return; } catch (e) { /* fall through */ } }
    }
    this.failed.add(file.key);
  },

  /** after all files loaded: create animations */
  finalize(game) {
    this.game = game;
    const tex = game.textures, anims = game.anims;
    // spritesheet anims (key = sheet key)
    for (const k in this.m.spritesheets) {
      const s = this.m.spritesheets[k];
      if (!tex.exists(k) || anims.exists(k)) continue;
      const total = tex.get(k).frameTotal - 1;
      const end = Math.min(total, s.frameCount || total) - 1;
      anims.create({ key: k, frames: anims.generateFrameNumbers(k, { start: 0, end: Math.max(0, end) }), frameRate: s.fps || 24, repeat: s.repeat !== undefined ? s.repeat : 0 });
    }
    // sprite anims (e.g. station work loops)
    for (const k in this.m.sprites) {
      const s = this.m.sprites[k];
      if (!s.anims || !s.atlas || !tex.exists(s.atlas)) continue;
      const t = tex.get(s.atlas);
      for (const an in s.anims) {
        const a = s.anims[an];
        const frames = (a.frames || []).filter((f) => t.has(f)).map((f) => ({ key: s.atlas, frame: f }));
        if (!frames.length) continue;
        const key = 'spr:' + k + ':' + an;
        if (!anims.exists(key)) anims.create({ key, frames, frameRate: a.fps || 8, repeat: a.repeat !== undefined ? a.repeat : -1 });
      }
    }
    // characters
    const keys = new Set(Object.keys(CHAR_DEFAULTS).concat(Object.keys(this.m.characters)));
    for (const c of keys) this.buildCharacter(game, c);
    Placeholders.shadow(tex);
    Placeholders.white(tex);
  },

  charDef(key) {
    if (this.charCache[key]) return this.charCache[key];
    const d = Object.assign({}, COMMON_CHAR, CHAR_DEFAULTS[key] || {}, this.m.characters[key] || {});
    d.anims = Object.assign({}, (CHAR_DEFAULTS[key] || {}).anims || {}, (this.m.characters[key] || {}).anims || {});
    this.charCache[key] = d;
    return d;
  },

  buildCharacter(game, key) {
    const tex = game.textures, anims = game.anims;
    const def = this.charDef(key);
    const atlasOk = def.atlas && tex.exists(def.atlas);
    let phKey = null;
    for (const an in def.anims) {
      const a = def.anims[an];
      for (const dir of def.dirs) {
        const akey = key + ':' + an + ':' + dir;
        if (anims.exists(akey)) continue;
        let frames = null;
        if (atlasOk) {
          const t = tex.get(def.atlas);
          const list = [];
          for (let i = 0; i < (a.frames || 1); i++) {
            const fn = def.frameName.replace('{anim}', an).replace('{dir}', dir).replace('{i}', i);
            if (t.has(fn)) list.push({ key: def.atlas, frame: fn });
          }
          if (list.length) frames = list;
        }
        if (!frames) {
          if (!phKey) { phKey = Placeholders.character(tex, key, def.dirs); this.warn('character atlas ' + key); }
          frames = [{ key: phKey, frame: dir + '_0' }, { key: phKey, frame: dir + '_1' }];
          def._placeholder = true;
        }
        const fps = def._placeholder ? 4 : (a.fps || 10);
        anims.create({ key: akey, frames, frameRate: fps, repeat: a.repeat !== undefined ? a.repeat : -1 });
      }
    }
  },

  /** anim key for character anim with fallback to a sensible alternative */
  charAnim(key, anim, baseDir) {
    const anims = this.game.anims;
    let k = key + ':' + anim + ':' + baseDir;
    if (anims.exists(k)) return k;
    const alt = { carry_idle: 'idle', carry_walk: 'walk', happy: 'idle', work: 'idle', chop: 'idle', mine: 'idle', harvest: 'idle' }[anim];
    if (alt) { k = key + ':' + alt + ':' + baseDir; if (anims.exists(k)) return k; }
    return key + ':idle:S';
  },

  // ---------- lookups ----------
  warn(what) {
    if (this.warned.has(what)) return;
    this.warned.add(what);
    console.warn('[FrostVillage] missing asset → placeholder:', what);
  },

  /** resolve a static picture: { tex, frame, anchor, def, ph } */
  sprite(key) {
    let r = this.cache.get(key);
    if (r) return r;
    const tex = this.game.textures;
    const def = this.m.sprites[key];
    if (def) {
      if (def.atlas && tex.exists(def.atlas) && tex.get(def.atlas).has(def.frame)) r = { tex: def.atlas, frame: def.frame, anchor: def.anchor || [0.5, 0.5], def };
      else if (def.image && tex.exists(def.image)) r = { tex: def.image, frame: undefined, anchor: def.anchor || [0.5, 0.5], def };
    }
    if (!r && tex.exists(key) && !this.failed.has(key)) {
      r = { tex: key, frame: undefined, anchor: (def && def.anchor) || (this.m.images[key] && this.m.images[key].anchor) || [0.5, 0.5], def: def || this.m.images[key] || {} };
    }
    if (!r) {
      this.warn(key);
      const ph = Placeholders.sprite(tex, key, def);
      r = { tex: ph.tex, frame: undefined, anchor: ph.anchor, def: def || {}, ph: true };
    }
    this.cache.set(key, r);
    return r;
  },

  has(key) {
    const tex = this.game.textures;
    const def = this.m.sprites[key];
    if (def && def.atlas) return tex.exists(def.atlas) && tex.get(def.atlas).has(def.frame);
    if (def && def.image) return tex.exists(def.image);
    return tex.exists(key) && !this.failed.has(key);
  },

  def(key) { return this.m.sprites[key] || {}; },

  /** apply a sprite key to an existing Image/Sprite */
  apply(img, key) {
    const r = this.sprite(key);
    img.setTexture(r.tex, r.frame);
    img.setOrigin(r.anchor[0], r.anchor[1]);
    return img;
  },

  image(scene, x, y, key) {
    const r = this.sprite(key);
    const img = scene.add.image(x, y, r.tex, r.frame);
    img.setOrigin(r.anchor[0], r.anchor[1]);
    return img;
  },

  /** source image/canvas for canvas-2D baking (patterns, decals) */
  source(key) {
    const r = this.sprite(key);
    const t = this.game.textures.get(r.tex);
    const fr = r.frame !== undefined ? t.get(r.frame) : t.get();
    return { img: t.getSourceImage(), frame: fr, anchor: r.anchor, ph: !!r.ph, def: r.def };
  },

  sheet(key) { return this.game.anims.exists(key) ? key : null; },
  sheetDef(key) { return this.m.spritesheets[key] || null; },

  spriteAnim(key, anim) { const k = 'spr:' + key + ':' + anim; return this.game.anims.exists(k) ? k : null; },

  nine(key) {
    const n = this.m.nineSlice[key];
    if (n) {
      const s = this.sprite(n.image || key);
      if (!s.ph) return { tex: s.tex, frame: s.frame, l: n.left, r: n.right, t: n.top, b: n.bottom };
    }
    const s = this.sprite(key);
    if (s.ph) return { tex: s.tex, frame: undefined, l: 30, r: 30, t: 30, b: 34 };
    const fr = this.game.textures.get(s.tex).get(s.frame);
    const m = Math.floor(Math.min(fr.width, fr.height) / 3);
    return { tex: s.tex, frame: s.frame, l: m, r: m, t: m, b: m };
  },

  audioDef(key) { return this.m.audio[key] || null; },
  audioGroup(key) { return this.m.audioGroups[key] || null; },
};
