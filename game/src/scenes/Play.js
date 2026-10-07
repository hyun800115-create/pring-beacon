// 게임 화면: 땅·길 그리기, 카메라(이동·확대·축소), 입력(길·건물·철거·누르기), 화면 밖 숨기기, 낮과 밤.

import { Assets } from '../core/assets.js';
import { World } from '../world/world.js';
import { People } from '../world/people.js';
import { Clock, PHASE } from '../world/clock.js';
import { BUILDINGS, NUM, ITEMS } from '../data/defs.js';
import { Hud } from '../ui/hud.js';

const ZMIN = 0.22, ZMAX = 1.6;

export class Play extends Phaser.Scene {
  constructor() { super('Play'); }

  create(data) {
    this.perf = !!(data && data.perf);
    this.dpr = window.__SM.Screen.dpr;
    this.speed = 1;
    this.mode = 'view';
    this.zoom = this.perf ? 0.45 : (window.innerHeight < 500 ? 0.55 : 0.8);
    this.frameN = 0;

    const world = this.world = new World(this, { n: this.perf ? 150 : 64, perf: this.perf });
    this.clock = new Clock();
    this.people = new People(world, this.clock);
    world.generate();

    // 땅 (카메라를 따라다니는 반복 무늬)
    this.ground = this.add.tileSprite(0, 0, 64, 64, 'ground_snow').setOrigin(0, 0).setDepth(-20000);
    this.edgeG = this.add.graphics().setDepth(-19000);
    const iso = world.iso, n = world.n;
    const corners = [iso.toWorld(-0.5, -0.5), iso.toWorld(-0.5, n - 0.5), iso.toWorld(n - 0.5, n - 0.5), iso.toWorld(n - 0.5, -0.5)];
    this.edgeG.lineStyle(10, 0xffffff, 0.8); this.edgeG.strokePoints(corners, true);
    this.edgeG.lineStyle(3, 0x9fb3cc, 0.9); this.edgeG.strokePoints(corners, true);
    this.pv = this.add.graphics().setDepth(44000);
    this.ghost = this.add.image(0, 0, 'gen_box').setAlpha(0.55).setDepth(44001).setVisible(false);
    world.on('roads', () => this.drawRoads());

    const cam = this.cameras.main;
    cam.setBounds(-400, -400, iso.width + 800, iso.height + 800);
    this.applyZoom(this.zoom);

    if (this.perf) this.setupPerf();
    else this.setupStart();

    this.hud = new Hud(this);
    world.on('built', (b) => this.onBuilt(b));
    world.on('news', (t, k) => this.hud.news(t, k));
    world.on('offer', (o) => this.hud.offer(o));
    this.setupInput();
    this.cullAll(true);
    this.installHooks();
  }

  // ---------------------------------------------------------------- 시작 장면
  setupStart() {
    const w = this.world;
    const st = w.startTile;
    const p = w.W(st.i, st.j);
    const spr = w.sprite('props_buildings', 'trade_post', p.x, p.y, st.i, st.j, 1);
    w.wagon = { x: p.x, y: p.y, i: st.i, j: st.j, spr, door: { x: p.x - 40, y: p.y + 30 } };
    for (let j = st.j - 1; j <= st.j; j++) for (let i = st.i - 1; i <= st.i + 1; i++) w.map.setOcc(i, j, { type: 'wagon', ref: null });
    this.people.startCaravan(p.x, p.y);
    this.mode = 'settle';
    this.centerOn(p.x, p.y);
  }

