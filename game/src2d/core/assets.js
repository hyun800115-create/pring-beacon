// 그림·소리 불러오기. 서리마을 매니페스트(manifest.json)를 읽어 필요한 것만 불러오고,
// 아직 그림이 없는 것(풍차·돌·밀가루·깃발)은 여기서 직접 그린다. 그림이 없으면 회색 상자로 대신한다.

import { CHARS_NEEDED } from '../data/defs.js';

const BASE = 'assets/';
const FRAGS = ['props', 'life_props', 'emotes', 'ground', 'characters', 'villagers', 'audio'];
const SOUNDS = ['bgm_village', 'sfx_build', 'sfx_complete', 'sfx_click', 'sfx_error', 'sfx_drop', 'sfx_pickup',
  'sfx_saw', 'sfx_chop_1', 'sfx_mine_1', 'sfx_harvest_1', 'sfx_oven', 'sfx_coin'];

export const Assets = {
  chars: {},        // 캐릭터 키 → 매니페스트 항목
  sprites: {},      // 소품 키 → 매니페스트 항목 (anchor 등)
  audio: {},        // 소리 키 → 매니페스트 항목
  scene: null,

  queueManifests(load) {
    for (const f of FRAGS) load.json('mf_' + f, BASE + f + '/manifest.json');
  },

  queueFiles(scene) {
    const load = scene.load, cache = scene.cache.json;
    const mf = (f) => (cache.exists('mf_' + f) ? cache.get('mf_' + f) : {});
    for (const f of ['props', 'life_props', 'emotes']) {
      const m = mf(f);
      for (const a of m.atlases || []) load.atlas(a.key, BASE + a.png, BASE + a.json);
      Object.assign(this.sprites, m.sprites || {});
    }
    const ground = mf('ground');
    for (const im of ground.images || []) if (im.key === 'ground_snow' || im.key === 'ground_dirt') load.image(im.key, BASE + im.png);
    for (const f of ['characters', 'villagers']) {
      const m = mf(f);
      const atl = {};
      for (const a of m.atlases || []) atl[a.key] = a;
      for (const k of CHARS_NEEDED) {
        const c = (m.characters || {})[k];
        if (!c || !atl[c.atlas]) continue;
        this.chars[k] = c;
        load.atlas(c.atlas, BASE + atl[c.atlas].png, BASE + atl[c.atlas].json);
      }
    }
    const au = mf('audio').audio || {};
    for (const k of SOUNDS) {
      const a = au[k];
      if (!a) continue;
      this.audio[k] = a;
      load.audio(k, a.files.map((p) => BASE + p));
    }
  },

  /** 캐릭터 동작(애니메이션) 만들기: 키 = "캐릭터:동작:방향" */
  makeAnims(scene) {
    for (const k in this.chars) {
      const c = this.chars[k];
      const tex = scene.textures.exists(c.atlas) ? scene.textures.get(c.atlas) : null;
      if (!tex) { delete this.chars[k]; continue; }
      for (const an in c.anims) {
        const a = c.anims[an];
        for (const d of a.dirs || c.dirs) {
          const frames = [];
          for (let i = 0; i < a.frames; i++) {
            const fn = c.frameName.replace('{anim}', an).replace('{dir}', d).replace('{i}', i);
            if (tex.has(fn)) frames.push({ key: c.atlas, frame: fn });
          }
          if (frames.length) scene.anims.create({ key: `${k}:${an}:${d}`, frames, frameRate: a.fps, repeat: a.repeat });
        }
      }
    }
    // 가공 건물 작업 동작 (매니페스트 anims.work)
    for (const k in this.sprites) {
      const s = this.sprites[k];
      if (!s.anims || !s.anims.work || !scene.textures.exists(s.atlas)) continue;
      const w = s.anims.work;
      scene.anims.create({ key: 'work:' + k, frames: w.frames.map((f) => ({ key: s.atlas, frame: f })), frameRate: w.fps, repeat: -1 });
    }
  },

  /** [텍스처, 프레임, 앵커x, 앵커y] — 없으면 회색 상자 */
  tex(scene, atlas, frame) {
    if (frame == null) {
      if (scene.textures.exists(atlas)) { const g = GEN_ANCHOR[atlas] || [0.5, 0.5]; return [atlas, undefined, g[0], g[1]]; }
      return ['gen_box', undefined, 0.5, 0.8];
    }
    if (scene.textures.exists(atlas) && scene.textures.get(atlas).has(frame)) {
      const s = this.sprites[frame];
      const an = s && s.anchor ? s.anchor : [0.5, 0.75];
      return [atlas, frame, an[0], an[1]];
    }
    return ['gen_box', undefined, 0.5, 0.8];
  },

  play(scene, key, vol = 1) {
    if (!this.audio[key] || !scene.cache.audio.exists(key)) return;
    try { scene.sound.play(key, { volume: (this.audio[key].volume || 0.6) * vol }); } catch (e) { /* 소리 실패는 무시 */ }
  },

  /** 아직 그림이 없는 것들을 직접 그린다 */
  makeGenerated(scene) {
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    const ink = 0x3a3040;

    // 회색 상자 (그림이 없을 때)
    g.clear();
    g.fillStyle(0x9aa1ab, 1); g.fillRect(8, 8, 80, 70);
    g.lineStyle(4, ink, 1); g.strokeRect(8, 8, 80, 70);
    g.generateTexture('gen_box', 96, 88);

    // 깃발
    g.clear();
    g.fillStyle(0xffffff, 0.9); g.fillEllipse(12, 66, 22, 9);
    g.lineStyle(4, 0x5a3c26, 1); g.lineBetween(12, 66, 12, 6);
    g.fillStyle(0xe2493a, 1); g.lineStyle(2.5, ink, 1);
    g.beginPath(); g.moveTo(13, 6); g.lineTo(40, 14); g.lineTo(13, 23); g.closePath(); g.fillPath(); g.strokePath();
    g.fillStyle(0xffd76a, 1); g.fillCircle(12, 5, 3.5);
    g.generateTexture('gen_flag', 44, 72);

    // 그림자 (사람 발밑)
    g.clear(); g.fillStyle(0x3b4a66, 0.22); g.fillEllipse(24, 10, 46, 18); g.generateTexture('gen_shadow', 48, 20);

    // 물건: 돌
    g.clear();
    const stone = (x, y, rx, ry) => {
      g.fillStyle(0x7f8996, 1); g.fillEllipse(x, y, rx * 2, ry * 2);
      g.fillStyle(0xaab3be, 1); g.fillEllipse(x - rx * 0.2, y - ry * 0.3, rx * 1.3, ry * 1.1);
      g.lineStyle(2.5, ink, 1); g.strokeEllipse(x, y, rx * 2, ry * 2);
    };
    stone(26, 48, 15, 10); stone(47, 49, 14, 9); stone(36, 36, 13, 10);
    g.generateTexture('gen_item_stone', 72, 72);

    // 물건: 밀가루 자루
    g.clear();
    g.fillStyle(0xeee3c8, 1); g.lineStyle(2.5, ink, 1);
    g.fillRoundedRect(20, 24, 32, 32, 12); g.strokeRoundedRect(20, 24, 32, 32, 12);
    g.fillStyle(0xd9c9a6, 1); g.fillRoundedRect(38, 28, 12, 26, 8);
    g.fillStyle(0xeee3c8, 1); g.beginPath(); g.moveTo(28, 25); g.lineTo(24, 14); g.lineTo(48, 14); g.lineTo(44, 25); g.closePath(); g.fillPath(); g.strokePath();
    g.lineStyle(3, 0xb0583e, 1); g.lineBetween(26, 24, 46, 24);
    g.fillStyle(0xffffff, 1); g.fillCircle(31, 39, 5); g.fillCircle(27, 45, 3);
    g.generateTexture('gen_item_flour', 72, 72);

    // 풍차 몸통 (날개는 따로 돌아간다). 240×330, 앵커 (120, 284)
    g.clear();
    g.fillStyle(0x3b4a66, 0.16); g.fillEllipse(150, 290, 190, 62);
    g.fillStyle(0x8e97a3, 1); g.fillEllipse(120, 284, 156, 58);
    g.fillStyle(0xb8c0ca, 1); g.fillEllipse(120, 276, 150, 50);
    g.lineStyle(3, ink, 1); g.strokeEllipse(120, 280, 156, 58);
    g.fillStyle(0xeadfca, 1);
    g.beginPath(); g.moveTo(62, 276); g.lineTo(178, 276); g.lineTo(152, 118); g.lineTo(88, 118); g.closePath(); g.fillPath();
    g.fillStyle(0xd3c3a6, 1);
    g.beginPath(); g.moveTo(124, 276); g.lineTo(178, 276); g.lineTo(152, 118); g.lineTo(122, 118); g.closePath(); g.fillPath();
    g.lineStyle(3, ink, 1);
    g.beginPath(); g.moveTo(62, 276); g.lineTo(178, 276); g.lineTo(152, 118); g.lineTo(88, 118); g.closePath(); g.strokePath();
    g.lineStyle(5, 0x8a6142, 1); g.lineBetween(72, 222, 168, 222); g.lineBetween(80, 172, 160, 172);
    g.fillStyle(0x7a5236, 1); g.fillRoundedRect(103, 236, 30, 40, { tl: 14, tr: 14, bl: 0, br: 0 });
    g.lineStyle(2.5, ink, 1); g.strokeRoundedRect(103, 236, 30, 40, { tl: 14, tr: 14, bl: 0, br: 0 });
    g.fillStyle(0x3b4a66, 1); g.fillCircle(118, 196, 10); g.lineStyle(3, 0x8a6142, 1); g.strokeCircle(118, 196, 11);
    g.fillStyle(0xb4553d, 1);
    g.beginPath(); g.moveTo(76, 124); g.lineTo(164, 124); g.lineTo(120, 34); g.closePath(); g.fillPath();
    g.fillStyle(0x8f412f, 1);
    g.beginPath(); g.moveTo(122, 124); g.lineTo(164, 124); g.lineTo(120, 34); g.closePath(); g.fillPath();
    g.fillStyle(0xffffff, 1);
    g.beginPath(); g.moveTo(103, 70); g.lineTo(120, 34); g.lineTo(137, 70); g.lineTo(130, 78); g.lineTo(121, 70); g.lineTo(111, 79); g.closePath(); g.fillPath();
    g.lineStyle(3, ink, 1);
    g.beginPath(); g.moveTo(76, 124); g.lineTo(164, 124); g.lineTo(120, 34); g.closePath(); g.strokePath();
    g.generateTexture('gen_windmill', 240, 330);

    // 풍차 날개 220×220 (가운데 축)
    g.clear();
    const c = 110;
    for (let k = 0; k < 4; k++) {
      const a = k * Math.PI / 2 + Math.PI / 4;
      const ca = Math.cos(a), sa = Math.sin(a), px = -sa, py = ca;
      const P = (r, w) => ({ x: c + ca * r + px * w, y: c + sa * r + py * w });
      const q = [P(18, 0), P(104, 0), P(104, 24), P(18, 24)];
      g.fillStyle(0xf5efe3, 1); g.lineStyle(2.5, ink, 1);
      g.beginPath(); g.moveTo(q[0].x, q[0].y); for (const p of q.slice(1)) g.lineTo(p.x, p.y); g.closePath(); g.fillPath(); g.strokePath();
      g.lineStyle(2, 0xb59a7a, 1);
      for (let r = 36; r < 104; r += 17) { const a1 = P(r, 0), a2 = P(r, 24); g.lineBetween(a1.x, a1.y, a2.x, a2.y); }
      const m1 = P(18, 12), m2 = P(104, 12); g.lineBetween(m1.x, m1.y, m2.x, m2.y);
      g.lineStyle(5, 0x6e4a30, 1); const s1 = P(6, -2), s2 = P(106, -2); g.lineBetween(s1.x, s1.y, s2.x, s2.y);
    }
    g.fillStyle(0x6e4a30, 1); g.fillCircle(c, c, 11); g.lineStyle(2.5, ink, 1); g.strokeCircle(c, c, 11);
    g.generateTexture('gen_windmill_blades', 220, 220);

    // 공사장 바닥 (흙 마름모는 게임에서 그린다), 말뚝
    g.clear();
    g.fillStyle(0x8a6142, 1); g.fillRect(3, 0, 6, 34); g.lineStyle(2, ink, 1); g.strokeRect(3, 0, 6, 34);
    g.fillStyle(0xf2c14e, 1); g.fillRect(3, 4, 6, 6);
    g.generateTexture('gen_stake', 12, 36);

    // 무덤 (장례식)
    g.clear();
    g.fillStyle(0x3b4a66, 0.18); g.fillEllipse(34, 62, 56, 16);
    g.fillStyle(0x9aa3ae, 1); g.lineStyle(3, ink, 1);
    g.fillRoundedRect(16, 14, 36, 48, { tl: 16, tr: 16, bl: 2, br: 2 }); g.strokeRoundedRect(16, 14, 36, 48, { tl: 16, tr: 16, bl: 2, br: 2 });
    g.fillStyle(0xc2c9d2, 1); g.fillRoundedRect(20, 18, 14, 40, { tl: 12, tr: 4, bl: 2, br: 2 });
    g.lineStyle(3, 0x6b7380, 1); g.lineBetween(34, 26, 34, 44); g.lineBetween(27, 32, 41, 32);
    g.fillStyle(0xf28fb0, 1); g.fillCircle(14, 60, 5); g.fillStyle(0xffe07a, 1); g.fillCircle(22, 63, 4); g.fillStyle(0xffffff, 1); g.fillCircle(52, 62, 4);
    g.generateTexture('gen_grave', 68, 72);

    g.destroy();
  },
};

/** 직접 그린 그림의 앵커 */
const GEN_ANCHOR = {
  gen_windmill: [0.5, 284 / 330],
  gen_item_stone: [0.5, 0.75],
  gen_item_flour: [0.5, 0.75],
  gen_flag: [12 / 44, 66 / 72],
  gen_box: [0.5, 0.8],
};
