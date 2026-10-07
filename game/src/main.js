// 봄날의 행진 (3D) — 시작점: 불러오기, 게임 모드(정착·보기·건축·길·없애기), 입력 연결, 매 프레임 진행.

import * as THREE from 'three';
import { Stage } from './render/stage.js';
import { Library } from './render/models.js';
import { World } from './game/world.js';
import { People } from './game/people.js';
import { Clock, PHASE } from './game/clock.js';
import { BUILDINGS, ITEMS, LOOKS, WORK_LOOKS, NUM, ROADS, ROAD_ORDER, BUILD_MENU } from './game/defs.js';
import { Hud, costText } from './ui/hud.js';
import { Bubbles } from './ui/bubbles.js';
import { Audio } from './core/audio.js';
import { makeWindmillModel, makeWell } from './game/buildings.js';

const loadTxt = (t) => { const e = document.getElementById('sm-loading-txt'); if (e) e.textContent = t; };

class Game {
  async boot() {
    const q = new URLSearchParams(location.search);
    this.perf = q.get('perf') === '1';
    this.showFps = q.get('debug') === '1' || this.perf;
    this.stage = new Stage(document.getElementById('game'), { size: NUM.mapSize });
    this.lib = new Library();
    await this.lib.init();
    // 캐릭터와 소품 미리 불러오기
    const chars = [...new Set([...LOOKS.m, ...LOOKS.f, ...LOOKS.oldM, ...LOOKS.oldF, ...LOOKS.kidM, ...LOOKS.kidF, ...WORK_LOOKS])];
    const props = new Set(['trade_post', 'crop_wheat_0', 'crop_wheat_1', 'crop_wheat_2', 'crop_wheat_3', 'lantern_string', 'picnic_table']);
    for (const t of Object.values(ITEMS)) if (t.model) props.add(t.model);
    for (const d of Object.values(BUILDINGS)) {
      const fbs = [d.fallback, ...(d.levels || []).map((l) => l.fallback)];
      for (const fb of fbs) if (Array.isArray(fb)) for (const f of fb) props.add(f[0]);
    }
    let done = 0;
    const total = chars.length + props.size + 1;
    const tick = () => loadTxt(`불러오는 중… ${Math.round((++done / total) * 100)}%`);
    await Promise.all([...chars.map((k) => this.lib.loadChar(k).then(tick)), ...[...props].map((k) => this.lib.loadProp(k).then(tick))]);
    for (const k of Object.keys(this.lib.index.buildings)) await this.lib.loadBuilding(k);
    tick();

    this.world = new World(this.stage, this.lib);
    this.world.initFx();
    this.audio = new Audio(this.stage);
    this.world.audio = this.audio;
    await this.world.loadNature();
    this.clock = new Clock();
    this.bub = new Bubbles(this.stage);
    this.people = new People(this.world, this.clock, this.bub);
    this.speed = 1;
    this.mode = 'view';
    this.placeRot = 0;
    this.hud = new Hud(this);
    this.world.on('news', (t, k) => this.hud.news(t, k));
    this.world.on('offer', (o) => this.hud.offer(o));
    this.world.on('built', (b, kind) => this.onBuilt(b, kind));
    this.world.on('removed', (b) => this.people.buildingGone(b));

    if (this.perf) await this.setupPerf();
    else await this.setupStart();
    this.setupInput();
    this.makeThumbs();
    const ld = document.getElementById('sm-loading');
    if (ld) { ld.classList.add('hide'); setTimeout(() => ld.remove(), 400); }
    this.last = performance.now(); this.fps = 60;
    this.installHooks();
    this.loop();
  }

  // ---------------------------------------------------------------- 시작
  async setupStart() {
    const S = NUM.mapSize;
    const start = { x: S * 0.45, z: S * 0.5 };
    this.world.generate(start);
    const wg = this.lib.prop('trade_post');
    wg.position.set(start.x, 0, start.z); wg.rotation.y = 0.5;
    this.stage.scene.add(wg);
    this.world.wagon = { x: start.x, z: start.z, obj: wg, door: { x: start.x, z: start.z + 2 } };
    this.people.startCaravan(start.x, start.z);
    this.stage.centerOn(start.x, start.z + 2, 30);
    this.stage.applyCamera(true);
    this.setMode('settle');
  }

