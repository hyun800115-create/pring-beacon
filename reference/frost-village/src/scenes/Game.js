// The village: builds the world from data/world.js, runs every entity and system,
// saves/loads, and installs the window.__FV test hooks.

import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { Input } from '../core/Input.js';
import { Save } from '../core/Save.js';
import { isoPt, isoRect, gdist, gdist2, inIsoRect } from '../core/Iso.js';
import { BALANCE } from '../data/balance.js';
import { WORLD } from '../data/world.js';
import { FONT, t } from '../data/strings.js';
import { DEPTH, DepthSort } from '../systems/DepthSort.js';
import { Collision, shoreY } from '../systems/Collision.js';
import { Effects } from '../systems/Effects.js';
import { Ground } from '../systems/Ground.js';
import { Economy } from '../systems/Economy.js';
import { Progression, STEPS } from '../systems/Progression.js';
import { Tutorial, PRODUCT_ZONE } from '../systems/Tutorial.js';
import { Player } from '../entities/Player.js';
import { Worker } from '../entities/Worker.js';
import { Animal } from '../entities/Animal.js';
import { Station } from '../entities/Station.js';
import { Market, TradePost, FOODS, GOODS } from '../entities/Seller.js';
import { Tree, Rock, Wheat, Net } from '../entities/ResourceNode.js';
import { TrashPad } from '../entities/TrashPad.js';
import { rng } from '../core/Placeholders.js';
import { View } from '../core/View.js';

// obstacle radius (ground space px) for static decor
const DECOR_R = {
  barrel: 20, crate: 26, lamp_post: 12, flag_pole: 14, bench: 40, firewood_pile: 36, hay_bale: 30, signpost: 12,
  campfire: 30, bush_snow: 24, ice_chunk: 0, snow_pile_a: 0, snow_pile_b: 0, tent_a: 80, chief_lodge: 170,
  worker_hut: 98, dock_pier: 0, boat_small: 0, mine_entrance: 120, tree_stump: 18, upgrade_bench: 70,
};

class UIProxy {
  constructor(game) { this.game = game; }
  get s() { const s = this.game.scene.getScene('UI'); return s && s.ready && s.sys.isActive() ? s : null; }
  setCoins(v, ms) { const s = this.s; if (s) s.setCoins(v, ms); }
  coinFly(wx, wy, n) { const s = this.s; if (s) s.coinFly(wx, wy, n); }
  toast(msg) { const s = this.s; if (s) s.toast(msg); }
  banner(msg, sub) { const s = this.s; if (s) s.banner(msg, sub); }
  setObjective(key, tg, text) { const s = this.s; if (s) s.setObjective(key, tg, text); }
  celebrate() { const s = this.s; if (s) s.celebrate(); }
}

export class Game extends Phaser.Scene {
  constructor() { super('Game'); }

  init(data) { this.fresh = !!(data && data.fresh); }

  create() {
    this._broken = false;
    try {
      this.build();
    } catch (e) {
      this._broken = true;
      // a save that cannot be restored must never brick the game: keep a copy aside and start fresh
      console.error('[FrostVillage] could not restore the saved game, starting fresh:', e);
      if (this.fresh) throw e;
      Save.quarantine();
      this.time.delayedCall(0, () => this.scene.restart({ fresh: true }));
    }
  }

  build() {
    const W = WORLD.width, H = WORLD.height;
    this.W = W; this.H = H;
    this.font = FONT;
    this.ui = new UIProxy(this.game);
    this.saved = this.fresh ? null : Save.load();
    const sv = this.saved || {};

    this.collision = new Collision(W, H);
    this.effects = new Effects(this);
    this.depthSort = new DepthSort();
    this.agents = [];          // moving characters (workers, customers) for separation
    this.workers = [];
    this.zones = {};
    this.zoneObjs = {};
    this.statics = [];

    this.ground = new Ground(this);
    this.buildZones();
    this.buildFences();
    this.buildDecor();
    this.buildTrees();
    this.buildResources();
    this.buildStations();
    this.buildSellers();
    this.buildHuts();

    const ps = sv.player || {};
    const okPos = Number.isFinite(ps.x) && Number.isFinite(ps.y) && ps.x >= 40 && ps.x <= W - 40 && ps.y >= 0 && ps.y <= H - 40;
    const sp = { x: okPos ? ps.x : WORLD.player.x, y: okPos ? ps.y : WORLD.player.y };
    if (okPos) this.collision.resolve(sp, 16);
    const px = sp.x, py = sp.y;
    this.player = new Player(this, px, py);
    this.economy = new Economy(this, sv.coins !== undefined ? sv.coins : BALANCE.start.coins);
    this.progress = new Progression(this, sv.progress);
    this.tutorial = new Tutorial(this);

    // lock zones that are not open yet
    for (const id in this.zones) if (!this.zones[id].unlocked) this.setZoneEnabled(id, false);
    this.progress.init();
    this.restore(sv);

    // ambient snowfall around the camera
    this.snow = this.effects.emitter('snowfall');
    this.snow.setDepth(DEPTH.FX - 10);
    this.snowT = 0;

    // camera
    const cam = this.cameras.main;
    cam.setBounds(0, 0, W, H);
    this.zoomBase = BALANCE.camera.zoom;
    cam.setZoom(this.zoomBase * View.k);
    // the canvas resolution (View.k) can change on rotation / resize
    const onResize = () => cam.setZoom(this.zoomBase * View.k);
    this.scale.on('resize', onResize);
    this.events.once('shutdown', () => this.scale.off('resize', onResize));
    cam.setBackgroundColor('#dbe6f2');
    const tv = this.tutorial.inTutorial && WORLD.tutorialView && gdist(px, py, WORLD.tutorialView[0], WORLD.tutorialView[1]) < 500 ? WORLD.tutorialView : null;
    this.camTarget = tv ? { x: tv[0], y: tv[1] } : { x: px, y: py - 20 };
    this.camFocus = null;     // { x, y, until } temporary pan target
    cam.startFollow(this.camTarget, false, 1, 1);
    cam.centerOn(this.camTarget.x, this.camTarget.y);

    this.padT = 0;
    this.playerOnPad = false;
    this.saveT = 0;
    this.ambT = 0;

    Input.attachKeyboard(this);
    if (window.__FV_DEBUG) {
      this.input.keyboard.on('keydown-M', () => this.economy.add(1000));
    }

    this.onVis = () => { if (document.visibilityState === 'hidden') { this.save(true); Input.release(); } };
    this.onHide = () => this.save(true);
    document.addEventListener('visibilitychange', this.onVis);
    window.addEventListener('pagehide', this.onHide);
    this.events.once('shutdown', () => { document.removeEventListener('visibilitychange', this.onVis); window.removeEventListener('pagehide', this.onHide); });

    this.installHooks();
    this.scene.launch('UI');
    Audio.playMusic('bgm_village');
    Audio.setAmbience('amb_wind', 0.5);
    Audio.setAmbience('amb_sea', 0.3);
    Audio.setAmbience('amb_fire', 0);
    this.loadDeferredAudio();
  }

