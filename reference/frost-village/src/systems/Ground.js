// Static ground: scrolling sea + fish schools (live tileSprites) and the snowy land baked once
// into a few canvas textures (snow pattern, shoreline foam, paths, decals). Zone floors are
// separate baked images so locked zones can fade in when they unlock.

import { Assets } from '../core/Assets.js';
import { WORLD } from '../data/world.js';
import { DEPTH } from './DepthSort.js';
import { shoreY } from './Collision.js';
import { isoRect } from '../core/Iso.js';
import { rng } from '../core/Placeholders.js';

const CHUNK = 1024;

function pattern(ctx, key, scale = 1) {
  const s = Assets.source(key);
  const p = ctx.createPattern(s.img, 'repeat');
  if (p && p.setTransform && scale !== 1 && typeof DOMMatrix !== 'undefined') p.setTransform(new DOMMatrix().scale(scale));
  return p;
}

function drawFrame(ctx, key, x, y, scale = 1, rot = 0, alpha = 1) {
  const s = Assets.source(key);
  const f = s.frame;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, y);
  if (rot) ctx.rotate(rot);
  ctx.scale(scale, scale);
  const w = f.cutWidth, h = f.cutHeight;
  ctx.drawImage(s.img, f.cutX, f.cutY, w, h, -w / 2, -h / 2, w, h);
  ctx.restore();
}

export class Ground {
  constructor(gs) {
    this.gs = gs;
    const W = WORLD.width, H = WORLD.height;
    this.W = W; this.H = H;
    let maxShore = 0;
    for (let x = 0; x <= W; x += 8) maxShore = Math.max(maxShore, shoreY(x));
    this.maxShore = maxShore;

    // --- sea (live, scrolling)
    const seaH = Math.ceil(maxShore + 40);
    this.sea = gs.add.tileSprite(0, -200, W, seaH + 200, Assets.sprite('water_sea').tex).setOrigin(0, 0).setDepth(DEPTH.WATER);
    this.fish1 = null; this.fish2 = null;
    const fs = Assets.sprite('fish_school');
    this.fish1 = gs.add.tileSprite(0, 40, W, 200, fs.tex, fs.frame).setOrigin(0, 0).setDepth(DEPTH.FISH).setAlpha(0.55);
    this.fish2 = gs.add.tileSprite(0, 150, W, 200, fs.tex, fs.frame).setOrigin(0, 0).setDepth(DEPTH.FISH).setAlpha(0.35).setTilePosition(130, 40);
    this.fish2.setTileScale(0.8, 0.8);
    this.t = 0;

    // --- baked land
    this.chunks = [];
    for (let y0 = 0; y0 < H; y0 += CHUNK) {
      const h = Math.min(CHUNK, H - y0);
      const key = 'fv_ground_' + y0;
      if (gs.textures.exists(key)) gs.textures.remove(key);
      const ct = gs.textures.createCanvas(key, W, h);
      this.bakeChunk(ct.context, y0, W, h);
      ct.refresh();
      this.chunks.push(gs.add.image(0, y0, key).setOrigin(0, 0).setDepth(DEPTH.GROUND));
    }
  }

  bakeChunk(ctx, y0, W, h) {
    ctx.save();
    ctx.translate(0, -y0);
    const H = this.H;
    // land polygon below the shoreline
    const land = () => {
      ctx.beginPath();
      ctx.moveTo(0, shoreY(0));
      for (let x = 0; x <= W; x += 8) ctx.lineTo(x, shoreY(x));
      ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
    };
    // shallow turquoise water hugging the shoreline (over the live sea, fading out to sea)
    if (y0 < this.maxShore + 20) {
      if (!this.shallow) this.shallow = this.makeShallow(W);
      ctx.drawImage(this.shallow, 0, 0);
    }
    // snow
    ctx.fillStyle = pattern(ctx, 'ground_snow') || '#eef3f9';
    land(); ctx.fill();
    // soft blue shading toward the south & edges (gives depth)
    const vg = ctx.createLinearGradient(0, 0, W, 0);
    vg.addColorStop(0, 'rgba(120,150,200,0.10)'); vg.addColorStop(0.12, 'rgba(120,150,200,0)');
    vg.addColorStop(0.88, 'rgba(120,150,200,0)'); vg.addColorStop(1, 'rgba(120,150,200,0.10)');
    ctx.fillStyle = vg; land(); ctx.fill();

    if (y0 < this.maxShore + 80) this.bakeShore(ctx, W);
    this.bakePaths(ctx);
    this.bakeDecals(ctx, y0, h);
    ctx.restore();
  }