  onBuilt(b) {
    const w = this.world;
    if (b.type === 'hall' && w.wagon) {
      this.people.unloadWagon(b, w.wagon);
      const wg = w.wagon;
      this.time.delayedCall(9000, () => {
        this.tweens.add({ targets: wg.spr, alpha: 0, duration: 1500, onComplete: () => w.killStatic(wg.spr) });
        for (let j = wg.j - 1; j <= wg.j; j++) for (let i = wg.i - 1; i <= wg.i + 1; i++) { const o = w.map.occAt(i, j); if (o && o.type === 'wagon') w.map.setOcc(i, j, null); }
        w.wagon = null;
      });
      this.people.news('🏛️ 마을회관이 완성됐어요! 이제 길을 깔고 건물을 지어 보세요', 'party');
      this.hud.refresh();
    } else if (b.def.kind === 'house') {
      this.people.assignHomes();
      this.people.news(`🏠 ${b.def.levels[b.level].name}이(가) 완성됐어요`, 'info');
    } else {
      this.people.news(`✅ ${b.def.name}이(가) 완성됐어요`, 'info');
    }
  }

  // ---------------------------------------------------------------- 성능 시험 (넓은 지도 + 짐꾼 수백 명)
  setupPerf() {
    const w = this.world, m = w.map, n = w.n, ppl = this.people;
    const c = Math.floor(n / 2);
    const G = 4, K = 17, i0 = c - (G * (K - 1)) / 2, j0 = c - (G * (K - 1)) / 2;
    // 길 자리의 나무 치우기
    const clearTile = (i, j) => { const o = m.objAt(i, j); if (o) { w.killStatic(o.spr); m.setObj(i, j, null); } };
    for (let a = 0; a < K; a++) for (let k = 0; k <= G * (K - 1); k++) { clearTile(i0 + a * G, j0 + k); clearTile(i0 + k, j0 + a * G); }
    for (let j = c - 2; j <= c + 2; j++) for (let i = c - 2; i <= c + 2; i++) clearTile(i, j);
    const flags = [];
    for (let a = 0; a < K; a++) for (let b = 0; b < K; b++) flags.push(w.addFlag(i0 + a * G, j0 + b * G));
    for (let a = 0; a < K; a++) for (let b = 0; b < K; b++) {
      if (a < K - 1) { const t = []; for (let k = 0; k <= G; k++) t.push([i0 + a * G + k, j0 + b * G]); w.makeRoad(t); }
      if (b < K - 1) { const t = []; for (let k = 0; k <= G; k++) t.push([i0 + a * G, j0 + b * G + k]); w.makeRoad(t); }
    }
    // 길마다 짐꾼 한 명
    for (const r of w.roads) {
      const mid = r.pts.length >> 1, pt = r.pts[mid];
      const p = ppl.makePerson({ x: pt.x, y: pt.y });
      p.job = { kind: 'carrier', road: r, x: pt.x, y: pt.y }; r.carrier = p; p.onRoad = true; p.ri = mid;
    }
    const rf = () => flags[Math.floor(w.rng.next() * flags.length)];
    for (let k = 0; k < 700; k++) {
      const f = rf();
      if (f.items.length >= NUM.flagCap) continue;
      const types = Object.keys(ITEMS);
      w.newItem(types[k % types.length], f, { flag: rf(), perf: true });
    }
    w.on('perfArrive', (it) => { it.dest = { flag: rf(), perf: true }; it.road = it.flag ? w.nextRoad(it.flag, it.dest.flag) : null; });
    this.clock.t = 0.25;
    this.perfFlags = flags;
    this.mode = 'view';
    const cp = w.W(c, c);
    this.centerOn(cp.x, cp.y);
    this.drawRoads();
  }

