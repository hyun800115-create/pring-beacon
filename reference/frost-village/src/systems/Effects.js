// Juice: pooled item sprites, particle bursts, animated fx sheets, floating texts, item arcs,
// camera shake and vibration. Everything degrades gracefully when fx assets are missing.

import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { DEPTH } from './DepthSort.js';
import { FONT } from '../data/strings.js';

// particle presets: key -> { sprite, size(px), ... }
const PRESETS = {
  wood:    { sprite: 'fx_chip_wood', size: 14, tint: [0xc98f55, 0xe2b57c, 0x8a5a33], speed: [90, 220], angle: [200, 340], gravityY: 600, life: [380, 650], rotate: true, qty: 7 },
  leaf:    { sprite: 'fx_leaf', size: 14, tint: [0x2e6b4f, 0x3f8a63], speed: [40, 120], angle: [200, 340], gravityY: 160, life: [600, 1000], rotate: true, qty: 4 },
  snowhit: { sprite: 'fx_snowflake', size: 12, tint: [0xdfe8f3, 0xc9d6e8, 0xafc3dc], speed: [50, 160], angle: [190, 350], gravityY: 220, life: [500, 900], rotate: true, qty: 7 },
  rock:    { sprite: 'fx_chip_rock', size: 13, tint: [0x8e96a3, 0x6f7784, 0xd9822b], speed: [100, 240], angle: [200, 340], gravityY: 650, life: [350, 600], rotate: true, qty: 8 },
  spark:   { sprite: 'fx_spark', size: 16, tint: [0xffc83d, 0xff8a2a, 0xffb03a], speed: [80, 220], angle: [0, 360], gravityY: 200, life: [200, 420], qty: 6 },
  wheat:   { sprite: 'fx_wheat_bit', size: 13, tint: [0xe8c25a, 0xf2d27a, 0xc9a03a], speed: [70, 190], angle: [200, 340], gravityY: 420, life: [400, 750], rotate: true, qty: 8 },
  splash:  { sprite: 'fx_droplet', size: 12, tint: [0x9cc7e6, 0xffffff, 0x2f86c9], speed: [80, 220], angle: [215, 325], gravityY: 700, life: [350, 650], qty: 9 },
  dust:    { sprite: 'fx_dust', size: 22, tint: [0xc9d6e8, 0xafc3dc], speed: [8, 30], angle: [180, 360], gravityY: -10, life: [300, 520], scaleEnd: 1.6, alpha: 0.75, qty: 2, ground: true },
  smoke:   { sprite: 'fx_smoke', size: 34, tint: [0xd9dee6, 0xbfc6d1, 0xeeeeee], speed: [10, 30], angle: [255, 285], gravityY: -45, life: [1300, 2000], scaleEnd: 2.2, alpha: 0.55, qty: 1 },
  heart:   { sprite: 'fx_heart', size: 26, tint: null, speed: [40, 90], angle: [240, 300], gravityY: -60, life: [700, 1000], qty: 3 },
  star:    { sprite: 'fx_star', size: 20, tint: [0xffc83d, 0xffffff, 0xffe08a], speed: [120, 320], angle: [0, 360], gravityY: 300, life: [450, 900], rotate: true, qty: 14, add: false },
  confetti:{ sprite: 'fx_star', size: 18, tint: [0xff6f91, 0x3d8be0, 0x5cc86a, 0xffc83d, 0xd9483b, 0xffffff], speed: [250, 620], angle: [235, 305], gravityY: 520, life: [1400, 2300], rotate: true, qty: 40 },
  coin:    { sprite: 'fx_coin', size: 18, tint: null, speed: [120, 260], angle: [220, 320], gravityY: 700, life: [400, 700], rotate: true, qty: 6 },
  glow:    { sprite: 'fx_glow', size: 46, tint: [0xffe08a], speed: [0, 10], angle: [0, 360], gravityY: 0, life: [300, 450], scaleEnd: 2.0, alpha: 0.8, qty: 1 },
  ring:    { sprite: 'fx_ring', size: 40, tint: [0x8fb4e0], speed: [0, 0], angle: [0, 360], gravityY: 0, life: [400, 500], scaleEnd: 3.0, alpha: 0.9, qty: 1 },
  flame:   { sprite: 'fx_flame', size: 18, tint: null, speed: [20, 50], angle: [250, 290], gravityY: -90, life: [350, 650], scaleEnd: 0.2, alpha: 0.95, qty: 1, add: true },
  snowfall:{ sprite: 'fx_snowflake', size: 9, tint: [0xffffff], speed: [10, 40], angle: [80, 110], gravityY: 12, life: [5000, 8000], rotate: true, qty: 1, alpha: 0.85 },
};