  /** village music + ambience were left out of the preload (faster title); fetch them now */
  loadDeferredAudio() {
    const want = Object.keys(Assets.m.audio).filter((k) => Assets.isDeferredAudio(k) && !this.cache.audio.exists(k) && !Assets.failed.has(k));
    if (!want.length) return;
    this.load.on('loaderror', (f) => Assets.onLoadError(f, this.load));
    Assets.queueAudio(this.load, (k) => want.indexOf(k) >= 0);
    this.load.once('complete', () => { Audio.trimLoops(); Audio.applyMusic(); });
    this.load.start();
  }

  // ------------------------------------------------------------------ building
  buildZones() {
    for (const id in WORLD.zones) {
      const z = WORLD.zones[id];
      const floor = this.ground.zoneFloor(id, z);
      const unlocked = !z.unlock;
      this.zones[id] = { id, cfg: z, floor, unlocked, outline: null };
      this.zoneObjs[id] = [];
      if (!unlocked) {
        floor.setAlpha(0);
        this.zones[id].outline = this.makeLockedOutline(id, z);
      }
    }
  }

  makeLockedOutline(id, z) {
    const g = this.add.graphics().setDepth(DEPTH.OUTLINE);
    const pts = isoRect(z.center[0], z.center[1], z.size[0], z.size[1]);
    // faint frosted fill
    g.fillStyle(0xc9d6e8, 0.28);
    g.beginPath(); g.moveTo(pts[0].x, pts[0].y); for (let i = 1; i < 4; i++) g.lineTo(pts[i].x, pts[i].y); g.closePath(); g.fillPath();
    // dashed border
    g.lineStyle(5, 0xffffff, 0.9);
    for (let i = 0; i < 4; i++) {
      const a = pts[i], b = pts[(i + 1) % 4];
      const len = Math.hypot(b.x - a.x, b.y - a.y), n = Math.floor(len / 26);
      for (let k = 0; k < n; k += 2) {
        const t0 = k / n, t1 = Math.min(1, (k + 1) / n);
        g.lineBetween(a.x + (b.x - a.x) * t0, a.y + (b.y - a.y) * t0, a.x + (b.x - a.x) * t1, a.y + (b.y - a.y) * t1);
      }
    }
    // a frosted preview of what is inside (station + a few resources), so the zone is not an empty void
    const ghosts = [];
    const ghost = (key, x, y, sc) => {
      if (!Assets.has(key)) return;
      const im = Assets.image(this, x, y, key).setAlpha(0.2).setTint(0x9fb3cc).setDepth(DEPTH.OUTLINE + 1 + y * 0.01);
      if (sc) im.setScale(sc);
      ghosts.push(im);
    };
    const [zx, zy] = z.center;
    for (const st of WORLD.stations) if (st.zone === id) ghost(st.sprite, st.x, st.y);
    if (id === 'forest') for (const [mx, my, k] of [[-1.6, 1.0, 'tree_pine_a'], [1.4, -1.8, 'tree_pine_snow'], [-2.6, -1.6, 'tree_pine_b'], [0.2, -3.0, 'tree_pine_a']]) { const p = isoPt(zx, zy, mx, my); ghost(k, p.x, p.y, 0.85); }
    if (id === 'farm') { const w = WORLD.wheat; for (const [i, j] of [[0, 0], [1, 1], [2, 0], [0, 2]]) { const p = isoPt(w.origin[0], w.origin[1], (i - 1) * w.step, (j - 1) * w.step); ghost('crop_wheat_3', p.x, p.y); } }
    if (id === 'mine') for (const [x, y, k] of WORLD.rocks.slice(0, 4)) ghost(k, x, y);
    if (id === 'hunt') for (const [mx, my, k] of [[2.6, -2.8, 'hay_bale'], [-2.8, -2.6, 'bush_snow'], [3.2, 0.4, 'bush_snow']]) { const p = isoPt(zx, zy, mx, my); ghost(k, p.x, p.y); }
    const lock = Assets.image(this, zx, zy - 14, 'ui_icon_lock').setDepth(DEPTH.PAD_TEXT);
    const lf = lock.frame; lock.setScale(60 / Math.max(lf.realWidth, 1)).setOrigin(0.5, 0.5).setAlpha(0.95);
    const txt = this.add.text(zx, zy + 34, t(z.name), { fontFamily: FONT, fontSize: '34px', fontStyle: '900', color: '#ffffff', stroke: '#4a5a72', strokeThickness: 8, resolution: 2 }).setOrigin(0.5, 0.5).setDepth(DEPTH.PAD_TEXT).setAlpha(0.97);
    return { g, lock, txt, ghosts };
  }

  addToZone(zone, obj) { if (zone && this.zoneObjs[zone]) this.zoneObjs[zone].push(obj); }

  staticImage(key, x, y, opts = {}) {
    const img = Assets.image(this, x, y, key).setDepth(y + (opts.depthOff || 0));
    if (opts.flip) img.setFlipX(true);
    if (opts.scale) { img.setScale(opts.scale); img.__bs = opts.scale; }
    const r = opts.r !== undefined ? opts.r : DECOR_R[key];
    let ob = null;
    if (r) ob = this.collision.add(x, y, r * (opts.scale || 1), key);
    img.__ob = ob;
    if (opts.zone) this.addToZone(opts.zone, img);
    this.statics.push(img);
    if (/^tree_pine|lodge|hut|tent|mine_entrance|market|trade_post|station_/.test(key)) this.addOccluder(img);
    return img;
  }