  // ---------------------------------------------------------------- 그리기
  drawRoads() {
    // 길은 구역(청크)마다 따로 그려서 화면에 보이는 구역만 그린다
    const w = this.world;
    this.roadGs = this.roadGs || new Map();
    for (const g of this.roadGs.values()) w.killStatic(g);
    this.roadGs.clear();
    const by = new Map();
    for (const r of w.roads) {
      const t = r.tiles[r.tiles.length >> 1], c = w.chunkOf(t[0], t[1]);
      if (!by.has(c)) by.set(c, { list: [], t });
      by.get(c).list.push(r);
    }
    for (const [c, { list, t }] of by) {
      const g = this.add.graphics().setDepth(-14500);
      for (const r of list) {
        g.lineStyle(30, 0x8f7356, 0.55); g.strokePoints(r.pts, false);
        g.fillStyle(0x8f7356, 0.55); for (const p of r.pts) g.fillEllipse(p.x, p.y, 30, 22);
      }
      for (const r of list) {
        g.lineStyle(18, 0xc7a780, 1); g.strokePoints(r.pts, false);
        g.fillStyle(0xc7a780, 1); for (const p of r.pts) g.fillEllipse(p.x, p.y, 18, 13);
      }
      if (!this.perf) for (const r of list) {
        g.fillStyle(0xe0c49c, 1);
        for (let k = 0; k < r.pts.length - 1; k++) { const a = r.pts[k], b = r.pts[k + 1]; g.fillCircle((a.x * 2 + b.x) / 3, (a.y * 2 + b.y) / 3 + 2, 2.2); g.fillCircle((a.x + b.x * 2) / 3 - 3, (a.y + b.y * 2) / 3 - 1, 1.8); }
      }
      w.addStatic(g, t[0], t[1]);
      this.roadGs.set(c, g);
    }
  }

  // ---------------------------------------------------------------- 카메라
  applyZoom(z, px, py) {
    const cam = this.cameras.main;
    z = Phaser.Math.Clamp(z, ZMIN, ZMAX);
    const z0 = cam.zoom, z1 = z * this.dpr;
    if (px == null) { px = cam.width / 2; py = cam.height / 2; }
    const wx = cam.scrollX + cam.width / 2 + (px - cam.width / 2) / z0;
    const wy = cam.scrollY + cam.height / 2 + (py - cam.height / 2) / z0;
    cam.setZoom(z1);
    cam.scrollX = wx - cam.width / 2 - (px - cam.width / 2) / z1;
    cam.scrollY = wy - cam.height / 2 - (py - cam.height / 2) / z1;
    this.zoom = z;
  }
  zoomBy(f, px, py) { this.applyZoom(this.zoom * f, px, py); }
  centerOn(x, y) { this.cameras.main.centerOn(x, y); }

  isVisible(x, y, m = 160) {
    const v = this.cameras.main.worldView;
    return x > v.x - m && x < v.right + m && y > v.y - m && y < v.bottom + m * 1.6;
  }

  cullAll(force) {
    const w = this.world, cam = this.cameras.main, v = cam.worldView;
    if (!v.width) return;
    const pts = [[v.x, v.y], [v.right, v.y], [v.x, v.bottom], [v.right, v.bottom]].map(([x, y]) => w.iso.toTileF(x, y));
    const i0 = Math.min(...pts.map((p) => p.i)) - 6, i1 = Math.max(...pts.map((p) => p.i)) + 6;
    const j0 = Math.min(...pts.map((p) => p.j)) - 6, j1 = Math.max(...pts.map((p) => p.j)) + 6;
    const N = w.chunkN, C = w.n / N;
    let changed = false;
    for (let cj = 0; cj < N; cj++) for (let ci = 0; ci < N; ci++) {
      const k = cj * N + ci;
      const on = (ci + 1) * C >= i0 && ci * C <= i1 && (cj + 1) * C >= j0 && cj * C <= j1 ? 1 : 0;
      if (!force && w.chunkVis[k] === on) continue;
      w.chunkVis[k] = on; changed = true;
      for (const s of w.chunks[k]) s.setVisible(!!on && !s.__hide);
    }
    if (changed || force) for (const f of w.flags) { const vis = !!w.chunkVis[w.chunkOf(f.i, f.j)]; for (const it of f.items) it.spr.setVisible(vis); }
  }

  // ---------------------------------------------------------------- 입력
  setupInput() {
    const inp = this.input;
    this.drag = null;
    inp.on('pointerdown', (p) => this.onDown(p));
    inp.on('pointermove', (p) => this.onMove(p));
    inp.on('pointerup', (p) => this.onUp(p));
    inp.on('wheel', (p, objs, dx, dy) => { this.zoomBy(dy > 0 ? 0.88 : 1.14, p.x, p.y); });
    this.keys = inp.keyboard.addKeys('W,A,S,D,UP,DOWN,LEFT,RIGHT,Q,E,ESC,PLUS,MINUS');
    inp.keyboard.on('keydown-ESC', () => this.setMode('view'));
  }