export class Effects {
  constructor(scene) {
    this.scene = scene;
    this.emitters = {};
    this.itemPool = [];
    this.sheetPool = [];
    this.textPool = [];
    this.flying = 0;
  }

  // ---------- item sprites (pooled) ----------
  takeItem(type) {
    const s = this.itemPool.pop() || this.scene.add.image(0, 0, '__WHITE');
    Assets.apply(s, type);
    s.setVisible(true).setAlpha(1).setScale(1).setAngle(0).setFlipX(false);
    s.__type = type;
    return s;
  }
  releaseItem(s) {
    if (!s) return;
    s.setVisible(false);
    this.itemPool.push(s);
  }

  // ---------- particles ----------
  emitter(name) {
    let e = this.emitters[name];
    if (e) return e;
    const p = PRESETS[name];
    const r = Assets.sprite(p.sprite);
    const fr = this.scene.textures.get(r.tex).get(r.frame);
    const base = p.size / Math.max(8, fr.width);
    const cfg = {
      lifespan: { min: p.life[0], max: p.life[1] },
      speed: { min: p.speed[0], max: p.speed[1] },
      angle: { min: p.angle[0], max: p.angle[1] },
      gravityY: p.gravityY,
      scale: { start: base, end: base * (p.scaleEnd !== undefined ? p.scaleEnd : 0.5) },
      alpha: { start: p.alpha !== undefined ? p.alpha : 1, end: 0 },
      emitting: false,
    };
    if (r.frame !== undefined) cfg.frame = r.frame;
    if (p.tint) cfg.tint = p.tint;
    if (p.rotate) cfg.rotate = { min: 0, max: 360 };
    if (p.add) cfg.blendMode = Phaser.BlendModes.ADD;
    e = this.scene.add.particles(0, 0, r.tex, cfg);
    e.setDepth(p.ground ? DEPTH.DUST : DEPTH.FX);
    this.emitters[name] = e;
    return e;
  }

  burst(name, x, y, qty) {
    const p = PRESETS[name];
    if (!p) return;
    const e = this.emitter(name);
    e.explode(qty || p.qty, x, y);
  }

  // ---------- animated fx sheets ----------
  sheet(key, x, y, opts = {}) {
    const anim = Assets.sheet(key);
    if (!anim) {
      // particle fallback
      const fb = { fx_poof: ['snowhit', 'glow'], fx_unlock: ['star', 'ring', 'glow'], fx_levelup: ['star', 'ring'], fx_hit: ['spark', 'glow'], fx_splash: ['splash'], fx_smoke_puff: ['smoke'], fx_sparkle: ['spark'] }[key] || ['glow'];
      for (const f of fb) this.burst(f, x, y);
      return null;
    }
    const s = this.sheetPool.pop() || this.scene.add.sprite(0, 0, key);
    const def = Assets.sheetDef(key) || {};
    s.setTexture(key, 0).setVisible(true).setAlpha(1).setAngle(0);
    s.setOrigin((def.anchor || [0.5, 0.5])[0], (def.anchor || [0.5, 0.5])[1]);
    const size = opts.size || 160;
    s.setScale(size / (def.frameWidth || 128));
    s.setBlendMode(def.blend === 'ADD' ? Phaser.BlendModes.ADD : Phaser.BlendModes.NORMAL);
    s.setPosition(x, y).setDepth(opts.depth !== undefined ? opts.depth : DEPTH.FX);
    s.play({ key: anim, repeat: 0 });   // one-shot even for looping sheets (loops use loop())
    s.once('animationcomplete', () => { s.setVisible(false); this.sheetPool.push(s); });
    return s;
  }