  /** tall things fade out when the player walks behind them */
  addOccluder(img) {
    const h = img.displayHeight * img.originY;
    const w = img.displayWidth;
    (this.occluders || (this.occluders = [])).push({ img, x: img.x + (0.5 - img.originX) * w * 0.4, y: img.y, hw: w * 0.4, top: h * 0.95, a: 1 });
  }

  /** opaque pixel of occluder `img` at world point (x, y)? (null when unknown) */
  pixelSolid(img, x, y) {
    try {
      const fr = img.frame, sx = img.scaleX || 1, sy = img.scaleY || 1;
      const lx = img.displayOriginX + ((img.flipX ? -1 : 1) * (x - img.x)) / sx;
      const ly = img.displayOriginY + (y - img.y) / sy;
      if (lx < 0 || ly < 0 || lx >= fr.realWidth || ly >= fr.realHeight) return false;
      const a = this.textures.getPixelAlpha(Math.floor(lx), Math.floor(ly), img.texture.key, fr.name);
      return a === null ? false : a > 110;
    } catch (e) { return null; }
  }

  updateOccluders(dt) {
    const p = this.player, list = this.occluders;
    if (!list) return;
    const px = p.x, py = p.y - 30;
    const k = Math.min(1, dt * 10);
    for (let i = 0; i < list.length; i++) {
      const o = list[i];
      let behind = py < o.y - 6 && py > o.y - o.top && Math.abs(px - o.x) < o.hw && o.img.visible;
      if (behind) {
        // the box says maybe: only fade when the art really covers the chief's body or head
        o.chkT = (o.chkT || 0) - dt;
        if (o.chkT <= 0 || o.lastPx === undefined || Math.abs(o.lastPx - px) + Math.abs(o.lastPy - p.y) > 6) {
          o.chkT = 0.12; o.lastPx = px; o.lastPy = p.y;
          const a = this.pixelSolid(o.img, px, p.y - 34), b = this.pixelSolid(o.img, px, p.y - 66);
          o.solid = a === null || b === null ? true : (a || b);
        }
        behind = o.solid;
      }
      const target = behind ? 0.32 : 1;
      if (o.a === target) continue;
      o.a += (target - o.a) * k;
      if (Math.abs(o.a - target) < 0.02) o.a = target;
      o.img.setAlpha(o.a);
    }
  }

  buildFences() {
    // posts shared by two edges / zones are placed once (a doubled post doubles its baked shadow)
    const posts = new Set();
    const post = (x, y, zone) => {
      const k = Math.round(x / 6) + ',' + Math.round(y / 6);
      if (posts.has(k)) return;
      posts.add(k);
      this.staticImage('fence_post', x, y, { zone, r: 16 });
    };
    for (const f of WORLD.fences) {
      const z = WORLD.zones[f.zone];
      const [cx, cy] = z.center;
      const hw = z.size[0] / 2, hh = z.size[1] / 2;
      const gated = z.unlock ? f.zone : null;
      // edge definitions: start point (local m), direction axis, length
      const E = {
        tl: { sx: -hw, sy: -hh, ax: 'y', len: z.size[1] },   // left -> top   (along +Y)
        tr: { sx: -hw, sy: hh, ax: 'x', len: z.size[0] },    // top -> right  (along +X)
        bl: { sx: -hw, sy: -hh, ax: 'x', len: z.size[0] },   // left -> bottom(along +X)
        br: { sx: hw, sy: -hh, ax: 'y', len: z.size[1] },    // bottom -> right (along +Y)
      };
      for (const e in f.edges) {
        const d = E[e], gaps = f.edges[e];
        const n = Math.floor(d.len);
        const off = (d.len - n) / 2;
        let lastIn = false;
        for (let i = 0; i < n; i++) {
          const m = off + i + 0.5;
          const inGap = gaps.some((g) => m >= g[0] && m <= g[1]);
          const mx = d.sx + (d.ax === 'x' ? m : 0), my = d.sy + (d.ax === 'y' ? m : 0);
          const p = isoPt(cx, cy, mx, my);
          if (inGap) {
            if (lastIn) { // cap the run with a post
              const q = isoPt(cx, cy, d.sx + (d.ax === 'x' ? m - 0.5 : 0), d.sy + (d.ax === 'y' ? m - 0.5 : 0));
              post(q.x, q.y, gated);
            }
            lastIn = false;
            continue;
          }
          if (!lastIn && i > 0) {
            const q = isoPt(cx, cy, d.sx + (d.ax === 'x' ? m - 0.5 : 0), d.sy + (d.ax === 'y' ? m - 0.5 : 0));
            post(q.x, q.y, gated);
          }
          this.staticImage(d.ax === 'x' ? 'fence_log_x' : 'fence_log_y', p.x, p.y, { zone: gated, r: 22 });
          lastIn = true;
        }
        // end posts
        const s = isoPt(cx, cy, d.sx, d.sy);
        const ePt = isoPt(cx, cy, d.sx + (d.ax === 'x' ? d.len : 0), d.sy + (d.ax === 'y' ? d.len : 0));
        if (!gaps.some((g) => g[0] <= 0.6)) post(s.x, s.y, gated);
        if (!gaps.some((g) => g[1] >= d.len - 0.6)) post(ePt.x, ePt.y, gated);
      }
    }
  }

  buildDecor() {
    for (const d of WORLD.decor) {
      const [key, x, y, o] = d;
      const img = this.staticImage(key, x, y, o || {});
      if (key === 'campfire') {
        const fire = this.effects.loop('fx_fire', x, y - 14, 58, y + 1);
        if (fire) { if (o && o.zone) this.addToZone(o.zone, fire); }
        else this.fireSpots = (this.fireSpots || []).concat([{ x, y, zone: o && o.zone }]);
        this.campfires = (this.campfires || []).concat([{ x, y }]);
      }
      if (key === 'lamp_post') this.lamps = (this.lamps || []).concat([img]);
      // things floating in the sea bob gently
      if ((key === 'boat_small' || key === 'ice_chunk') && y < shoreY(x) + 10) {
        this.tweens.add({ targets: img, y: y + 4, angle: { from: -1.5, to: 1.5 }, duration: 1600 + (x % 7) * 120, yoyo: true, repeat: -1, ease: 'Sine.easeInOut', delay: (x % 5) * 200 });
      }
    }
  }