  tileAt(p) { return this.world.iso.toTile(p.worldX, p.worldY); }

  onDown(p) {
    const ps = this.input.manager.pointers.filter((q) => q.isDown);
    if (ps.length >= 2) {
      const [a, b] = ps;
      this.pinch = { d: Phaser.Math.Distance.Between(a.x, a.y, b.x, b.y), z: this.zoom };
      this.drag = null;
      return;
    }
    this.drag = { x: p.x, y: p.y, sx: this.cameras.main.scrollX, sy: this.cameras.main.scrollY, moved: false, t: this.time.now, road: false };
    if (this.mode === 'road') {
      const t = this.tileAt(p);
      this.drag.roadFrom = this.flagFromTile(t.i, t.j);
    }
  }

  onMove(p) {
    if (this.pinch) {
      const ps = this.input.manager.pointers.filter((q) => q.isDown);
      if (ps.length >= 2) {
        const [a, b] = ps;
        const d = Phaser.Math.Distance.Between(a.x, a.y, b.x, b.y);
        this.applyZoom(this.pinch.z * d / Math.max(1, this.pinch.d), (a.x + b.x) / 2, (a.y + b.y) / 2);
      }
      return;
    }
    const d = this.drag;
    if (d && p.isDown) {
      if (Math.hypot(p.x - d.x, p.y - d.y) > 10 * this.dpr) d.moved = true;
      if (d.roadFrom && d.moved && !d.road) { d.road = true; this.roadStart = d.roadFrom; this.roadPlan = null; }
      if (d.road) { this.previewRoad(p); return; }
      if (d.moved) {
        const cam = this.cameras.main;
        cam.scrollX = d.sx - (p.x - d.x) / cam.zoom;
        cam.scrollY = d.sy - (p.y - d.y) / cam.zoom;
      }
      return;
    }
    this.hover = p;
  }

  onUp(p) {
    if (this.pinch) { if (!this.input.manager.pointers.some((q) => q.isDown)) this.pinch = null; return; }
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (d.road && d.moved) { this.commitRoad(); return; }
    if (!d.moved) this.tap(p);
  }

  flagFromTile(i, j) {
    const o = this.world.map.occAt(i, j);
    if (!o) return null;
    if (o.type === 'flag') return o.ref;
    if (o.type === 'bld' && o.ref.flag) return o.ref.flag;
    return null;
  }

  setMode(m) {
    this.mode = m;
    this.roadStart = null; this.roadPlan = null;
    this.ghost.setVisible(false);
    this.pv.clear();
    if (this.hud) this.hud.refresh();
  }