  /** looping sheet (fx_fire, fx_sparkle, fx_coin_spin) — returns sprite or null */
  loop(key, x, y, size, depth) {
    const anim = Assets.sheet(key);
    if (!anim) return null;
    const def = Assets.sheetDef(key) || {};
    const s = this.scene.add.sprite(x, y, key);
    s.setOrigin((def.anchor || [0.5, 0.5])[0], (def.anchor || [0.5, 0.5])[1]);
    s.setScale(size / (def.frameWidth || 128));
    if (def.blend === 'ADD') s.setBlendMode(Phaser.BlendModes.ADD);
    s.setDepth(depth);
    const an = this.scene.anims.get(anim);
    const n = an && an.frames ? an.frames.length : 1;
    s.play({ key: anim, repeat: -1, startFrame: Math.floor(Math.random() * Math.min(4, n)) });
    return s;
  }

  // ---------- floating text ----------
  floatText(x, y, text, color = '#ffffff', size = 30) {
    let t = this.textPool.pop();
    if (!t) {
      t = this.scene.add.text(0, 0, '', { fontFamily: FONT, fontSize: '30px', fontStyle: '900', color: '#ffffff', stroke: '#2b2f3a', strokeThickness: 7, resolution: 2 });
      t.setOrigin(0.5, 1);
    }
    t.setText(text).setColor(color).setFontSize(size).setPosition(x, y).setAlpha(1).setScale(0.6).setVisible(true).setDepth(DEPTH.LABEL);
    this.scene.tweens.add({ targets: t, scale: 1, duration: 160, ease: 'Back.easeOut' });
    this.scene.tweens.add({ targets: t, y: y - 70, alpha: 0, duration: 900, delay: 180, ease: 'Cubic.easeIn', onComplete: () => { t.setVisible(false); this.textPool.push(t); } });
  }

  // ---------- item flight ----------
  /**
   * Fly sprite `spr` in an arc from (fx, fy) to target ({x,y} or () => {x,y}). onDone(spr) on arrival.
   */
  fly(spr, fx, fy, target, opts = {}) {
    const dur = opts.dur || 260;
    const h = opts.height !== undefined ? opts.height : 70;
    const s0 = opts.scaleFrom !== undefined ? opts.scaleFrom : spr.scaleX;
    const s1 = opts.scaleTo !== undefined ? opts.scaleTo : s0;
    const spin = opts.spin || 0;
    spr.setPosition(fx, fy).setDepth(DEPTH.FLY + (this.flying++ % 100));
    const tw = this.scene.tweens.addCounter({
      from: 0, to: 1, duration: dur, ease: opts.ease || 'Linear',
      onUpdate: (t) => {
        const p = t.getValue();
        const tg = typeof target === 'function' ? target() : target;
        const x = fx + (tg.x - fx) * p;
        const y = fy + (tg.y - fy) * p - Math.sin(p * Math.PI) * h;
        spr.setPosition(x, y);
        spr.setScale(s0 + (s1 - s0) * p);
        if (spin) spr.setAngle(spin * p);
      },
      onComplete: () => { spr.setAngle(0); if (opts.onDone) opts.onDone(spr); },
    });
    return tw;
  }

  // ---------- camera ----------
  shake(ms = 140, amt = 0.004) { this.scene.cameras.main.shake(ms, amt); }
  vibrate(ms) { Audio.vibrate(ms); }

  /** squash & stretch pop on any game object with scale */
  pop(obj, amt = 0.18, dur = 110) {
    if (!obj || !obj.active) return;
    const sx = obj.__bs || 1, sy = obj.__bs || 1;
    this.scene.tweens.killTweensOf(obj);
    obj.setScale(sx * (1 + amt), sy * (1 - amt));
    this.scene.tweens.add({ targets: obj, scaleX: sx, scaleY: sy, duration: dur * 2.2, ease: 'Elastic.easeOut', easeParams: [1.2, 0.5] });
  }
}