  makeShallow(W) {
    const h = Math.ceil(this.maxShore + 30);
    const c = document.createElement('canvas');
    c.width = W; c.height = h;
    const g = c.getContext('2d');
    g.fillStyle = pattern(g, 'water_shallow') || 'rgba(120,200,230,1)';
    g.fillRect(0, 0, W, h);
    // keep a band ~130 px tall above the wavy shoreline, alpha ramping toward the beach.
    // (build the mask separately: destination-in clears everything outside each drawn shape)
    const m = document.createElement('canvas');
    m.width = W; m.height = h;
    const mg = m.getContext('2d');
    const band = 130;
    for (let x = 0; x < W; x += 6) {
      const sy = shoreY(x + 3);
      const gr = mg.createLinearGradient(0, sy - band, 0, sy + 6);
      gr.addColorStop(0, 'rgba(0,0,0,0)');
      gr.addColorStop(0.55, 'rgba(0,0,0,0.35)');
      gr.addColorStop(1, 'rgba(0,0,0,0.85)');
      mg.fillStyle = gr;
      mg.fillRect(x, sy - band, 6, band + 6);
    }
    g.globalCompositeOperation = 'destination-in';
    g.drawImage(m, 0, 0);
    g.globalCompositeOperation = 'source-over';
    return c;
  }

  bakeShore(ctx, W) {
    // icy rim + wet edge
    ctx.save();
    ctx.lineJoin = 'round';
    const line = (off) => { ctx.beginPath(); for (let x = -8; x <= W + 8; x += 8) { const y = shoreY(x) + off; if (x < 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); } };
    ctx.strokeStyle = 'rgba(201,214,232,0.9)'; ctx.lineWidth = 12; line(6); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 7; line(1); ctx.stroke();
    ctx.strokeStyle = 'rgba(156,199,230,0.55)'; ctx.lineWidth = 5; line(-6); ctx.stroke();
    ctx.restore();
    // foam strip segments along the curve (texture: water above, land below; lip at anchor y)
    const foam = Assets.source('shore_foam');
    const f = foam.frame;
    const lip = (foam.def && foam.def.anchor ? foam.def.anchor[1] : 0.6) * f.cutHeight;
    const seg = 32;
    let sx = 0;
    for (let x = -seg; x < W + seg; x += seg) {
      const y1 = shoreY(x), y2 = shoreY(x + seg);
      const ang = Math.atan2(y2 - y1, seg);
      ctx.save();
      ctx.translate(x, y1 + 4);
      ctx.rotate(ang);
      const u = ((sx % f.cutWidth) + f.cutWidth) % f.cutWidth;
      const sw = Math.min(seg + 1, f.cutWidth - u);
      ctx.drawImage(foam.img, f.cutX + u, f.cutY, sw, f.cutHeight, 0, -lip, sw + 0.6, f.cutHeight);
      ctx.restore();
      sx += seg;
    }
  }

  bakePaths(ctx) {
    ctx.save();
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    // all paths as one shape (so junctions are not darker), stroked far off-canvas: only its blurred
    // shadow lands on the snow. Soft feathered edges everywhere (shadowBlur works in every browser).
    const OFF = 30000;
    const allPaths = () => {
      ctx.beginPath();
      for (const pts of WORLD.paths) pts.forEach((p, i) => (i ? ctx.lineTo(p[0] - OFF, p[1]) : ctx.moveTo(p[0] - OFF, p[1])));
    };
    const soft = (w, color, blur) => {
      ctx.save();
      ctx.shadowColor = color; ctx.shadowBlur = blur; ctx.shadowOffsetX = OFF; ctx.shadowOffsetY = 0;
      ctx.strokeStyle = '#000'; ctx.lineWidth = w;
      allPaths(); ctx.stroke();
      ctx.restore();
    };
    soft(80, 'rgba(136,160,198,0.36)', 26);   // packed, slightly blue-grey trodden snow
    soft(34, 'rgba(150,138,130,0.26)', 14);   // a hint of earth showing through in the middle
    // drift texture breaking up the edges
    const r1 = rng(11);
    if (Assets.has('decal_snow_drift_a')) {
      for (const pts of WORLD.paths) {
        for (let i = 0; i < pts.length - 1; i++) {
          const [ax, ay] = pts[i], [bx, by] = pts[i + 1];
          const len = Math.hypot(bx - ax, by - ay), ang = Math.atan2(by - ay, bx - ax);
          for (let d = 90; d < len - 60; d += 230 + r1() * 140) {
            const t = d / len, side = (r1() < 0.5 ? -1 : 1) * (34 + r1() * 10);
            const x = ax + (bx - ax) * t - Math.sin(ang) * side, y = ay + (by - ay) * t + Math.cos(ang) * side;
            drawFrame(ctx, r1() < 0.5 ? 'decal_snow_drift_a' : 'decal_snow_drift_b', x, y, 0.42 + r1() * 0.2, 0, 0.55);
          }
        }
      }
    }
    // footprints stamped along the paths (decal runs along the A axis = 26.6 deg)
    const hasFoot = Assets.has('decal_footprints');
    const r2 = rng(5);
    const A = Math.atan2(22.63, 45.25);
    for (const pts of WORLD.paths) {
      for (let i = 0; i < pts.length - 1; i++) {
        const [ax, ay] = pts[i], [bx, by] = pts[i + 1];
        const len = Math.hypot(bx - ax, by - ay), ang = Math.atan2(by - ay, bx - ax);
        if (hasFoot) {
          for (let d = 60; d < len - 40; d += 150 + r2() * 80) {
            const t = d / len, side = (r2() - 0.5) * 24;
            const x = ax + (bx - ax) * t - Math.sin(ang) * side, y = ay + (by - ay) * t + Math.cos(ang) * side;
            drawFrame(ctx, 'decal_footprints', x, y, 0.42, ang - A + (r2() < 0.5 ? Math.PI : 0), 0.45);
          }
        } else {
          ctx.fillStyle = 'rgba(150,170,205,0.28)';
          for (let d = 10; d < len; d += 26) {
            if (r2() < 0.35) continue;
            const t = d / len, side = (Math.floor(d / 26) % 2 ? 1 : -1) * 7;
            const x = ax + (bx - ax) * t - Math.sin(ang) * side, y = ay + (by - ay) * t + Math.cos(ang) * side;
            ctx.beginPath(); ctx.ellipse(x, y, 5, 3, ang, 0, Math.PI * 2); ctx.fill();
          }
        }
      }
    }
    ctx.restore();
  }