  tap(p) {
    const w = this.world, t = this.tileAt(p), m = this.mode;
    if (m === 'settle') {
      const o = w.originFor('hall', t.i, t.j);
      const area = { i: w.startTile.i, j: w.startTile.j, r: 14 };
      if (!w.canBuild('hall', o.bi, o.bj, area)) { this.fail('여기에는 마을회관을 세울 수 없어요 (마차 가까운 빈 땅을 골라 주세요)'); return; }
      const hall = w.placeBuilding('hall', o.bi, o.bj, { free: true });
      this.people.settle(hall);
      Assets.play(this, 'sfx_build');
      this.people.news('🔨 모두 함께 마을회관을 짓기 시작했어요!', 'info');
      this.setMode('view');
      return;
    }
    if (m === 'road') {
      const f = this.flagFromTile(t.i, t.j);
      if (!this.roadStart) {
        if (f) { this.roadStart = f; this.previewRoad(p); return; }
        if (w.placeFlag(t.i, t.j)) { Assets.play(this, 'sfx_click', 0.6); return; }
        this.fail('먼저 깃발(또는 건물)을 눌러서 길의 시작점을 정해 주세요');
        return;
      }
      if (f === this.roadStart) { this.roadStart = null; this.pv.clear(); return; }
      this.previewRoad(p);
      this.commitRoad();
      return;
    }
    if (m === 'flag') {
      if (w.placeFlag(t.i, t.j)) Assets.play(this, 'sfx_click', 0.6);
      else this.fail('여기에는 깃발을 꽂을 수 없어요 (다른 깃발과 한 칸 띄워 주세요)');
      return;
    }
    if (m.startsWith('build:')) {
      const type = m.slice(6);
      const o = w.originFor(type, t.i, t.j);
      if (!w.hall || w.hall.state !== 'active') { this.fail('마을회관이 완성된 뒤에 지을 수 있어요'); return; }
      if (!w.canBuild(type, o.bi, o.bj)) { this.fail('여기에는 지을 수 없어요 (나무·바위·길이 없는 빈 땅이 필요해요)'); return; }
      const b = w.placeBuilding(type, o.bi, o.bj);
      Assets.play(this, 'sfx_build', 0.7);
      this.hud.toast(`${b.def.name} 공사 자리를 정했어요. 깃발에서 길을 이어 주세요!`);
      this.setMode('road');
      this.roadStart = b.flag;
      return;
    }
    if (m === 'remove') {
      const o = w.map.occAt(t.i, t.j);
      if (!o) return;
      if (o.type === 'flag') { if (o.ref.bld && o.ref.bld.def.kind === 'hq') { this.fail('마을회관은 없앨 수 없어요'); return; } w.removeFlag(o.ref); }
      else if (o.type === 'road') w.removeRoad(o.ref);
      else if (o.type === 'bld') { if (!w.removeBuilding(o.ref)) { this.fail('마을회관은 없앨 수 없어요'); return; } }
      else return;
      Assets.play(this, 'sfx_drop', 0.7);
      return;
    }
    // 보기: 사람 → 건물 → 깃발
    const person = this.personAt(p.worldX, p.worldY);
    if (person) { this.hud.showPerson(person); return; }
    const o = w.map.occAt(t.i, t.j);
    if (o && o.type === 'bld') { this.hud.showBuilding(o.ref); return; }
    if (o && o.type === 'flag') { if (o.ref.bld) this.hud.showBuilding(o.ref.bld); else this.hud.showFlag(o.ref); return; }
    if (o && o.type === 'plot' && o.ref) { this.hud.showBuilding(o.ref.b); return; }
    this.hud.closeCard();
  }