  /** true if a decorative tree at (x, y) would sit inside a zone, on a path or on gameplay objects */
  blockedForDecor(x, y) {
    for (const id in WORLD.zones) {
      const z = WORLD.zones[id];
      if (inIsoRect(x, y, z.center[0], z.center[1], z.size[0] + 1.6, z.size[1] + 1.6)) return true;
      // the canopy (~1.5-2.5 m above the trunk on screen) must not cover the zone either
      if (inIsoRect(x, y - 90, z.center[0], z.center[1], z.size[0] + 0.6, z.size[1] + 0.6)) return true;
      if (inIsoRect(x, y - 170, z.center[0], z.center[1], z.size[0], z.size[1])) return true;
    }
    for (const pts of WORLD.paths) {
      for (let i = 0; i < pts.length - 1; i++) {
        const [ax, ay] = pts[i], [bx, by] = pts[i + 1];
        const vx = bx - ax, vy = by - ay, l2 = vx * vx + vy * vy;
        const tt = Math.max(0, Math.min(1, ((x - ax) * vx + (y - ay) * vy) / l2));
        if (Math.hypot(ax + vx * tt - x, ay + vy * tt - y) < 75) return true;
      }
    }
    const spots = [[WORLD.net.x, WORLD.net.y, 170], [WORLD.player.x, WORLD.player.y, 120]];
    for (const id in WORLD.pads) { const p = WORLD.pads[id]; spots.push([p.x, p.y, 120]); if (p.hut) spots.push([p.hut[0], p.hut[1], 150]); }
    for (const d of WORLD.decor) if (/lodge|tent|pier|flag|campfire/.test(d[0])) spots.push([d[1], d[2], d[0] === 'chief_lodge' ? 230 : 120]);
    for (const [sx, sy, r] of spots) if (gdist(x, y, sx, sy) < r) return true;
    return false;
  }

  buildTrees() {
    // decorative border forest
    const r = rng(1234);
    const kinds = ['tree_pine_a', 'tree_pine_b', 'tree_pine_snow', 'tree_pine_snow'];
    for (const [x0, y0, x1, y1, step] of WORLD.borderTrees) {
      let row = 0;
      for (let y = y0; y <= y1; y += step * 0.55, row++) {
        for (let x = x0; x <= x1; x += step) {
          const x2 = x + (r() - 0.5) * step * 0.6 + ((row % 2) * step) / 2;
          const y2 = y + (r() - 0.5) * step * 0.3;
          const k = kinds[Math.floor(r() * kinds.length)], fl = r() < 0.5, sc = 0.9 + r() * 0.25;
          if (y2 < shoreY(x2) + 40 || this.blockedForDecor(x2, y2)) continue;
          this.staticImage(k, x2, y2, { r: 24, flip: fl, scale: sc });
        }
      }
    }
    for (const [x, y, k] of WORLD.extraTrees) if (!this.blockedForDecor(x, y)) this.staticImage(k, x, y, { r: 24, flip: x % 2 === 0 });
  }

  buildResources() {
    // net (start zone)
    const n = WORLD.net;
    this.net = new Net(this, n.x, n.y, n);
    // forest trees on a jittered iso grid
    this.trees = [];
    const tz = WORLD.zones[WORLD.trees.zone];
    const cfg = WORLD.trees;
    const r = rng(77);
    const kinds = ['tree_pine_a', 'tree_pine_snow', 'tree_pine_b'];
    const hw = tz.size[0] / 2 - cfg.margin, hh = tz.size[1] / 2 - cfg.margin;
    for (let mx = -hw; mx <= hw + 0.01; mx += cfg.grid) {
      for (let my = -hh; my <= hh + 0.01; my += cfg.grid) {
        const p = isoPt(tz.center[0], tz.center[1], mx + (r() - 0.5) * cfg.jitter, my + (r() - 0.5) * cfg.jitter);
        if (cfg.avoid.some(([ax, ay, ar]) => gdist(p.x, p.y, ax, ay) < ar)) continue;
        if (r() < 0.12) continue;
        // the zone's far-left corner runs into the border pines: a chief chopping there would vanish
        if (mx + my < (cfg.cornerCut !== undefined ? cfg.cornerCut : -1e9)) continue;
        const tr = new Tree(this, p.x, p.y, kinds[Math.floor(r() * kinds.length)]);
        if (cfg.scale) { tr.img.setScale(cfg.scale); tr.img.__bs = cfg.scale; tr.scale = cfg.scale; }
        this.addOccluder(tr.img);
        this.trees.push(tr);
        this.addToZone(WORLD.trees.zone, tr);
      }
    }
    // ore rocks
    this.rocks = [];
    for (const [x, y, k] of WORLD.rocks) { const rk = new Rock(this, x, y, k); this.rocks.push(rk); this.addToZone('mine', rk); }
    // wheat plots
    this.wheat = [];
    const w = WORLD.wheat;
    for (let i = 0; i < w.rows; i++) {
      for (let j = 0; j < w.cols; j++) {
        const p = isoPt(w.origin[0], w.origin[1], (i - (w.rows - 1) / 2) * w.step, (j - (w.cols - 1) / 2) * w.step);
        const wh = new Wheat(this, p.x, p.y);
        this.wheat.push(wh);
        this.addToZone(w.zone, wh);
      }
    }
    // animals
    this.animals = [];
    const hz = WORLD.zones[WORLD.hunt.zone];
    const A = BALANCE.resources.animal;
    for (let i = 0; i < A.deer + A.boar; i++) {
      const a = new Animal(this, i < A.deer ? 'deer' : 'boar', hz);
      this.animals.push(a);
      this.addToZone(WORLD.hunt.zone, a);
    }
  }

  buildStations() {
    this.stations = {};
    this.stationList = [];
    this.stationByInput = {};
    for (const c of WORLD.stations) {
      const s = new Station(this, c);
      this.stations[c.id] = s;
      this.stationByInput[c.input] = s;
      this.stationList.push(s);
      if (WORLD.zones[c.zone].unlock) this.addToZone(c.zone, s);
    }
  }

