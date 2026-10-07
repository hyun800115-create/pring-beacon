// 경제: 코인(가게에서 주민에게 팔아서 벌기), 외부 상인, 카드 뽑기(확률 공개), 장식 보관함, 능력 효과(버프).

import { ITEMS, FOODS, NUM, MERCHANT, CARDS, CARD_COST, BUFF_CARDS, SPECIAL_PEOPLE, DECOS } from './defs.js';

export class Economy {
  constructor(game) {
    this.g = game;
    this.coins = NUM.startCoins;
    this.decos = {};            // 장식 보관함: 키 → 개수
    this.buffs = [];            // {name, buff:{...}, until: 날짜}
    this.merchant = null;       // {offers, until, doll, sled}
    this.daysSince = 0;
    this.earned = 0;
  }

  /** 지금 걸린 능력 효과 합 (work, speed, mood, grow) */
  buff(kind) { let s = 0; for (const b of this.buffs) s += b.buff[kind] || 0; return s; }

  earn(n, x, z) {
    if (n <= 0) return;
    this.coins += n; this.earned += n;
    if (x != null && this.g.stage.isNear(x, z)) this.g.bub.show({ x, z, y: 0.6, headY: 1.6 }, `+${n}`, 'emote_star', 1.4);
    this.g.audio.play('coin', 0.35, x, z);
  }

  /** 주민이 가게를 이용했다 → 창고 물건을 팔아 코인 */
  shopVisit(p, b) {
    const w = this.g.world, s = w.stock;
    let pool = [];
    if (b.type === 'tavern') pool = ['cheese', 'meat', 'bread', 'fish', 'honey', 'apple', 'egg'];
    else if (b.type === 'bakery') pool = ['bread'];
    else if (b.type === 'shop') pool = ['wool', 'honey', 'apple', 'egg', 'cheese'];
    else if (b.type === 'market') pool = ['apple', 'egg', 'milk', 'fish', 'wool'];
    const t = pool.find((k) => (s[k] || 0) >= 1);
    if (!t) { if (Math.random() < 0.3) this.g.people.say(p, 'grumble', false, 'emote_dots'); return 0; }
    s[t]--;
    const bonus = b.type === 'shop' && t === 'wool' ? 4 : 0;   // 털 → 옷으로 팔면 더 비싸요
    const n = (ITEMS[t].price || 2) + bonus;
    this.earn(n, b.x, b.z);
    if (FOODS.includes(t)) { p.hungry = false; p.ate = (p.ate || new Set()); p.ate.add(t); }
    p.joy = Math.min(0.3, (p.joy || 0) + 0.05);
    w.emit('stock');
    return n;
  }

  // ---------------------------------------------------------------- 외부 상인
  morning() {
    const day = this.g.clock.day;
    this.buffs = this.buffs.filter((b) => b.until > day);
    if (this.merchant && this.merchant.until <= day) this.leave();
    this.daysSince++;
    if (!this.merchant && this.g.world.hall && this.daysSince >= NUM.merchantEvery) { this.daysSince = 0; this.arrive(); }
  }

  async arrive() {
    const w = this.g.world, lib = this.g.lib;
    const stall = w.blds.find((b) => b.type === 'market' && b.state === 'active' && !b.ai);
    const at = stall ? stall.door : w.hall.toWorld(5, w.hall.size[1] / 2 + 4);
    const shuffled = MERCHANT.slice().sort(() => Math.random() - 0.5).slice(0, 6);
    await lib.loadProp('trade_post');
    const sled = lib.prop('trade_post');
    sled.position.set(at.x + 1.5, 0, at.z + 1.2); sled.rotation.y = Math.random() * 6;
    w.stage.scene.add(sled);
    const d = lib.char('npc_merchant');
    d.root.position.set(at.x, 0, at.z); d.play('wave');
    w.stage.scene.add(d.root);
    this.merchant = { offers: shuffled.map((o) => Object.assign({ sold: false }, o)), until: this.g.clock.day + 1, sled, doll: d, at, stall };
    this.g.people.news('🧳 외부 상인이 왔어요! 특별한 물건·생활용품·미술품을 팔아요 (위쪽 🧳 버튼)', 'party');
    this.g.hud.refresh();
  }
  leave() {
    const m = this.merchant; if (!m) return;
    this.g.stage.scene.remove(m.sled, m.doll.root);
    this.merchant = null;
    this.g.people.news('👋 외부 상인이 다음 마을로 떠났어요', 'info');
    this.g.hud.refresh();
  }
  update(dt) {
    const m = this.merchant; if (!m) return;
    m.doll.update(dt);
    m.t = (m.t || 0) + dt;
    if (m.t > 4) { m.t = 0; m.doll.play(['talk', 'wave', 'idle', 'laugh'][Math.floor(Math.random() * 4)]); }
  }