  personAt(x, y) {
    let best = null, bd = 46;
    for (const p of this.people.list) {
      if (p.dead || p.hidden) continue;
      const d = Math.hypot(p.x - x, (p.y - 40) - y);
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  fail(msg) { Assets.play(this, 'sfx_error', 0.5); this.hud.toast(msg, true); }

  previewRoad(p) {
    if (!this.roadStart) return;
    const t = this.tileAt(p);
    this.roadPlan = this.world.planRoad(this.roadStart, t.i, t.j);
  }

  commitRoad() {
    const plan = this.roadPlan;
    this.roadPlan = null;
    if (!plan || !plan.path) return;
    if (!plan.ok) { this.fail('길을 여기까지 낼 수 없어요'); return; }
    const made = this.world.buildRoad(plan.path, true);
    if (!made) { this.fail('길을 여기까지 낼 수 없어요'); return; }
    Assets.play(this, 'sfx_click', 0.8);
    const end = plan.path[plan.path.length - 1];
    this.roadStart = this.world.flagAt(end[0], end[1]);   // 이어서 그리기
  }

  drawPreview() {
    const g = this.pv, w = this.world;
    g.clear();
    this.ghost.setVisible(false);
    const m = this.mode;
    const dia = (i, j, col, a = 0.45, grow = -0.06) => { g.fillStyle(col, a); g.fillPoints(w.iso.diamond(i, j, grow), true); };
    if (m === 'road' || m === 'flag') {
      if (this.roadStart) {
        const f = this.roadStart;
        g.lineStyle(4, 0xffe066, 1); g.strokeEllipse(f.x, f.y, 70, 34);
      }
      if (this.roadPlan && this.roadPlan.path) {
        const col = this.roadPlan.ok ? 0x6fd36f : 0xe25b4f;
        for (const [i, j] of this.roadPlan.path) dia(i, j, col, 0.5, -0.18);
      } else if (this.hover && !this.roadStart) {
        const t = this.tileAt(this.hover);
        dia(t.i, t.j, w.canFlag(t.i, t.j) ? 0x6fd36f : 0xe25b4f, 0.35);
      }
      // 짐꾼 없는 길 표시
      for (const r of w.roads) if (!r.carrier) { const mp = r.pts[r.pts.length >> 1]; g.fillStyle(0xff6b5a, 0.9); g.fillCircle(mp.x, mp.y - 6, 6); }
    }
    let type = null, area = null;
    if (m === 'settle') { type = 'hall'; area = { i: w.startTile.i, j: w.startTile.j, r: 14 }; }
    if (m.startsWith('build:')) type = m.slice(6);
    if (type && this.hover) {
      const t = this.tileAt(this.hover);
      const o = w.originFor(type, t.i, t.j);
      const ok = w.canBuild(type, o.bi, o.bj, area);
      const { s, fi, fj } = w.footprint(type, o.bi, o.bj);
      for (let j = o.bj; j < o.bj + s; j++) for (let i = o.bi; i < o.bi + s; i++) dia(i, j, ok ? 0x6fd36f : 0xe25b4f, 0.4);
      dia(fi, fj, 0xffe066, 0.55);
      const def = BUILDINGS[type];
      const sp = def.levels ? def.levels[0].sprite : def.sprite;
      const [k, f, ax, ay] = Assets.tex(this, sp[0], sp[1]);
      const c = w.W(o.bi + (s - 1) / 2, o.bj + (s - 1) / 2);
      this.ghost.setTexture(k, f).setOrigin(ax, ay).setPosition(c.x, c.y).setVisible(true).setTint(ok ? 0xffffff : 0xff9a9a);
    }
    if (m === 'settle' && area) {
      const c = w.W(area.i, area.j);
      g.lineStyle(4, 0xffffff, 0.7); g.strokeEllipse(c.x, c.y, area.r * 2 * 96, area.r * 96);
    }
  }

  // ---------------------------------------------------------------- 매 프레임
  update(time, delta) {
    const real = Math.min(delta, 60) / 1000;
    const dt = real * this.speed;
    const k = this.keys, cam = this.cameras.main, pan = 900 * real / cam.zoom * this.dpr;
    if (k.A.isDown || k.LEFT.isDown) cam.scrollX -= pan;
    if (k.D.isDown || k.RIGHT.isDown) cam.scrollX += pan;
    if (k.W.isDown || k.UP.isDown) cam.scrollY -= pan;
    if (k.S.isDown || k.DOWN.isDown) cam.scrollY += pan;
    if (k.Q.isDown || k.MINUS.isDown) this.zoomBy(1 - real * 1.5);
    if (k.E.isDown || k.PLUS.isDown) this.zoomBy(1 + real * 1.5);

    this.anims.globalTimeScale = Math.max(0.0001, this.speed);
    this.tweens.timeScale = Math.max(0.0001, this.speed);
    if (dt > 0) {
      if (!this.perf) this.clock.update(dt);
      this.world.update(dt, this.clock.phase === PHASE.DAY);
      this.people.update(dt);
    }
    // 땅
    const v = cam.worldView;
    this.ground.setPosition(v.x - 2, v.y - 2);
    if (Math.abs(this.ground.width - v.width - 4) > 1 || Math.abs(this.ground.height - v.height - 4) > 1) this.ground.setSize(v.width + 4, v.height + 4);
    this.ground.tilePositionX = v.x - 2; this.ground.tilePositionY = v.y - 2;
    const tint = this.clock.season.tint;
    if (this.ground.tintTopLeft !== tint) this.ground.setTint(tint);

    if ((this.frameN++ & 3) === 0) this.cullAll(false);
    this.drawPreview();
    this.hud.tick(real);
  }

  // ---------------------------------------------------------------- 자동 시험용
  installHooks() {
    const self = this;
    window.__SM.play = this;
    window.__SM.api = {
      stats() {
        const w = self.world;
        return {
          fps: Math.round(self.game.loop.actualFps), people: self.people.list.filter((p) => !p.dead).length, items: w.items.length,
          roads: w.roads.length, flags: w.flags.length, blds: w.blds.map((b) => `${b.type}:${b.state}`), stock: Object.assign({}, w.stock),
          day: self.clock.day, phase: self.clock.phase, mode: self.mode, breadMade: w.stats.breadMade,
          jobs: self.people.list.filter((p) => p.job).length,
          jobKinds: self.people.list.reduce((a, p) => { const k = p.job ? p.job.kind : 'none'; a[k] = (a[k] || 0) + 1; return a; }, {}),
          fullFlags: w.flags.filter((f) => f.items.length >= 8).length, carried: w.items.filter((i) => i.carrier && i.carrier !== 'tween').length,
        };
      },
      settle(i, j) { self.mode = 'settle'; const o = self.world.originFor('hall', i, j); const h = self.world.placeBuilding('hall', o.bi, o.bj, { free: true }); self.people.settle(h); self.setMode('view'); return !!h; },
      build(type, i, j) { const o = self.world.originFor(type, i, j); if (!self.world.canBuild(type, o.bi, o.bj)) return null; const b = self.world.placeBuilding(type, o.bi, o.bj); return b && b.flag ? [b.flag.i, b.flag.j] : null; },
      road(i1, j1, i2, j2) { const f = self.world.flagAt(i1, j1); if (!f) return false; const pl = self.world.planRoad(f, i2, j2); if (!pl.ok) return false; return !!self.world.buildRoad(pl.path, true); },
      speed(s) { self.speed = s; },
      skipTo(frac) { self.clock.t = frac; },
      hall() { const h = self.world.hall; return h ? { i: h.flag.i, j: h.flag.j, state: h.state } : null; },
      start() { return self.world.startTile; },
      finishBuild() { for (const b of self.world.blds) if (b.con) { b.con.have = Object.assign({}, b.con.need); b.con.work = b.con.workNeeded; self.world.finishCon(b); } },
      zoom(z) { self.applyZoom(z); },
      findSpot(type, ni, nj) {
        const w = self.world;
        for (let r = 0; r < 14; r++) for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
          if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
          const o = w.originFor(type, ni + di, nj + dj);
          if (w.canBuild(type, o.bi, o.bj)) return [ni + di, nj + dj];
        }
        return null;
      },
      connect(i1, j1) {
        const w = self.world; const f = w.flagAt(i1, j1); const h = w.hall; if (!f || !h) return false;
        const targets = w.flags.filter((g) => g !== f && (g === h.flag || w.dist(g, h.flag) < Infinity)).sort((a, b) => Math.hypot(a.i - f.i, a.j - f.j) - Math.hypot(b.i - f.i, b.j - f.j));
        for (const g of targets.slice(0, 8)) { const pl = w.planRoad(f, g.i, g.j); if (pl.ok && w.buildRoad(pl.path, true)) return true; }
        return false;
      },
      people() { return self.people.list.filter((p) => !p.dead).map((p) => ({ n: p.name, job: p.job ? p.job.kind + (p.job.bld ? ':' + p.job.bld.type : '') : '-', e: +p.energy.toFixed(2), m: +p.mood.toFixed(2), hid: p.hidden, home: p.home ? p.home.type : null, partner: p.partner ? p.partner.name : null })); },
      offer(yes) { if (!self.people.offer) return false; self.hud.modalEl.style.display = 'none'; self.people.answerOffer(yes); return true; },
      news() { return self.people.log.slice(0, 12).map((x) => x.text); },
      center(i, j) { const p = self.world.W(i, j); self.centerOn(p.x, p.y); },
    };
  }
}