  async onBuilt(b, kind) {
    const w = this.world;
    this.audio.play('complete', 0.8, b.x, b.z);
    if (b.type === 'hall' && w.wagon) {
      this.people.unloadWagon(b, w.wagon);
      const wg = w.wagon;
      setTimeout(() => { this.stage.scene.remove(wg.obj); w.wagon = null; }, 12000);
      this.people.news('🏛️ 마을회관이 완성됐어요! 이제 길을 그리고 건물을 지어 보세요', 'party');
      this.hud.cat = 'house'; this.hud.fillTools(); this.hud.refresh();
    } else if (b.def.kind === 'house') { this.people.assignHomes(); this.people.news(`🏠 ${b.name}이(가) ${kind === 'upgrade' ? '업그레이드' : '완성'}됐어요`, 'info'); }
    else this.people.news(`✅ ${b.name}이(가) 완성됐어요`, 'info');
  }

  // ---------------------------------------------------------------- 성능 시험
  async setupPerf() {
    const S = NUM.mapSize, w = this.world;
    w.generate({ x: S / 2, z: S / 2 });
    // 격자 길
    for (let i = 0; i < 6; i++) {
      const a = 20 + i * 20;
      w.roads.addPath([{ x: 15, z: a }, { x: S - 15, z: a }], i % 2 ? 'stone' : 'dirt');
      w.roads.addPath([{ x: a, z: 15 }, { x: a, z: S - 15 }], 'gravel');
    }
    for (let k = 0; k < 300; k++) {
      const p = this.people.makePerson({ x: 15 + Math.random() * (S - 30), z: 15 + Math.random() * (S - 30) });
      p.perfWalker = true;
    }
    this.clock.t = 0.25;
    this.stage.centerOn(S / 2, S / 2, 70);
  }

  // ---------------------------------------------------------------- 모드
  setMode(m) {
    this.mode = m;
    this.roadPts = null;
    if (this.ghost) { this.stage.scene.remove(this.ghost); this.ghost = null; }
    if (this.roadPrev) { this.stage.scene.remove(this.roadPrev); this.roadPrev = null; }
    const type = m === 'settle' ? 'hall' : m.startsWith('build:') ? m.slice(6) : null;
    if (type) this.makeGhost(type);
    this.hud.refresh();
  }