  offerName(o) { return o.kind === 'deco' ? DECOS[o.key].name : o.name; }
  offerDesc(o) { return o.kind === 'deco' ? `장식 · 주변 주민 기분 +${Math.round(DECOS[o.key].joy * 100)}` : o.desc || ''; }

  buy(o) {
    if (!o || o.sold) return '이미 팔렸어요';
    if (this.coins < o.price) return `코인이 ${o.price - this.coins}개 모자라요`;
    this.coins -= o.price; o.sold = true;
    this.apply(o, '상인');
    this.g.audio.play('coin', 0.7);
    return null;
  }

  apply(o, from) {
    const w = this.g.world;
    if (o.kind === 'deco') { this.decos[o.key] = (this.decos[o.key] || 0) + 1; this.g.people.news(`🌷 ${DECOS[o.key].name}을(를) 얻었어요. 장식 탭에서 놓을 수 있어요`, 'info'); }
    if (o.kind === 'buff') { this.buffs.push({ name: o.name, buff: o.buff, until: this.g.clock.day + o.buff.days }); this.g.people.news(`✨ ${o.name}: ${o.desc}`, 'party'); }
    if (o.kind === 'goods') { for (const [k, v] of Object.entries(o.goods)) w.stock[k] = (w.stock[k] || 0) + v; w.emit('stock'); this.g.people.news(`📦 ${o.name}이(가) 창고에 들어왔어요`, 'info'); }
    void from;
  }

  // ---------------------------------------------------------------- 카드 뽑기
  draw() {
    if (this.coins < CARD_COST) return { err: `코인이 ${CARD_COST - this.coins}개 모자라요` };
    this.coins -= CARD_COST;
    let r = Math.random(), card = CARDS[CARDS.length - 1];
    for (const c of CARDS) { if (r < c.rate) { card = c; break; } r -= c.rate; }
    const pick = (a) => a[Math.floor(Math.random() * a.length)];
    let res;
    if (card.kind === 'person') {
      const sp = pick(SPECIAL_PEOPLE);
      res = { card, title: sp.name, desc: '특별한 주민이 마을로 이사 와요!' };
      this.g.people.specialArrive(sp);
    } else if (card.kind === 'deco') {
      const key = pick(Object.keys(DECOS));
      res = { card, title: DECOS[key].name, desc: '장식 탭에서 놓을 수 있어요' };
      this.apply({ kind: 'deco', key });
    } else if (card.kind === 'buff') {
      const b = pick(BUFF_CARDS);
      res = { card, title: b.name, desc: b.desc };
      this.apply({ kind: 'buff', name: b.name, desc: b.desc, buff: b.buff });
    } else {
      const packs = [{ plank: 8, stone: 6 }, { bread: 6, fish: 4 }, { log: 10, plank: 4 }, { stone: 10 }, { cheese: 3, honey: 2, apple: 4 }];
      const goods = pick(packs);
      res = { card, title: '물건 꾸러미', desc: Object.entries(goods).map(([k, v]) => `${ITEMS[k].name} ${v}`).join(' · ') };
      this.apply({ kind: 'goods', name: '물건 꾸러미', goods });
    }
    this.g.audio.play('complete', 0.6);
    return res;
  }

  /** 장식이 주는 기분 (주민 위치 근처) */
  decoJoy(x, z) {
    let j = 0;
    for (const b of this.g.world.blds) { if (b.def.deco && b.state === 'active' && Math.hypot(b.x - x, b.z - z) < 10) j += b.def.joy; }
    return Math.min(0.2, j);
  }
}
