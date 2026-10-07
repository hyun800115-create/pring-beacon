// 무대: three.js 화면, 빛(해·하늘), 땅, 안개, 카메라와 조작(이동·회전·확대).
//  마우스: 왼쪽 끌기 = 이동(도구가 없을 때), 가운데(휠) 누르고 끌기 = 360° 회전·기울이기, 오른쪽 끌기 = 회전, 휠 = 확대·축소
//  터치: 한 손가락 = 이동, 두 손가락 = 벌려 확대 + 비틀어 회전 + 위아래로 기울이기
//  키보드: WASD/화살표 이동, Q/E 회전, R/F 확대·축소

import * as THREE from 'three';

const DEG = Math.PI / 180;

export class Stage {
  constructor(parent, opts = {}) {
    this.size = opts.size || 140;
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.maxDpr = Math.min(2, window.devicePixelRatio || 1);
    r.setPixelRatio(this.maxDpr);
    r.setSize(window.innerWidth, window.innerHeight);
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.NeutralToneMapping;
    r.toneMappingExposure = 1.05;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.localClippingEnabled = true;
    parent.appendChild(r.domElement);
    this.canvas = r.domElement;

    const sc = this.scene = new THREE.Scene();
    this.skyCol = new THREE.Color(0xdfe9f5);
    sc.background = this.skyCol.clone();
    sc.fog = new THREE.Fog(this.skyCol, 120, 320);

    this.cam = new THREE.PerspectiveCamera(32, window.innerWidth / window.innerHeight, 0.3, 900);
    this.rig = { tx: this.size / 2, tz: this.size / 2, yaw: 45 * DEG, pitch: 38 * DEG, dist: 34 };
    this.goal = Object.assign({}, this.rig);

    this.hemi = new THREE.HemisphereLight(0xe8efff, 0xa9b3c6, 1.75);
    sc.add(this.hemi);
    const sun = this.sun = new THREE.DirectionalLight(0xfff1dc, 2.5);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.03;
    sc.add(sun, sun.target);

    // 땅: 눈 무늬 반복
    this.groundMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.96, metalness: 0 });
    const g = this.ground = new THREE.Mesh(new THREE.PlaneGeometry(this.size * 3, this.size * 3), this.groundMat);
    g.rotation.x = -Math.PI / 2;
    g.position.set(this.size / 2, 0, this.size / 2);
    g.receiveShadow = true;
    g.name = 'ground';
    sc.add(g);
    new THREE.TextureLoader().load(opts.groundTex || 'assets/ground/ground_snow.png', (t) => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.repeat.set(this.size * 3 / 7, this.size * 3 / 7);
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 8;
      this.groundMat.map = t; this.groundMat.needsUpdate = true;
    });
    // 지도 가장자리 표시
    const edge = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0.03, 0), new THREE.Vector3(this.size, 0.03, 0), new THREE.Vector3(this.size, 0.03, this.size), new THREE.Vector3(0, 0.03, this.size)]),
    new THREE.LineBasicMaterial({ color: 0x9fb3cc, transparent: true, opacity: 0.7 }));
    sc.add(edge);

    this.ray = new THREE.Raycaster();
    this.plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    this.handlers = {};
    this.keys = {};
    this.pointers = new Map();
    this.setupInput();
    window.addEventListener('resize', () => this.resize());
    this.applyCamera(true);
  }

  on(ev, fn) { this.handlers[ev] = fn; }
  emit(ev, ...a) { const f = this.handlers[ev]; return f ? f(...a) : undefined; }

  resize() {
    const w = window.innerWidth, h = window.innerHeight;
    this.renderer.setSize(w, h);
    this.cam.aspect = w / h;
    this.cam.updateProjectionMatrix();
  }

  // ---------------------------------------------------------------- 카메라
  applyCamera(snap) {
    const g = this.goal, r = this.rig;
    const k = snap ? 1 : 0.22;
    g.pitch = Math.max(18 * DEG, Math.min(82 * DEG, g.pitch));
    g.dist = Math.max(5, Math.min(170, g.dist));
    g.tx = Math.max(-10, Math.min(this.size + 10, g.tx));
    g.tz = Math.max(-10, Math.min(this.size + 10, g.tz));
    for (const key of ['tx', 'tz', 'pitch', 'dist']) r[key] += (g[key] - r[key]) * k;
    let dy = g.yaw - r.yaw;
    r.yaw += dy * k;
    const cp = Math.cos(r.pitch), sp = Math.sin(r.pitch);
    this.cam.position.set(r.tx + Math.sin(r.yaw) * cp * r.dist, sp * r.dist, r.tz + Math.cos(r.yaw) * cp * r.dist);
    this.cam.lookAt(r.tx, 0, r.tz);
    // 해 그림자 범위를 보는 곳에 맞춘다
    const s = Math.max(14, r.dist * 0.9);
    const sh = this.sun.shadow.camera;
    if (Math.abs(sh.right - s) > 0.5) { sh.left = -s; sh.right = s; sh.top = s; sh.bottom = -s; sh.near = 1; sh.far = 260; sh.updateProjectionMatrix(); }
    this.sun.target.position.set(r.tx, 0, r.tz);
    this.sun.position.set(r.tx + this.sunDir.x * 90, this.sunDir.y * 90, r.tz + this.sunDir.z * 90);
  }
  get sunDir() { return this._sunDir || (this._sunDir = new THREE.Vector3(-0.5, 0.8, 0.35).normalize()); }

  /** 화면에 보일 만큼 가까운가 (효과·소리 줄이기용) */
  isNear(x, z) { const r = this.rig; return Math.abs(x - r.tx) < r.dist * 1.2 && Math.abs(z - r.tz) < r.dist * 1.2; }
  centerOn(x, z, dist) { this.goal.tx = x; this.goal.tz = z; if (dist) this.goal.dist = dist; }
  rotateBy(dyaw, dpitch = 0) { this.goal.yaw += dyaw; this.goal.pitch += dpitch; }
  zoomBy(f, sx, sy) {
    const before = sx != null ? this.groundAt(sx, sy) : null;
    this.goal.dist *= f;
    if (before) {   // 마우스 쪽으로 다가가기
      const t = 1 - f;
      this.goal.tx += (before.x - this.goal.tx) * t * 0.9;
      this.goal.tz += (before.z - this.goal.tz) * t * 0.9;
    }
  }
  /** 손가락(마우스)이 dx, dy 픽셀 움직였을 때 땅이 손을 따라오게 */
  panScreen(dx, dy) {
    const yaw = this.rig.yaw;
    const s = this.rig.dist * 1.15 / Math.max(500, window.innerHeight);
    const k = s / Math.max(0.4, Math.sin(this.rig.pitch));
    const rx = Math.cos(yaw), rz = -Math.sin(yaw);       // 화면 오른쪽 (땅 위)
    const fx = -Math.sin(yaw), fz = -Math.cos(yaw);      // 화면 안쪽 (땅 위)
    this.goal.tx += -rx * dx * s + fx * dy * k;
    this.goal.tz += -rz * dx * s + fz * dy * k;
  }

  /** 화면 좌표(CSS px) → 땅 위 점 */
  groundAt(sx, sy) {
    const v = new THREE.Vector2((sx / window.innerWidth) * 2 - 1, -(sy / window.innerHeight) * 2 + 1);
    this.ray.setFromCamera(v, this.cam);
    const p = new THREE.Vector3();
    return this.ray.ray.intersectPlane(this.plane, p) ? p : null;
  }
  /** 화면 좌표 → 물체 고르기 */
  pick(sx, sy, objs) {
    const v = new THREE.Vector2((sx / window.innerWidth) * 2 - 1, -(sy / window.innerHeight) * 2 + 1);
    this.ray.setFromCamera(v, this.cam);
    return this.ray.intersectObjects(objs, true);
  }
  /** 3D 점 → 화면 좌표 */
  toScreen(x, y, z) {
    const v = new THREE.Vector3(x, y, z).project(this.cam);
    return { x: (v.x + 1) / 2 * window.innerWidth, y: (1 - v.y) / 2 * window.innerHeight, vis: v.z < 1 && v.z > -1 };
  }

  // ---------------------------------------------------------------- 입력
  setupInput() {
    const c = this.canvas;
    c.style.touchAction = 'none';
    c.addEventListener('contextmenu', (e) => e.preventDefault());
    c.addEventListener('pointerdown', (e) => this.down(e));
    window.addEventListener('pointermove', (e) => this.move(e));
    window.addEventListener('pointerup', (e) => this.up(e));
    window.addEventListener('pointercancel', (e) => this.up(e));
    c.addEventListener('wheel', (e) => { e.preventDefault(); this.zoomBy(e.deltaY > 0 ? 1.12 : 0.89, e.clientX, e.clientY); }, { passive: false });
    window.addEventListener('keydown', (e) => { if (e.target.tagName === 'INPUT') return; this.keys[e.code] = true; this.emit('key', e); });
    window.addEventListener('keyup', (e) => { this.keys[e.code] = false; });
    window.addEventListener('blur', () => { this.keys = {}; });
  }

  down(e) {
    this.canvas.setPointerCapture?.(e.pointerId);
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now(), btn: e.button, type: e.pointerType });
    if (this.pointers.size === 2) {
      const [a, b] = [...this.pointers.values()];
      this.gesture = { d: Math.hypot(a.x - b.x, a.y - b.y), ang: Math.atan2(b.y - a.y, b.x - a.x), my: (a.y + b.y) / 2 };
      if (this.drag && this.drag.tool) this.emit('dragCancel');
      this.drag = null;
      return;
    }
    const mode = e.button === 1 || e.button === 2 ? 'rotate' : 'left';
    this.drag = { mode, x: e.clientX, y: e.clientY, moved: false, tool: false };
    if (mode === 'left') this.drag.tool = !!this.emit('dragStart', e.clientX, e.clientY, e);
  }

  move(e) {
    const p = this.pointers.get(e.pointerId);
    if (!p) { this.emit('hover', e.clientX, e.clientY, e); return; }
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (this.pointers.size >= 2 && this.gesture) {
      const [a, b] = [...this.pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y), ang = Math.atan2(b.y - a.y, b.x - a.x), my = (a.y + b.y) / 2;
      this.goal.dist *= this.gesture.d / Math.max(1, d);
      let da = ang - this.gesture.ang;
      if (da > Math.PI) da -= Math.PI * 2; if (da < -Math.PI) da += Math.PI * 2;
      this.goal.yaw -= da;
      this.goal.pitch += (my - this.gesture.my) * 0.004;
      this.gesture = { d, ang, my };
      return;
    }
    const d = this.drag;
    if (!d) return;
    if (!d.moved && Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > 6) d.moved = true;
    if (!d.moved) return;
    if (d.mode === 'rotate') { this.goal.yaw -= dx * 0.008; this.goal.pitch += dy * 0.006; return; }
    if (d.tool) { this.emit('dragMove', e.clientX, e.clientY, e); return; }
    this.panScreen(dx, dy);
  }

  up(e) {
    const p = this.pointers.get(e.pointerId);
    this.pointers.delete(e.pointerId);
    if (this.pointers.size < 2) this.gesture = null;
    const d = this.drag;
    if (!p || !d) { if (!this.pointers.size) this.drag = null; return; }
    if (this.pointers.size === 0) this.drag = null;
    if (d.tool && d.moved) { this.emit('dragEnd', e.clientX, e.clientY, e); return; }
    if (d.tool && !d.moved) this.emit('dragCancel');
    if (!d.moved && performance.now() - p.t < 600) this.emit('tap', e.clientX, e.clientY, e);
  }

  // ---------------------------------------------------------------- 매 프레임
  update(dt) {
    const k = this.keys;
    let px = 0, py = 0;
    if (k.KeyA || k.ArrowLeft) px -= 1; if (k.KeyD || k.ArrowRight) px += 1;
    if (k.KeyW || k.ArrowUp) py -= 1; if (k.KeyS || k.ArrowDown) py += 1;
    if (px || py) { const K = 700 * dt; this.panScreen(-px * K, -py * K); }
    if (k.KeyQ) this.goal.yaw += dt * 1.6;
    if (k.KeyE) this.goal.yaw -= dt * 1.6;
    if (k.KeyR) this.goal.dist *= 1 - dt * 1.2;
    if (k.KeyF) this.goal.dist *= 1 + dt * 1.2;
    this.applyCamera(false);
  }

  render() { this.renderer.render(this.scene, this.cam); }

  /** 시간에 따른 하늘·해 (t: 하루 비율 0~1, 0.0 = 새벽 6시) */
  setTime(t, seasonTint) {
    const ang = (t / 0.76) * Math.PI;           // 낮 동안 동쪽→서쪽
    const day = t < 0.76;
    const h = day ? Math.sin(ang) : 0.25;
    this._sunDir = new THREE.Vector3(Math.cos(ang) * 0.8, Math.max(0.18, h), 0.45).normalize();
    const key = [
      [0.00, 0xffd2c0, 1.2, 0xf0d8d0, 1.2], [0.07, 0xfff1dc, 2.5, 0xdfe9f5, 1.75], [0.55, 0xfff1dc, 2.5, 0xdfe9f5, 1.75],
      [0.66, 0xffb070, 1.8, 0xf4c9a8, 1.3], [0.76, 0x6a78c8, 0.45, 0x2e3a66, 0.55], [0.94, 0x6a78c8, 0.4, 0x27325c, 0.5], [1.0, 0xffd2c0, 1.2, 0xf0d8d0, 1.2],
    ];
    let a = key[0], b = key[1];
    for (let i = 0; i < key.length - 1; i++) if (t >= key[i][0] && t <= key[i + 1][0]) { a = key[i]; b = key[i + 1]; break; }
    const u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]);
    const sunC = new THREE.Color(a[1]).lerp(new THREE.Color(b[1]), u);
    const skyC = new THREE.Color(a[3]).lerp(new THREE.Color(b[3]), u);
    this.sun.color.copy(sunC);
    this.sun.intensity = a[2] + (b[2] - a[2]) * u;
    this.hemi.intensity = a[4] + (b[4] - a[4]) * u;
    this.hemi.color.copy(skyC).lerp(new THREE.Color(0xffffff), 0.4);
    this.scene.background.copy(skyC);
    this.scene.fog.color.copy(skyC);
    if (seasonTint != null) this.groundMat.color.setHex(seasonTint);
    this.night = day ? Math.max(0, (t - 0.62) / 0.14) : 1;
    if (t < 0.06) this.night = 1 - t / 0.06;
    this.night = Math.max(0, Math.min(1, this.night));
  }
}