  buildSellers() {
    this.market = new Market(this, WORLD.market);
    this.trade = new TradePost(this, WORLD.trade);
    this.addToZone(WORLD.trade.zone, this.trade);
    this.trash = new TrashPad(this, WORLD.trash);
    const b = WORLD.bench;
    this.bench = this.staticImage(b.sprite, b.x, b.y, {});
    this.bench.setVisible(false);
    if (this.bench.__ob) this.bench.__ob.active = false;
  }

  buildHuts() {
    for (const id in WORLD.pads) {
      const p = WORLD.pads[id];
      if (!p.hut) continue;
      const zone = { fisherman: null, lumberjack: 'forest', farmer: 'farm', miner: 'mine', hunter: 'hunt' }[p.worker];
      this.staticImage('worker_hut', p.hut[0], p.hut[1], { zone, scale: 0.8, r: 80 });
    }
  }

  // ------------------------------------------------------------------ zones
  setZoneEnabled(id, v) {
    for (const o of this.zoneObjs[id]) {
      if (o.setEnabled) o.setEnabled(v);
      else { o.setVisible(v); if (o.__ob) o.__ob.active = v; }
    }
  }

  revealZone(id, instant) {
    const z = this.zones[id];
    if (!z || z.unlocked) return;
    z.unlocked = true;
    this.setZoneEnabled(id, true);
    if (z.outline) {
      const o = z.outline; z.outline = null;
      const all = [o.g, o.lock, o.txt].concat(o.ghosts || []);
      if (instant) for (const x of all) x.destroy();
      else this.tweens.add({ targets: all, alpha: 0, duration: 400, onComplete: () => { for (const x of all) x.destroy(); } });
    }
    if (instant) { z.floor.setAlpha(1); return; }
    // cinematic reveal: pan the camera, fade the floor in, pop every object in
    const [cx, cy] = z.cfg.center;
    this.focusCamera(cx, cy, BALANCE.camera.revealPanMs + BALANCE.camera.revealHoldMs + 600);
    z.floor.setAlpha(0);
    this.tweens.add({ targets: z.floor, alpha: 1, duration: 700, delay: 350 });
    Audio.play('sfx_build');
    const objs = [];
    for (const o of this.zoneObjs[id]) {
      if (o.revealObjects) objs.push(...o.revealObjects());
      else if (o.img) objs.push(o.img);
      else if (o.sprite) objs.push(o.sprite);
      else objs.push(o);
    }
    objs.sort((a, b) => gdist2(a.x, a.y, cx, cy) - gdist2(b.x, b.y, cx, cy));
    objs.forEach((o, i) => {
      const sx = o.scaleX, sy = o.scaleY;
      o.setScale(0.01);
      this.tweens.add({ targets: o, scaleX: sx, scaleY: sy, duration: 420, delay: 450 + i * 22, ease: 'Back.easeOut' });
      if (i % 4 === 0) this.time.delayedCall(450 + i * 22, () => this.effects.burst('snowhit', o.x, o.y - 10, 4));
    });
    this.time.delayedCall(500, () => { this.effects.sheet('fx_poof', cx, cy, { size: 360 }); this.effects.shake(220, 0.006); });
  }

  focusCamera(x, y, ms) { this.camFocus = { x, y, until: this.time.now + ms }; }

  showBench(instant) {
    const b = this.bench;
    b.setVisible(true);
    if (b.__ob) b.__ob.active = true;
    if (!instant) {
      b.setScale(0.01);
      this.tweens.add({ targets: b, scale: 1, duration: 500, ease: 'Back.easeOut' });
      this.effects.sheet('fx_poof', b.x, b.y - 30, { size: 220 });
      Audio.play('sfx_build');
      this.focusCamera(b.x, b.y, 1600);
    }
  }

  popIn(pad) {
    const objs = [pad.pad.img, pad.label];
    for (const o of objs) {
      const sx = o.scaleX, sy = o.scaleY;
      o.setScale(0.01);
      this.tweens.add({ targets: o, scaleX: sx, scaleY: sy, duration: 380, ease: 'Back.easeOut' });
    }
    this.effects.sheet('fx_sparkle', pad.x, pad.y - 10, { size: 120 });
  }

  workerHome(type, index) {
    const h = WORLD.workerHome[type];
    return [h[0] + index * 40, h[1] + index * 20];
  }

  hireWorker(type, index, instant, x, y, role) {
    const home = Worker.homeFor(this, type, index, role);
    const w = new Worker(this, type, x !== undefined ? x : home[0], y !== undefined ? y : home[1], index, role);
    this.workers.push(w);
    if (!instant) {
      this.effects.sheet('fx_poof', w.x, w.y - 30, { size: 180 });
      this.effects.burst('star', w.x, w.y - 40, 12);
      w.sprite.setScale(0.1);
      this.tweens.add({ targets: w.sprite, scale: 1, duration: 450, ease: 'Back.easeOut' });
    }
    return w;
  }

  celebrate() {
    Audio.play('sfx_complete');
    this.ui.celebrate();
    const p = this.player;
    this.effects.sheet('fx_unlock', p.x, p.y - 20, { size: 320 });
    this.effects.sheet('fx_levelup', p.x, p.y + 4, { size: 240 });
    for (let i = 0; i < 10; i++) {
      this.time.delayedCall(i * 300, () => {
        const x = p.x + (Math.random() - 0.5) * 520, y = p.y - 160 - Math.random() * 320;
        this.effects.burst('confetti', x, y, 22);
        this.effects.burst('star', x, y, 12);
        this.effects.burst('glow', x, y, 1);
      });
    }
    this.effects.shake(300, 0.006);
    this.effects.vibrate(80);
  }

  // ------------------------------------------------------------------ helpers
  isOnScreen(x, y, margin = 0) {
    const v = this.cameras.main.worldView;
    return x > v.x - margin && x < v.right + margin && y > v.y - margin && y < v.bottom + margin;
  }
  isNear(x, y, d) { const p = this.player; return Math.abs(p.x - x) < d && Math.abs(p.y - y) < d; }