  bakeDecals(ctx, y0, h) {
    for (const d of WORLD.decals) {
      const [key, x, y, sc = 1, rot = 0] = d;
      if (y < y0 - 300 || y > y0 + h + 300) continue;
      drawFrame(ctx, key, x, y, sc, (rot * Math.PI) / 180, 0.95);
    }
  }

  /** bake one zone floor (iso parallelogram) into its own image; returns the Image */
  zoneFloor(id, z) {
    const gs = this.gs;
    const [cx, cy] = z.center;
    const pts = isoRect(cx, cy, z.size[0], z.size[1]);
    const pad = 24;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of pts) { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y); }
    x0 = Math.floor(x0 - pad); y0 = Math.floor(y0 - pad); x1 = Math.ceil(x1 + pad); y1 = Math.ceil(y1 + pad);
    const key = 'fv_floor_' + id;
    if (gs.textures.exists(key)) gs.textures.remove(key);
    const ct = gs.textures.createCanvas(key, x1 - x0, y1 - y0);
    const ctx = ct.context;
    ctx.translate(-x0, -y0);
    const poly = (inset = 0) => {
      ctx.beginPath();
      // inset toward the centre
      pts.forEach((p, i) => {
        const x = p.x + (cx - p.x) * inset, y = p.y + (cy - p.y) * inset;
        if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      });
      ctx.closePath();
    };
    // soft snow-bank shadow around the floor
    ctx.save();
    ctx.shadowColor = 'rgba(90,110,150,0.35)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
    ctx.fillStyle = 'rgba(0,0,0,1)';
    poly(); ctx.fill();
    ctx.restore();
    ctx.globalCompositeOperation = 'source-over';
    ctx.save();
    poly(); ctx.clip();
    ctx.fillStyle = pattern(ctx, z.floor) || '#d9a08a';
    ctx.globalAlpha = 1;
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    if (z.floorAlpha !== undefined && z.floorAlpha < 1) {
      // blend toward snow for soft floors (forest, hunting ground)
      ctx.globalAlpha = 1 - z.floorAlpha;
      ctx.fillStyle = pattern(ctx, 'ground_snow') || '#eef3f9';
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      ctx.globalAlpha = 1;
    }
    // inner bevel / edge darkening
    ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(80,50,40,0.18)'; ctx.lineWidth = 14; poly(); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 3; poly(0.012); ctx.stroke();
    ctx.restore();
    // remove the black used for the shadow inside: redraw done above covers it; outside keep only shadow
    // snow lip on the border
    ctx.strokeStyle = 'rgba(244,247,251,0.9)'; ctx.lineWidth = 5; poly(); ctx.stroke();
    ct.refresh();
    return gs.add.image(x0, y0, key).setOrigin(0, 0).setDepth(DEPTH.FLOOR);
  }

  update(dt) {
    this.t += dt;
    this.sea.tilePositionX = this.t * 6;
    this.sea.tilePositionY = Math.sin(this.t * 0.4) * 6;
    if (this.fish1) { this.fish1.tilePositionX = this.t * 22; this.fish1.tilePositionY = Math.sin(this.t * 0.7) * 5; }
    if (this.fish2) { this.fish2.tilePositionX = 130 + this.t * 14; }
  }
}