  async makeGhost(type) {
    const def = BUILDINGS[type];
    const g = new THREE.Group();
    const [w, d] = def.size;
    const foot = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ color: 0x6fd36f, transparent: true, opacity: 0.35, depthWrite: false }));
    foot.rotation.x = -Math.PI / 2; foot.position.y = 0.05; g.add(foot);
    const arrow = new THREE.Mesh(new THREE.ConeGeometry(0.45, 1.0, 3), new THREE.MeshBasicMaterial({ color: 0xffd23f }));
    arrow.rotation.x = Math.PI / 2; arrow.position.set(0, 0.15, d / 2 + 0.9); g.add(arrow);
    const key = def.levels ? def.levels[0].key : type;
    const real = this.lib.building(key);
    let model;
    if (real) model = real.scene;
    else {
      model = new THREE.Group();
      const fb = def.levels ? def.levels[0].fallback : def.fallback;
      if (Array.isArray(fb)) for (const [k, lx, lz, deg, sc] of fb) { await this.lib.loadProp(k); const o = this.lib.prop(k); o.position.set(lx, 0, lz); o.rotation.y = (deg || 0) * Math.PI / 180; o.scale.setScalar(sc || 1); model.add(o); }
      else { const box = new THREE.Mesh(new THREE.BoxGeometry(w * 0.8, def.height * 0.8, d * 0.8), new THREE.MeshStandardMaterial({ color: 0xeadfca })); box.position.y = def.height * 0.4; model.add(box); }
    }
    model.traverse((o) => { if (o.isMesh) { const mats = Array.isArray(o.material) ? o.material : [o.material]; const nm = mats.map((m) => { const c = m.clone(); c.transparent = true; c.opacity = 0.6; c.depthWrite = false; return c; }); o.material = Array.isArray(o.material) ? nm : nm[0]; o.castShadow = false; } });
    g.add(model);
    g.userData = { foot, type };
    g.visible = false;
    if (this.mode === (type === 'hall' ? 'settle' : 'build:' + type)) { this.ghost = g; this.stage.scene.add(g); }
  }

  rotatePlacing(d) { this.placeRot += d; this.updateGhost(); }

  updateGhost(sx, sy) {
    const g = this.ghost; if (!g) return;
    if (sx != null) this.ghostScreen = { x: sx, y: sy };
    if (!this.ghostScreen) return;
    const p = this.stage.groundAt(this.ghostScreen.x, this.ghostScreen.y);
    if (!p) return;
    const type = g.userData.type;
    const snapX = Math.round(p.x * 2) / 2, snapZ = Math.round(p.z * 2) / 2;
    g.position.set(snapX, 0, snapZ); g.rotation.y = this.placeRot; g.visible = true;
    const area = this.mode === 'settle' ? { x: this.world.wagon.x, z: this.world.wagon.z, r: 22 } : null;
    const res = this.world.check(type, snapX, snapZ, this.placeRot, area);
    g.userData.foot.material.color.setHex(res.ok ? 0x6fd36f : 0xe25b4f);
    g.userData.ok = res; g.userData.at = { x: snapX, z: snapZ };
  }

  // ---------------------------------------------------------------- 입력
  setupInput() {
    const st = this.stage;
    st.on('hover', (x, y) => { this.hoverAt = { x, y }; if (this.ghost) this.updateGhost(x, y); });
    st.on('tap', (x, y) => this.tap(x, y));
    st.on('dragStart', (x, y) => {
      if (this.mode !== 'road') return false;
      const p = st.groundAt(x, y); if (!p) return false;
      this.roadPts = [{ x: p.x, z: p.z }];
      return true;
    });
    st.on('dragMove', (x, y) => {
      if (!this.roadPts) return;
      const p = st.groundAt(x, y); if (!p) return;
      const l = this.roadPts[this.roadPts.length - 1];
      if (Math.hypot(p.x - l.x, p.z - l.z) > 0.6) { this.roadPts.push({ x: p.x, z: p.z }); this.drawRoadPreview(); }
    });
    st.on('dragEnd', () => this.finishRoad());
    st.on('dragCancel', () => { this.roadPts = null; this.drawRoadPreview(); });
    st.on('key', (e) => {
      if (e.code === 'Escape') { this.setMode('view'); this.hud.closeCard(); }
      if (this.ghost && (e.code === 'KeyQ' || e.code === 'KeyE')) { this.rotatePlacing(e.code === 'KeyQ' ? Math.PI / 8 : -Math.PI / 8); }
    });
  }

  drawRoadPreview() {
    if (this.roadPrev) { this.stage.scene.remove(this.roadPrev); this.roadPrev = null; }
    if (!this.roadPts || this.roadPts.length < 2) return;
    const g = new THREE.BufferGeometry().setFromPoints(this.roadPts.map((p) => new THREE.Vector3(p.x, 0.12, p.z)));
    this.roadPrev = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xffd23f, linewidth: 3 }));
    this.stage.scene.add(this.roadPrev);
  }

  finishRoad() {
    const pts = this.roadPts; this.roadPts = null; this.drawRoadPreview();
    if (!pts || pts.length < 2) return;
    const w = this.world;
    const blocked = (x, z) => w.blds.some((b) => !b.dead && b.contains(x, z, -0.2));
    const made = w.roads.addPath(pts, 'dirt', blocked);
    if (made === null) { this.fail('건물을 지나가는 길은 낼 수 없어요'); return; }
    if (!made.length) { this.fail('길이 너무 짧아요'); return; }
    // 길 위의 덤불·그루터기 치우기
    for (const e of made) for (const p of e.pts) w.natureNear(p.x, p.z, 1.3, (o) => { if (o.type === 'bush' || o.type === 'stump' || o.type === 'tree') w.removeNature(o); });
    this.audio.play('click', 0.8);
  }

  fail(msg) { this.audio.play('error', 0.5); this.hud.toast(msg, true); }

  async tap(sx, sy) {
    const st = this.stage, w = this.world, m = this.mode;
    if (this.ghost) {
      this.updateGhost(sx, sy);
      const r = this.ghost.userData.ok, at = this.ghost.userData.at;
      if (!r || !r.ok) { this.fail(r ? r.why : '여기에는 지을 수 없어요'); return; }
      const type = this.ghost.userData.type;
      if (m === 'settle') {
        this.setMode('view');
        const hall = await w.place('hall', at.x, at.z, this.placeRot, { free: true });
        this.people.settle(hall);
        this.audio.play('build', 0.9);
        this.people.news('🔨 모두 함께 마을회관을 짓기 시작했어요!', 'info');
        return;
      }
      await w.place(type, at.x, at.z, this.placeRot);
      this.audio.play('build', 0.7, at.x, at.z);
      this.hud.toast(`${BUILDINGS[type].name} 공사 자리를 정했어요. 길을 이어 주면 더 빨리 날라요!`);
      return;
    }
    const gp = st.groundAt(sx, sy);
    if (m === 'remove') {
      const b = this.pickBuilding(sx, sy);
      if (b) { if (b.def.kind === 'hq') { this.fail('마을회관은 없앨 수 없어요'); return; } w.remove(b); this.audio.play('drop', 0.7); return; }
      const e = gp && w.roads.pick(gp.x, gp.z);
      if (e) { w.roads.removeEdge(e); this.audio.play('drop', 0.7); }
      return;
    }
    if (m === 'road') return;
    // 보기: 사람 → 건물 → 길
    const person = this.pickPerson(sx, sy);
    if (person) { this.hud.showPerson(person); return; }
    const b = this.pickBuilding(sx, sy);
    if (b) { this.hud.showBuilding(b); return; }
    const e = gp && w.roads.pick(gp.x, gp.z);
    if (e) { this.hud.showRoad(e); return; }
    this.hud.closeCard();
  }

  pickPerson(sx, sy) {
    let best = null, bd = 34;
    for (const p of this.people.list) {
      if (p.dead || p.hidden) continue;
      const s = this.stage.toScreen(p.x, p.y + 0.7, p.z);
      if (!s.vis) continue;
      const d = Math.hypot(s.x - sx, s.y - sy);
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }
  pickBuilding(sx, sy) {
    const hits = this.stage.pick(sx, sy, this.world.blds.map((b) => b.group));
    for (const h of hits) { let o = h.object; while (o && !o.userData.bld) o = o.parent; if (o && o.userData.bld && !o.userData.bld.dead) return o.userData.bld; }
    const gp = this.stage.groundAt(sx, sy);
    return gp ? this.world.blds.find((b) => !b.dead && b.contains(gp.x, gp.z, 0.3)) : null;
  }

  /** 카드 버튼 */
  act(a, sel) {
    const w = this.world;
    if (a === 'follow') { this.follow = this.follow === sel ? null : sel; if (this.follow) this.stage.goal.dist = Math.min(this.stage.goal.dist, 18); }
    if (a === 'inside') { sel.pinned = !sel.pinned; sel.setCutaway(sel.pinned); }
    if (a === 'upgrade') { if (w.upgrade(sel)) { this.hud.toast(`${sel.def.levels[sel.level + 1].name}로 업그레이드를 시작해요`); this.audio.play('build', 0.6, sel.x, sel.z); } }
    if (a === 'remove') { if (sel.def) { w.remove(sel); this.hud.closeCard(); } }
    if (a === 'roadrm') { w.roads.removeEdge(sel); this.hud.closeCard(); }
    if (a === 'roadup') this.upgradeRoad(sel);
    this.hud.cardEl.__h = null;
  }

  /** 길 업그레이드: 재료를 쓰고, 주민 한 명이 길을 따라가며 망치질하면 바뀐다 */
  upgradeRoad(e) {
    const w = this.world, i = ROAD_ORDER.indexOf(e.type), next = ROAD_ORDER[i + 1];
    if (!next || e.busy) return;
    const nr = ROADS[next], n = Math.max(1, Math.ceil(e.len / nr.per));
    for (const [k, v] of Object.entries(nr.cost)) if ((w.stock[k] || 0) < v * n) { this.fail(`${ITEMS[k].name}이(가) ${v * n}개 필요해요 (창고 ${Math.floor(w.stock[k] || 0)}개)`); return; }
    const pp = this.people;
    const p = pp.list.filter((q) => !q.dead && q.stage === 'adult' && !q.job && !q.event && !q.hidden).sort((a, b) => Math.hypot(a.x - e.pts[0].x, a.z - e.pts[0].z) - Math.hypot(b.x - e.pts[0].x, b.z - e.pts[0].z))[0];
    if (!p) { this.fail('쉬고 있는 주민이 없어요. 조금 뒤에 다시 해 주세요'); return; }
    for (const [k, v] of Object.entries(nr.cost)) w.stock[k] -= v * n;
    e.busy = true;
    pp.clearQ(p); if (p.slot) pp.leaveSlot(p);
    p.job = { kind: 'road', x: e.pts[0].x, z: e.pts[0].z };
    pp.walkTo(p, e.pts[0].x, e.pts[0].z);
    pp.doit(p, () => pp.setLook(p, 'miner'));
    for (let k = 0; k < e.pts.length; k += 3) {
      const pt = e.pts[k];
      pp.walkTo(p, pt.x + 0.6, pt.z, 0.7);
      pp.wait(p, 0.9, 'work', Math.atan2(-0.6, 0));
      pp.doit(p, () => { w.chips(pt.x, 0.2, pt.z, 0x9aa3ad, 3); this.audio.play('mine', 0.25, pt.x, pt.z); });
    }
    pp.doit(p, () => { w.roads.setType(e, next); e.busy = false; pp.setLook(p, p.look); p.job = null; pp.say(p, 'brave'); this.people.news(`🛤️ ${nr.name}이(가) 깔렸어요`, 'info'); });
    this.hud.toast(`${p.name}이(가) ${nr.name}을(를) 깔러 가요`);
  }

  // ---------------------------------------------------------------- 매 프레임
  loop() {
    requestAnimationFrame(() => this.loop());
    const now = performance.now();
    const raw = (now - this.last) / 1000;
    const real = Math.min(0.25, raw);      // 화면이 느려도 게임 시간은 제대로 흐르게 (잘게 나눠 계산)
    this.last = now;
    this.fps += (1 / Math.max(1e-3, raw) - this.fps) * 0.05;
    const dt = real * this.speed;
    const st = this.stage, w = this.world;
    if (this.follow && !this.follow.dead) { st.goal.tx = this.follow.x; st.goal.tz = this.follow.z; }
    st.update(real);
    const steps = Math.max(1, Math.ceil(dt / 0.06));
    for (let k = 0; k < steps && dt > 0; k++) {
      const h = dt / steps;
      if (!this.perf) this.clock.update(h);
      this.updateBuildings(h);
      w.regrow(h); w.growTrees(h);
      if (this.perf) this.perfTick();
      this.people.update(h, st.rig);
    }
    w.updateFx(Math.min(real, 0.06));
    st.setTime(this.clock.frac, this.clock.season.tint);
    this.updateHover();
    this.bub.update(real);
    this.hud.tick(real);
    st.render();
    // 느리면 화면 해상도 낮추기
    this.perfT = (this.perfT || 0) + real;
    if (this.perfT > 3) { this.perfT = 0; const r = st.renderer.getPixelRatio(); if (this.fps < 32 && r > 1) st.renderer.setPixelRatio(Math.max(1, r - 0.25)); else if (this.fps > 55 && r < st.maxDpr) st.renderer.setPixelRatio(Math.min(st.maxDpr, r + 0.25)); }
  }

  updateBuildings(dt) {
    const w = this.world, day = this.clock.phase === PHASE.DAY;
    for (const b of w.blds) {
      b.update(dt, this.stage.night);
      if (b.state !== 'active' || b.dead) continue;
      const def = b.def;
      if (def.kind === 'farm') for (const p of b.plots) if (p.stage < 3) { p.t += dt; const s = Math.min(3, Math.floor(p.t / (def.grow / 3))); if (s !== p.stage) w.setPlotStage(p, s); }
      if (def.kind === 'process') {
        const here = b.worker && b.worker.atWork && day;
        if (b.working) {
          if (here) b.t += dt * (b.worker.workRate || 1);
          if (b.t >= def.time) { b.working = false; b.out += def.outN || 1; if (def.out === 'bread') w.stats.breadMade += def.outN || 1; b.updateOutPile(); }
        } else if (here && b.inputs > 0 && b.out < NUM.outputCap) {
          b.inputs--; b.working = true; b.t = 0;
          if (def.sfx) this.audio.play(def.sfx, 0.35, b.x, b.z);
        }
      }
    }
  }

  perfTick() {
    for (const p of this.people.list) if (p.perfWalker && !p.cur && !p.q.length) {
      const S = NUM.mapSize;
      this.people.walkTo(p, 15 + Math.random() * (S - 30), 15 + Math.random() * (S - 30));
    }
  }

  /** 건물 위에 마우스를 올리면 실내 보기 */
  updateHover() {
    this.hoverT = (this.hoverT || 0) + 1;
    if (this.hoverT % 6) return;
    let hb = null;
    if (this.hoverAt && this.mode === 'view' && !this.stage.pointers.size) hb = this.pickBuilding(this.hoverAt.x, this.hoverAt.y);
    for (const b of this.world.blds) if (b.hasInterior) b.setCutaway(b.pinned || b === hb);
  }

  // ---------------------------------------------------------------- 메뉴 그림 (건물 미리보기)
  async makeThumbs() {
    const r = this.stage.renderer;
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xb0b8c8, 2.0));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(-3, 6, 5); scene.add(sun);
    const cam = new THREE.PerspectiveCamera(28, 1, 0.1, 200);
    const rt = new THREE.WebGLRenderTarget(128, 128);
    const buf = new Uint8Array(128 * 128 * 4);
    const types = Object.values(BUILD_MENU).flat();
    for (const type of types) {
      const def = BUILDINGS[type];
      const key = def.levels ? def.levels[0].key : type;
      const g = new THREE.Group();
      const real = this.lib.building(key);
      if (real) g.add(real.scene);
      else {
        const fb = def.levels ? def.levels[0].fallback : def.fallback;
        if (Array.isArray(fb)) for (const [k, lx, lz, deg, sc] of fb) { await this.lib.loadProp(k); const o = this.lib.prop(k); o.position.set(lx, 0, lz); o.rotation.y = (deg || 0) * Math.PI / 180; o.scale.setScalar(sc || 1); g.add(o); }
        else if (fb === 'windmill') g.add(makeWindmillModel().g);
        else if (fb === 'well') g.add(makeWell());
      }
      scene.add(g);
      const box = new THREE.Box3().setFromObject(g), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3()).length();
      cam.position.set(c.x + s * 0.9, c.y + s * 0.75, c.z + s * 1.05); cam.lookAt(c);
      r.setRenderTarget(rt); r.setClearColor(0x000000, 0); r.clear(); r.render(scene, cam);
      r.readRenderTargetPixels(rt, 0, 0, 128, 128, buf);
      r.setRenderTarget(null);
      scene.remove(g);
      const cv = document.createElement('canvas'); cv.width = cv.height = 128;
      const ctx = cv.getContext('2d'), img = ctx.createImageData(128, 128);
      for (let y = 0; y < 128; y++) img.data.set(buf.subarray((127 - y) * 512, (128 - y) * 512), y * 512);
      ctx.putImageData(img, 0, 0);
      this.hud.thumbs[type] = cv.toDataURL();
    }
    r.setClearColor(0x000000, 1);
    this.hud.fillTools(); this.hud.refresh();
  }

  // ---------------------------------------------------------------- 자동 시험용
  installHooks() {
    const self = this;
    window.__SM = {
      game: this,
      api: {
        stats() {
          const w = self.world;
          return {
            fps: Math.round(self.fps), people: self.people.list.filter((p) => !p.dead).length, tasks: w.tasks.length,
            roads: w.roads.edges.size, blds: w.blds.map((b) => `${b.type}:${b.state}${b.con ? ':' + Math.round(b.con.work / b.con.workNeeded * 100) : ''}`),
            stock: Object.assign({}, w.stock), day: self.clock.day, phase: self.clock.phase, mode: self.mode, breadMade: w.stats.breadMade,
            jobs: self.people.list.reduce((a, p) => { const k = p.job ? p.job.kind : 'none'; a[k] = (a[k] || 0) + 1; return a; }, {}),
            draws: self.stage.renderer.info.render.calls, tris: self.stage.renderer.info.render.triangles,
          };
        },
        start() { return self.world.start; },
        async settle(x, z, rot = 0) { self.setMode('view'); const h = await self.world.place('hall', x, z, rot, { free: true }); self.people.settle(h); return true; },
        hall() { const h = self.world.hall; return h ? { x: h.x, z: h.z, state: h.state, door: h.door } : null; },
        async build(type, x, z, rot = 0) { const r = self.world.check(type, x, z, rot); if (!r.ok) return r.why; const b = await self.world.place(type, x, z, rot); return { door: b.door }; },
        findSpot(type, x, z, rot = 0) {
          for (let rr = 0; rr < 30; rr += 1) for (let k = 0; k < 16; k++) { const a = k / 16 * Math.PI * 2; const px = x + Math.cos(a) * rr, pz = z + Math.sin(a) * rr; if (self.world.check(type, px, pz, rot).ok) return [px, pz]; }
          return null;
        },
        road(pts, type = 'dirt') { const m = self.world.roads.addPath(pts.map(([x, z]) => ({ x, z })), type); return m ? m.length : -1; },
        speed(s) { self.speed = s; },
        skipTo(t) { self.clock.t = t; },
        cam(x, z, dist, yaw, pitch) { const g = self.stage.goal; g.tx = x; g.tz = z; if (dist) g.dist = dist; if (yaw != null) g.yaw = yaw; if (pitch != null) g.pitch = pitch; self.stage.applyCamera(true); },
        offer(yes) { if (!self.people.offer) return false; self.hud.modalEl.style.display = 'none'; self.people.answerOffer(yes); return true; },
        news() { return self.people.log.slice(0, 15).map((x) => x.text); },
        people() { return self.people.list.filter((p) => !p.dead).map((p) => ({ n: p.name, job: p.job ? p.job.kind + (p.job.bld ? ':' + p.job.bld.type : '') : '-', e: +p.energy.toFixed(2), m: +p.mood.toFixed(2), hid: p.hidden, slot: p.slot ? p.slot.s.action : null, home: p.home ? p.home.type : null })); },
        cutaway(type, on) { for (const b of self.world.blds) if (b.type === type) { b.pinned = on; b.setCutaway(on); } },
      },
    };
  }
}

const game = new Game();
game.boot().catch((e) => { console.error(e); if (window.__smShowError) window.__smShowError('게임을 시작하지 못했어요.', String(e && e.message || e)); });