  /** positional sfx: only when (x, y) is on or near the screen, softer just outside it. `force` = always (the chief's own actions) */
  sfxAt(key, x, y, opts, force) {
    if (!force) {
      if (!this.isOnScreen(x, y, 220)) return;
      if (!this.isOnScreen(x, y, 0)) opts = Object.assign({}, opts, { volume: ((opts && opts.volume) !== undefined ? opts.volume : 1) * 0.5 });
    }
    Audio.play(key, opts);
  }

  findGatherable(x, y, range) {
    let best = null, bd = range * range;
    const check = (n) => {
      if (!n.ready()) return;
      const d = gdist2(x, y, n.x, n.y);
      if (d < bd) { bd = d; best = n; }
    };
    check(this.net);
    if (gdist2(x, y, this.net.gather.x, this.net.gather.y) < 55 * 55 && this.net.ready()) return this.net;
    for (const n of this.trees) check(n);
    for (const n of this.rocks) {
      if (!n.ready()) continue;
      const rr = range + n.standDist - 40;
      const d = gdist2(x, y, n.x, n.y);
      if (d < rr * rr && d - (n.standDist - 40) * (n.standDist - 40) < bd) { bd = Math.max(1, d - (n.standDist - 40) ** 2); best = n; }
    }
    for (const n of this.wheat) check(n);
    for (const n of this.animals) check(n);
    return best;
  }

  /** move one item from stack A to stack B in an arc; returns true if started */
  moveItem(from, to, types, opts = {}) {
    if (to.room <= 0) return false;
    const it = from.pop(types);
    if (!it) return false;
    to.reserve(it.type);
    const fx = it.spr.x, fy = it.spr.y;
    const isPlayerDest = to === this.player.stack;
    this.effects.fly(it.spr, fx, fy, () => to.nextPos(it.type), {
      dur: opts.dur || 240, height: opts.height || 60, scaleTo: to.scale,
      onDone: (s) => {
        to.arrive(it.type);
        to.push(it.type, s);
        if (from === this.player.stack && PRODUCT_ZONE[it.type] && (to === this.market.stock || to === this.trade.stock)) this.progress.hints[PRODUCT_ZONE[it.type]] = true;
        if (opts.sfx === 'pickup' || isPlayerDest) {
          if (isPlayerDest) Audio.play('sfx_pickup', { volume: 0.7, rate: 0.9 + Math.min(0.9, to.count * 0.045), throttle: 30 });
        } else if (opts.sfx === 'drop' && this.isNear(fx, fy, 500)) Audio.play('sfx_drop', { volume: 0.5, rate: 0.85 + Math.min(0.7, to.count * 0.03), throttle: 40 });
      },
    });
    return true;
  }

  /** spawn a fresh item at (x, y) that flies into character `ch`'s stack */
  spawnItemTo(type, x, y, ch, isPlayer, delay = 0) {
    const st = ch.stack;
    if (st.count + st.incoming >= (isPlayer ? this.player.capacity : st.max)) return false;
    st.reserve(type);
    const go = () => {
      const spr = this.effects.takeItem(type);
      spr.setScale(0.45);
      this.effects.fly(spr, x, y, () => st.nextPos(type), {
        dur: 300, height: 70, scaleTo: st.scale,
        onDone: (s) => {
          st.arrive(type);
          if (!ch.alive) { this.effects.releaseItem(s); return; }
          st.push(type, s);
          if (isPlayer) {
            Audio.play('sfx_pickup', { volume: 0.75, rate: 0.9 + Math.min(0.9, st.count * 0.05), throttle: 30 });
            if (st.count >= this.player.capacity) this.effects.floatText(ch.x, ch.y + ch.headTop - 30, 'MAX', '#ffd84a', 26);
          }
        },
      });
    };
    if (delay > 0) this.time.delayedCall(delay, go); else go();
    return true;
  }

  /** steer an agent toward (tx, ty); returns true when within `arrive` px */
  moveAgent(a, tx, ty, speed, dt, arrive = 8) {
    const dx = tx - a.x, dy = ty - a.y;
    const d = Math.hypot(dx, dy);
    if (d <= arrive) { a.vx = a.vy = 0; a.stuckT = 0; return true; }
    let vx = (dx / d) * speed, vy = (dy / d) * speed;
    // unstick: slide sideways for a moment when blocked
    if (a.sideT > 0) { a.sideT -= dt; const s = a.sideDir || 1; const ox = -vy * s, oy = vx * s; vx = vx * 0.3 + ox * 0.9; vy = vy * 0.3 + oy * 0.9; }
    // separation from other agents
    const list = this.agents;
    for (let i = 0; i < list.length; i++) {
      const o = list[i];
      if (o === a || !o.alive) continue;
      const ex = a.x - o.x, ey = (a.y - o.y) * 2;
      const e2 = ex * ex + ey * ey;
      if (e2 < 900 && e2 > 0.01) { const e = Math.sqrt(e2); vx += (ex / e) * 60; vy += (ey / e) * 30; }
    }
    const px = a.x, py = a.y;
    const p = a._mp || (a._mp = { x: 0, y: 0 });
    p.x = a.x + vx * dt; p.y = a.y + vy * dt;
    this.collision.resolve(p, a.radius);
    a.x = p.x; a.y = p.y;
    a.vx = vx; a.vy = vy;
    const moved = Math.hypot(a.x - px, a.y - py);
    if (moved < speed * dt * 0.25) { a.stuckT = (a.stuckT || 0) + dt; if (a.stuckT > 0.35) { a.sideT = 0.7; a.sideDir = Math.random() < 0.5 ? -1 : 1; a.stuckT = 0; } }
    else a.stuckT = 0;
    a.face(vx, vy);
    a.locomotion(true);
    return false;
  }

  // ------------------------------------------------------------------ update
  update(time, delta) {
    if (this._broken || !this.player) return;    // create() failed and a fresh restart is queued
    // an exception inside Phaser's loop would stop the game for good: report it once, keep running
    try { this.tick(time, delta); } catch (e) { if (!this._tickErr) { this._tickErr = true; console.error('[FrostVillage] update error:', e); } }
  }

  tick(time, delta) {
    const dt = Math.min(0.05, delta / 1000);
    const inp = Input.update(time);
    const p = this.player;
    this.ground.update(dt);
    p.update(dt, inp);

    // player pad interactions
    this.playerOnPad = this.progress.update(dt);
    this.padT -= dt;
    const onPadNow = this.handlePlayerPads(dt);
    this.playerOnPad = this.playerOnPad || onPadNow;

    this.net.update(dt);
    for (const n of this.trees) n.update(dt);
    for (const n of this.rocks) n.update(dt);
    for (const n of this.wheat) n.update(dt);
    for (const a of this.animals) a.update(dt);
    for (const s of this.stationList) s.update(dt);
    this.market.update(dt);
    this.trade.update(dt);
    for (const w of this.workers) w.update(dt);
    this.tutorial.update(dt);
    this.updateOccluders(dt);

    // camera target
    const ct = this.camTarget;
    let fx = p.x, fy = p.y - 30;
    if (this.tutorial.inTutorial && WORLD.tutorialView) {
      // first loop: frame net, grill, counter and queue together; follow the chief only near the edges
      const v = this.cameras.main.worldView, hw = v.width / 2, hh = v.height / 2;
      fx = Math.max(p.x - hw + 120, Math.min(p.x + hw - 120, WORLD.tutorialView[0]));
      fy = Math.max(p.y - 30 - hh + 260, Math.min(p.y - 30 + hh - 260, WORLD.tutorialView[1]));
    }
    if (this.camFocus) { if (time < this.camFocus.until) { fx = this.camFocus.x; fy = this.camFocus.y; } else this.camFocus = null; }
    const k = this.camFocus ? 1 - Math.pow(1 - 0.06, delta / 16.67) : 1 - Math.pow(1 - BALANCE.camera.lerp, delta / 16.67);
    ct.x += (fx - ct.x) * k; ct.y += (fy - ct.y) * k;

    // ambient snow
    this.snowT -= dt;
    if (this.snowT <= 0) {
      this.snowT = 0.09;
      const v = this.cameras.main.worldView;
      this.effects.emitters.snowfall.emitParticleAt(v.x + Math.random() * v.width, v.y - 20 + Math.random() * v.height * 0.6, 1);
    }

    // ambience by location
    this.ambT -= dt;
    if (this.ambT <= 0) {
      this.ambT = 0.25;
      const sea = Math.max(0, Math.min(1, 1 - (p.y - 400) / 900));
      Audio.setAmbience('amb_sea', 0.15 + sea * 0.6);
      let fire = 0;
      for (const s of this.stationList) if (s.working && s.enabled) { const d = Math.hypot(s.x - p.x, s.y - p.y); fire = Math.max(fire, 1 - d / 420); }
      for (const c of this.campfires || []) { const d = Math.hypot(c.x - p.x, c.y - p.y); fire = Math.max(fire, (1 - d / 350) * 0.7); }
      Audio.setAmbience('amb_fire', Math.max(0, fire) * 0.8);
    }
    Audio.updateAmbience(dt);

    this.saveT += dt;
    if (this.saveT >= BALANCE.autosaveEvery) { this.saveT = 0; this.save(false); }
  }

  handlePlayerPads(dt) {
    const p = this.player;
    let on = false;
    const ready = this.padT <= 0;
    const cap = p.capacity;
    for (const s of this.stationList) {
      if (!s.enabled) continue;
      if (s.inPad.contains(p.x, p.y)) {
        on = true;
        if (ready && p.stack.countOf(s.input) > 0) {
          if (s.feedFrom(p)) { this.padT = BALANCE.player.padItemInterval; s.inPad.pulse(); }
          else this.fullToast();
        }
      } else if (s.outPad.contains(p.x, p.y)) {
        on = true;
        if (ready) {
          if (s.takeTo(p, cap)) this.padT = BALANCE.player.padItemInterval;
          else if (s.outStack.count > 0 && p.room <= 0) p.warnFull();
        }
      }
    }
    if (this.market.shelf.contains(p.x, p.y)) {
      on = true;
      if (ready && p.stack.hasAny(FOODS) && this.market.feedFrom(p)) { this.padT = BALANCE.player.padItemInterval; this.market.shelf.pulse(); }
    }
    if (this.trade.enabled && this.trade.shelf.contains(p.x, p.y)) {
      on = true;
      if (ready && p.stack.hasAny(GOODS) && this.trade.feedFrom(p)) { this.padT = BALANCE.player.padItemInterval; this.trade.shelf.pulse(); }
    }
    if (this.market.cash.pad.contains(p.x, p.y) || (this.trade.enabled && this.trade.cash.pad.contains(p.x, p.y))) on = true;
    this.trash.setEnabled(this.progress.isDone('hire_fisherman'));
    if (this.trash.update(dt)) on = true;
    return on;
  }

  /** true when the station that takes `item` can neither accept more input nor make more output (gathering would only fill the bag with things nobody takes) */
  stationBlocked(item) {
    const st = this.stationByInput && this.stationByInput[item];
    return !!(st && st.enabled && st.inStack.full && st.outStack.full);
  }

  fullToast() {
    this._fullT = this._fullT || 0;
    if (this.time.now - this._fullT > 2500) { this._fullT = this.time.now; this.ui.toast(t('stationFull')); }
  }

  // ------------------------------------------------------------------ save / load
  serialize() {
    const st = {};
    for (const s of this.stationList) st[s.id] = s.serialize();
    // items in mid-air are saved where they are going; food a waiting customer got but has not paid for
    // yet (the queue is not saved) goes back on the shelf, and so do goods on their way to the merchant
    const shelf = (stock, types, extra) => { const o = {}; for (const ty of types) o[ty] = stock.countWithIncoming(ty) + ((extra && extra[ty]) || 0); return o; };
    const unpaid = {};
    for (const c of this.market.queue) for (const ty of c.bought.concat(c.flying || [])) unpaid[ty] = (unpaid[ty] || 0) + 1;
    const pl = this.player.stack;
    return {
      coins: this.economy.coins,
      progress: this.progress.serialize(),
      stations: st,
      market: { stock: shelf(this.market.stock, FOODS, unpaid), cash: this.market.cash.serialize() },
      trade: { stock: shelf(this.trade.stock, GOODS, this.trade.flying), cash: this.trade.cash.serialize() },
      player: { x: Math.round(this.player.x), y: Math.round(this.player.y), stack: pl.items.map((i) => i.type).concat(pl.inTypes) },
    };
  }

  save(force) {
    if (this.resetting || this._broken || !this.player) return;
    const ok = Save.write(this.serialize());
    if (!ok && !this._saveWarned) { this._saveWarned = true; this.ui.toast(t('noSave')); }
  }

  restore(sv) {
    const fx = this.effects;
    if (sv.stations) for (const s of this.stationList) s.restore(sv.stations[s.id]);
    const fill = (stock, obj, max) => { if (!obj) return; for (const ty in obj) for (let i = 0; i < Math.min(max, obj[ty] || 0); i++) stock.push(ty, null, fx); };
    if (sv.market) { fill(this.market.stock, sv.market.stock, this.market.maxPerType); this.market.cash.restore(sv.market.cash); }
    if (sv.trade) { fill(this.trade.stock, sv.trade.stock, this.trade.maxPerType); this.trade.cash.restore(sv.trade.cash); }
    if (sv.player && sv.player.stack) for (const ty of sv.player.stack.slice(0, this.player.capacity)) this.player.stack.push(ty, null, fx);
    this.market.restoreQueue(BALANCE.start.firstCustomers);
  }

  resetProgress() {
    this.resetting = true;
    Save.clear();
    Input.release();
    Audio.stopMusic();
    this.scene.stop('UI');
    this.scene.restart({ fresh: true });
    this.resetting = false;
  }

  // ------------------------------------------------------------------ test hooks
  installHooks() {
    const gs = this;
    const hooks = window.__FV || {};
    Object.assign(hooks, {
      game: this.game,
      scene: gs,
      state() {
        const p = gs.player;
        return {
          coins: gs.economy.coins,
          player: { x: Math.round(p.x), y: Math.round(p.y), anim: p.animName, stack: p.stack.items.map((i) => i.type), capacity: p.capacity },
          done: Object.keys(gs.progress.done).filter((k) => gs.progress.done[k]),
          upgrades: Object.assign({}, gs.progress.up),
          stations: Object.fromEntries(gs.stationList.map((s) => [s.id, { enabled: s.enabled, in: s.inStack.count, out: s.outStack.count, working: s.working }])),
          market: { stock: gs.market.stock.count, cash: gs.market.cash.value, queue: gs.market.queue.length },
          trade: { enabled: gs.trade.enabled, stock: gs.trade.stock.count, cash: gs.trade.cash.value },
          workers: gs.workers.map((w) => ({ type: w.type, state: w.state, carry: w.stack.count })),
          zones: Object.fromEntries(Object.keys(gs.zones).map((k) => [k, gs.zones[k].unlocked])),
          objective: gs.tutorial.textKey,
          pads: Object.keys(gs.progress.pads),
          fps: Math.round(gs.game.loop.actualFps),
        };
      },
      give(c) { gs.economy.add(Math.floor(c || 0)); return gs.economy.coins; },
      unlockAll() {
        const pr = gs.progress;
        for (const s of STEPS) {
          if (pr.done[s.id]) continue;
          pr.done[s.id] = true;
          const pad = pr.pads[s.id];
          if (pad) { pad.destroy(); delete pr.pads[s.id]; }
          if (s.type === 'zone') gs.revealZone(s.zone, true);
          if (s.type === 'hire') gs.hireWorker(s.worker, s.index || 0, true, undefined, undefined, s.role);
        }
        pr.openBench(true);
        pr.celebrated = true;
        for (const z of ['forest', 'farm', 'mine', 'hunt']) pr.hints[z] = true;
        pr.syncPads();
        gs.save(true);
        return Object.keys(pr.done);
      },
      teleport(x, y) { gs.player.x = x; gs.player.y = y; gs.camTarget.x = x; gs.camTarget.y = y - 30; gs.player.sync(0); },
      setInput(vx, vy) { Input.override = (vx || vy) ? { x: vx, y: vy } : null; },
      where(name) {
        const S = gs.stations;
        const m = {
          net: gs.net.gather, grillIn: S.grill.inPad, grillOut: S.grill.outPad, shelf: gs.market.shelf, cash: gs.market.cash.pad,
          tradeShelf: gs.trade.shelf, tradeCash: gs.trade.cash.pad, bench: gs.bench, trash: gs.trash,
        };
        for (const s of gs.stationList) { m[s.id + 'In'] = s.inPad; m[s.id + 'Out'] = s.outPad; }
        for (const id in gs.progress.pads) m[id] = gs.progress.pads[id];
        for (const k in gs.progress.upPads) m['up_' + k] = gs.progress.upPads[k];
        for (const id in gs.zones) m['zone:' + id] = { x: gs.zones[id].cfg.center[0], y: gs.zones[id].cfg.center[1] };
        if (name === 'tree') { const tr = gs.trees.find((n) => n.ready()); return tr && tr.standPoint(tr.x + 60, tr.y + 30); }
        if (name === 'rock') { const n = gs.rocks.find((r) => r.ready()); return n && n.standPoint(n.x + 80, n.y + 60); }
        if (name === 'wheat') { const n = gs.wheat.find((r) => r.ready()); return n && n.standPoint(n.x - 60, n.y + 30); }
        if (name === 'animal') { const n = gs.animals.find((a) => a.ready() && !a.targetedBy) || gs.animals.find((a) => a.ready()); return n && { x: Math.round(n.x - 30), y: Math.round(n.y + 10) }; }
        const o = m[name];
        return o ? { x: Math.round(o.x), y: Math.round(o.y) } : null;
      },
      camera(x, y, zoom) {
        const cam = gs.cameras.main;
        if (zoom) { gs.zoomBase = zoom; cam.setZoom(zoom * View.k); if (zoom < 0.7) cam.removeBounds(); }
        if (x !== undefined) gs.focusCamera(x, y, 1e9);
        else { gs.camFocus = null; gs.zoomBase = BALANCE.camera.zoom; cam.setZoom(gs.zoomBase * View.k); cam.setBounds(0, 0, gs.W, gs.H); }
      },
      save() { gs.save(true); },
      clearStack() { gs.player.stack.clear(gs.effects); gs.player.node = null; return 0; },
      reset() { gs.resetProgress(); },
      warnings() { return Array.from(Assets.warned); },
    });
    window.__FV = hooks;
  }
}
