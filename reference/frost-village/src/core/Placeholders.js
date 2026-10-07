// Generated fallback textures. Used whenever a manifest key is missing so the game
// always stays playable (and reasonably pretty) without the real art.

const ITEM_COLORS = {
  item_fish_raw: ['#9fb8cc', '#5f7f9c'], item_fish_cooked: ['#f08a5d', '#c0603a'], item_log: ['#8a5a33', '#6e4428'],
  item_plank: ['#e2b57c', '#c98f55'], item_wheat: ['#e8c25a', '#b8902e'], item_bread: ['#c9853f', '#9b6128'],
  item_ore: ['#7e7f86', '#d9822b'], item_ingot: ['#c8d2e0', '#8e96a3'], item_meat_raw: ['#c8463d', '#f3e6d8'],
  item_meat_cooked: ['#8a4a2a', '#f3e6d8'], item_coin: ['#f2c14e', '#c9952a'],
};

const CHAR_COLORS = {
  player: '#f2f0ea', fisherman: '#f2c230', lumberjack: '#d9483b', farmer: '#5c9e4a', miner: '#e0812b', hunter: '#8a5a33',
  villager_a: '#f2c230', villager_b: '#d9483b', villager_c: '#3d7cc9', deer: '#b9814f', boar: '#6e4a3a',
};

function rr(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }

function diamond(ctx, cx, cy, hw, hh) {
  ctx.beginPath(); ctx.moveTo(cx - hw, cy); ctx.lineTo(cx, cy - hh); ctx.lineTo(cx + hw, cy); ctx.lineTo(cx, cy + hh); ctx.closePath();
}

function star(ctx, cx, cy, r1, r2, n = 5) {
  ctx.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const r = i % 2 ? r2 : r1, a = -Math.PI / 2 + (i * Math.PI) / n;
    const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
    if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  }
  ctx.closePath();
}

function heart(ctx, cx, cy, s) {
  ctx.beginPath();
  ctx.moveTo(cx, cy + s * 0.9);
  ctx.bezierCurveTo(cx - s * 1.4, cy - s * 0.1, cx - s * 0.6, cy - s * 1.1, cx, cy - s * 0.35);
  ctx.bezierCurveTo(cx + s * 0.6, cy - s * 1.1, cx + s * 1.4, cy - s * 0.1, cx, cy + s * 0.9);
  ctx.closePath();
}

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  if (f < 0) { r *= 1 + f; g *= 1 + f; b *= 1 + f; } else { r += (255 - r) * f; g += (255 - g) * f; b += (255 - b) * f; }
  return 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (b | 0) + ')';
}

export const Placeholders = {
  /** create a canvas texture; returns the CanvasTexture */
  canvas(textures, key, w, h, draw) {
    if (textures.exists(key)) return textures.get(key);
    const ct = textures.createCanvas(key, w, h);
    const ctx = ct.context;
    ctx.clearRect(0, 0, w, h);
    draw(ctx, w, h);
    ct.refresh();
    return ct;
  },

  /** sprite-like placeholder: returns { tex, anchor } */
  sprite(textures, key, def) {
    const tk = 'ph__' + key;
    def = def || {};
    const kind = def.kind || guessKind(key);
    let anchor = def.anchor || [0.5, 0.5];
    if (key.startsWith('item_')) {
      anchor = [0.5, 0.75];
      this.canvas(textures, tk, 64, 64, (ctx) => {
        const [c1, c2] = ITEM_COLORS[key] || ['#cccccc', '#888888'];
        ctx.fillStyle = 'rgba(0,0,0,0.0)';
        ctx.fillStyle = c2; rr(ctx, 8, 30, 48, 18, 9); ctx.fill();
        ctx.fillStyle = c1; rr(ctx, 8, 24, 48, 18, 9); ctx.fill();
        ctx.strokeStyle = 'rgba(40,30,20,0.55)'; ctx.lineWidth = 2; rr(ctx, 8, 24, 48, 24, 9); ctx.stroke();
      });
    } else if (key.startsWith('tree_')) {
      anchor = [0.5, 0.9];
      if (key === 'tree_stump') {
        anchor = [0.5, 0.7];
        this.canvas(textures, tk, 64, 48, (ctx) => {
          ctx.fillStyle = '#6e4428'; rr(ctx, 16, 14, 32, 22, 6); ctx.fill();
          ctx.fillStyle = '#e2b57c'; ctx.beginPath(); ctx.ellipse(32, 15, 16, 7, 0, 0, Math.PI * 2); ctx.fill();
        });
      } else {
        this.canvas(textures, tk, 120, 200, (ctx) => {
          ctx.fillStyle = '#6e4428'; ctx.fillRect(54, 150, 12, 34);
          for (let i = 0; i < 4; i++) {
            const y = 150 - i * 34, w = 52 - i * 9;
            ctx.fillStyle = i % 2 ? '#2e6b4f' : '#1f4d3a';
            ctx.beginPath(); ctx.moveTo(60 - w, y); ctx.lineTo(60, y - 58); ctx.lineTo(60 + w, y); ctx.closePath(); ctx.fill();
            ctx.fillStyle = '#f4f7fb'; ctx.beginPath(); ctx.moveTo(60 - w * 0.45, y - 32); ctx.lineTo(60, y - 58); ctx.lineTo(60 + w * 0.45, y - 32); ctx.closePath(); ctx.fill();
          }
        });
      }
    } else if (key.startsWith('fx_')) {
      this.fx(textures, tk, key);
      anchor = [0.5, 0.5];
    } else if (key.startsWith('ui_') || key.startsWith('portrait_')) {
      this.ui(textures, tk, key);
      anchor = def.anchor || (key.startsWith('ui_pad') ? [0.5, 0.5] : [0.5, 0.5]);
    } else if (key.startsWith('decal_') || key === 'fish_school' || key === 'shore_foam' || key.startsWith('ground_') || key.startsWith('water_')) {
      this.ground(textures, tk, key);
      anchor = [0.5, 0.5];
    } else if (key === 'projectile_arrow') {
      this.canvas(textures, tk, 64, 16, (ctx) => {
        ctx.fillStyle = '#8a5a33'; ctx.fillRect(6, 7, 46, 3);
        ctx.fillStyle = '#8e96a3'; ctx.beginPath(); ctx.moveTo(62, 8); ctx.lineTo(50, 2); ctx.lineTo(50, 14); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#f4f7fb'; ctx.fillRect(2, 3, 9, 4); ctx.fillRect(2, 10, 9, 4);
      });
      anchor = [0.5, 0.5];
    } else {
      // generic iso box prop
      const fp = def.footprint || [110, 55];
      const top = def.topPx || (kind === 'station' || kind === 'building' ? 110 : 50);
      const w = Math.ceil(fp[0] + 8), h = Math.ceil(top + fp[1] / 2 + 8);
      const ay = (top + 4) / h;
      anchor = [0.5, ay];
      const col = kind === 'station' ? '#b5654a' : kind === 'building' ? '#a8743f' : key.startsWith('rock') ? '#8e96a3' : key.startsWith('crop') ? '#8a5a33' : key.startsWith('snow') || key.startsWith('ice') ? '#e8eef6' : '#c98f55';
      this.canvas(textures, tk, w, h, (ctx) => {
        const cx = w / 2, cy = top + 4, hw = fp[0] / 2, hh = fp[1] / 2;
        const bh = Math.max(8, top - hh);
        // left face
        ctx.fillStyle = shade(col, -0.18);
        ctx.beginPath(); ctx.moveTo(cx - hw, cy - bh); ctx.lineTo(cx, cy + hh - bh); ctx.lineTo(cx, cy + hh); ctx.lineTo(cx - hw, cy); ctx.closePath(); ctx.fill();
        // right face
        ctx.fillStyle = shade(col, -0.32);
        ctx.beginPath(); ctx.moveTo(cx + hw, cy - bh); ctx.lineTo(cx, cy + hh - bh); ctx.lineTo(cx, cy + hh); ctx.lineTo(cx + hw, cy); ctx.closePath(); ctx.fill();
        // top
        ctx.fillStyle = key.startsWith('crop_wheat_3') ? '#e8c25a' : key.startsWith('crop_wheat_2') ? '#6aa84f' : shade(col, 0.15);
        diamond(ctx, cx, cy - bh, hw, hh); ctx.fill();
        ctx.strokeStyle = 'rgba(40,30,20,0.45)'; ctx.lineWidth = 2; diamond(ctx, cx, cy - bh, hw, hh); ctx.stroke();
      });
    }
    return { tex: tk, anchor };
  },

  fx(textures, tk, key) {
    const S = 32;
    this.canvas(textures, tk, S, S, (ctx) => {
      const c = S / 2;
      const glow = (col) => { const g = ctx.createRadialGradient(c, c, 0, c, c, c); g.addColorStop(0, col); g.addColorStop(1, 'rgba(255,255,255,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, S, S); };
      switch (key) {
        case 'fx_star': ctx.fillStyle = '#ffffff'; star(ctx, c, c, 14, 6); ctx.fill(); break;
        case 'fx_spark': ctx.fillStyle = '#ffffff'; star(ctx, c, c, 14, 3, 4); ctx.fill(); break;
        case 'fx_heart': ctx.fillStyle = '#ff6f91'; heart(ctx, c, c, 12); ctx.fill(); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; ctx.stroke(); break;
        case 'fx_ring': ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(c, c, 12, 0, Math.PI * 2); ctx.stroke(); break;
        case 'fx_coin': ctx.fillStyle = '#f2c14e'; ctx.beginPath(); ctx.arc(c, c, 12, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#c9952a'; ctx.lineWidth = 3; ctx.stroke(); break;
        case 'fx_flame': ctx.fillStyle = '#ff8a2a'; ctx.beginPath(); ctx.ellipse(c, c + 3, 8, 12, 0, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#ffd45a'; ctx.beginPath(); ctx.ellipse(c, c + 6, 4, 7, 0, 0, Math.PI * 2); ctx.fill(); break;
        case 'fx_chip_wood': ctx.fillStyle = '#ffffff'; ctx.fillRect(9, 12, 14, 8); break;
        case 'fx_chip_rock': ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.moveTo(8, 20); ctx.lineTo(14, 9); ctx.lineTo(24, 12); ctx.lineTo(22, 23); ctx.closePath(); ctx.fill(); break;
        case 'fx_snowflake': ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5; for (let i = 0; i < 3; i++) { const a = (i * Math.PI) / 3; ctx.beginPath(); ctx.moveTo(c - Math.cos(a) * 12, c - Math.sin(a) * 12); ctx.lineTo(c + Math.cos(a) * 12, c + Math.sin(a) * 12); ctx.stroke(); } break;
        case 'fx_droplet': ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(c, c + 3, 7, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.moveTo(c - 6, c + 1); ctx.lineTo(c, c - 11); ctx.lineTo(c + 6, c + 1); ctx.fill(); break;
        case 'fx_wheat_bit': ctx.fillStyle = '#e8c25a'; ctx.beginPath(); ctx.ellipse(c, c, 4, 9, 0.6, 0, Math.PI * 2); ctx.fill(); break;
        case 'fx_leaf': ctx.fillStyle = '#2e6b4f'; ctx.beginPath(); ctx.ellipse(c, c, 5, 11, 0.8, 0, Math.PI * 2); ctx.fill(); break;
        case 'fx_smoke': case 'fx_dust': glow('rgba(255,255,255,0.85)'); break;
        default: glow('rgba(255,255,255,1)');
      }
    });
  },

  ground(textures, tk, key) {
    const r = rng(hashStr(key));
    if (key.startsWith('ground_') || key.startsWith('water_')) {
      const S = 256;
      const base = {
        ground_snow: '#eef3f9', ground_plaza: '#d9a08a', ground_dirt: '#b99a7c', ground_farm: '#9b7350',
        ground_rock: '#a3a9b3', water_sea: '#2f86c9', water_shallow: '#5aa6d8',
      }[key] || '#dddddd';
      this.canvas(textures, tk, S, S, (ctx) => {
        ctx.fillStyle = base; ctx.fillRect(0, 0, S, S);
        if (key === 'ground_plaza') {
          // wooden board floor (iso-ish planks)
          ctx.strokeStyle = 'rgba(150,90,70,0.35)'; ctx.lineWidth = 2;
          for (let i = -S; i < S * 2; i += 32) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i + S, S / 2); ctx.stroke(); ctx.beginPath(); ctx.moveTo(i, -S / 2); ctx.lineTo(i + S, 0); ctx.stroke(); }
        }
        if (key === 'ground_farm') {
          ctx.strokeStyle = 'rgba(70,45,25,0.35)'; ctx.lineWidth = 6;
          for (let i = -S; i < S * 2; i += 24) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i + S, S / 2); ctx.stroke(); }
        }
        const n = key.startsWith('water') ? 140 : 150;
        for (let i = 0; i < n; i++) {
          const x = r() * S, y = r() * S, s = 1 + r() * (key.startsWith('water') ? 10 : 4);
          const light = r() < 0.5;
          ctx.fillStyle = key.startsWith('water') ? (light ? 'rgba(255,255,255,0.06)' : 'rgba(10,40,90,0.08)') : (light ? 'rgba(255,255,255,0.12)' : 'rgba(60,70,100,0.035)');
          ctx.beginPath(); ctx.ellipse(x, y, s * 2, s, 0, 0, Math.PI * 2); ctx.fill();
          // wrap
          for (const [ox, oy] of [[S, 0], [-S, 0], [0, S], [0, -S]]) { ctx.beginPath(); ctx.ellipse(x + ox, y + oy, s * 2, s, 0, 0, Math.PI * 2); ctx.fill(); }
        }
      });
    } else if (key === 'shore_foam') {
      this.canvas(textures, tk, 256, 32, (ctx) => {
        for (let i = 0; i < 60; i++) { ctx.fillStyle = 'rgba(255,255,255,' + (0.4 + r() * 0.5) + ')'; const x = r() * 256; ctx.beginPath(); ctx.ellipse(x, 14 + r() * 6, 6 + r() * 14, 3 + r() * 3, 0, 0, Math.PI * 2); ctx.fill(); }
      });
    } else if (key === 'fish_school') {
      this.canvas(textures, tk, 256, 128, (ctx) => {
        ctx.fillStyle = 'rgba(12,40,80,0.35)';
        for (let i = 0; i < 9; i++) {
          const x = 20 + r() * 216, y = 16 + r() * 96;
          ctx.beginPath(); ctx.ellipse(x, y, 13, 5, -0.4, 0, Math.PI * 2); ctx.fill();
          ctx.beginPath(); ctx.moveTo(x - 11, y + 4); ctx.lineTo(x - 21, y + 2); ctx.lineTo(x - 17, y + 11); ctx.closePath(); ctx.fill();
        }
      });
    } else {
      // decals: soft blobs
      const col = key.includes('dirt') || key.includes('path') ? 'rgba(160,130,100,0.35)' : key.includes('puddle') ? 'rgba(156,199,230,0.6)' : key.includes('foot') ? 'rgba(150,170,200,0.4)' : 'rgba(255,255,255,0.7)';
      this.canvas(textures, tk, 192, 96, (ctx) => {
        if (key.includes('foot')) {
          ctx.fillStyle = col;
          for (let i = 0; i < 8; i++) { ctx.beginPath(); ctx.ellipse(20 + i * 20, 40 + (i % 2) * 14, 5, 3, 0.4, 0, Math.PI * 2); ctx.fill(); }
          return;
        }
        const g = ctx.createRadialGradient(96, 96, 4, 96, 96, 90);
        g.addColorStop(0, col); g.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = g; ctx.save(); ctx.scale(1, 0.5); ctx.beginPath(); ctx.arc(96, 96, 92, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      });
    }
  },

  ui(textures, tk, key) {
    const icon = (S, draw) => this.canvas(textures, tk, S, S, (ctx) => draw(ctx, S));
    const btn = (top, bot) => this.canvas(textures, tk, 96, 96, (ctx) => {
      ctx.fillStyle = 'rgba(0,0,0,0.18)'; rr(ctx, 4, 10, 88, 82, 24); ctx.fill();
      ctx.fillStyle = bot; rr(ctx, 4, 6, 88, 82, 24); ctx.fill();
      ctx.fillStyle = top; rr(ctx, 4, 4, 88, 74, 24); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.28)'; rr(ctx, 12, 10, 72, 22, 12); ctx.fill();
    });
    const pad = (fill, symbol) => this.canvas(textures, tk, 256, 128, (ctx) => {
      ctx.fillStyle = fill; diamond(ctx, 128, 64, 120, 60); ctx.fill();
      ctx.setLineDash([16, 10]); ctx.lineCap = 'round'; ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 6;
      diamond(ctx, 128, 64, 108, 54); ctx.stroke(); ctx.setLineDash([]);
      if (symbol) { ctx.save(); ctx.translate(128, 64); ctx.scale(1, 0.5); symbol(ctx); ctx.restore(); }
    });
    switch (key) {
      case 'ui_panel':
        this.canvas(textures, tk, 96, 96, (ctx) => {
          ctx.fillStyle = 'rgba(30,40,60,0.18)'; rr(ctx, 4, 8, 88, 84, 26); ctx.fill();
          ctx.fillStyle = '#fff8ec'; rr(ctx, 4, 4, 88, 84, 26); ctx.fill();
          ctx.strokeStyle = '#e6d6bd'; ctx.lineWidth = 3; rr(ctx, 5.5, 5.5, 85, 81, 24); ctx.stroke();
        }); break;
      case 'ui_button_blue': btn('#3d8be0', '#2a64a8'); break;
      case 'ui_button_green': btn('#5cc86a', '#3c9a49'); break;
      case 'ui_button_gray': btn('#aab3c0', '#7d8796'); break;
      case 'ui_coin_bar':
        this.canvas(textures, tk, 96, 56, (ctx) => { ctx.fillStyle = 'rgba(43,47,58,0.55)'; rr(ctx, 2, 2, 92, 52, 26); ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 2; rr(ctx, 3, 3, 90, 50, 25); ctx.stroke(); }); break;
      case 'ui_icon_coin': icon(64, (ctx) => {
        ctx.fillStyle = '#c9952a'; ctx.beginPath(); ctx.arc(32, 35, 26, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#f2c14e'; ctx.beginPath(); ctx.arc(32, 31, 26, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#ffe08a'; star(ctx, 32, 31, 13, 6); ctx.fill();
        ctx.strokeStyle = '#a8761c'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(32, 31, 25, 0, Math.PI * 2); ctx.stroke();
      }); break;
      case 'ui_icon_settings': icon(64, (ctx) => {
        ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#2b2f3a'; ctx.lineWidth = 3;
        ctx.beginPath(); for (let i = 0; i < 16; i++) { const a = (i * Math.PI) / 8, rad = i % 2 ? 22 : 27; ctx.lineTo(32 + Math.cos(a) * rad, 32 + Math.sin(a) * rad); } ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#3d8be0'; ctx.beginPath(); ctx.arc(32, 32, 9, 0, Math.PI * 2); ctx.fill();
      }); break;
      case 'ui_icon_sound_on': case 'ui_icon_sound_off': icon(64, (ctx) => {
        ctx.fillStyle = '#2b2f3a'; ctx.beginPath(); ctx.moveTo(10, 24); ctx.lineTo(22, 24); ctx.lineTo(36, 12); ctx.lineTo(36, 52); ctx.lineTo(22, 40); ctx.lineTo(10, 40); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#2b2f3a'; ctx.lineWidth = 4; ctx.lineCap = 'round';
        if (key.endsWith('on')) { ctx.beginPath(); ctx.arc(38, 32, 10, -0.9, 0.9); ctx.stroke(); ctx.beginPath(); ctx.arc(38, 32, 19, -0.9, 0.9); ctx.stroke(); }
        else { ctx.strokeStyle = '#d9483b'; ctx.beginPath(); ctx.moveTo(42, 22); ctx.lineTo(58, 42); ctx.moveTo(58, 22); ctx.lineTo(42, 42); ctx.stroke(); }
      }); break;
      case 'ui_icon_music_on': case 'ui_icon_music_off': icon(64, (ctx) => {
        ctx.fillStyle = '#2b2f3a'; ctx.strokeStyle = '#2b2f3a'; ctx.lineWidth = 5;
        ctx.beginPath(); ctx.ellipse(20, 46, 9, 7, -0.4, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.ellipse(46, 40, 9, 7, -0.4, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.moveTo(28, 45); ctx.lineTo(28, 14); ctx.lineTo(54, 8); ctx.lineTo(54, 39); ctx.stroke();
        if (key.endsWith('off')) { ctx.strokeStyle = '#d9483b'; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(8, 8); ctx.lineTo(56, 56); ctx.stroke(); }
      }); break;
      case 'ui_icon_lock': icon(64, (ctx) => {
        ctx.strokeStyle = '#5d6b80'; ctx.lineWidth = 7; ctx.beginPath(); ctx.arc(32, 26, 12, Math.PI, 0); ctx.stroke();
        ctx.fillStyle = '#ffc83d'; rr(ctx, 14, 26, 36, 28, 7); ctx.fill(); ctx.strokeStyle = '#a8761c'; ctx.lineWidth = 3; ctx.stroke();
        ctx.fillStyle = '#7a5a10'; ctx.beginPath(); ctx.arc(32, 38, 4, 0, Math.PI * 2); ctx.fill();
      }); break;
      case 'ui_icon_close': icon(64, (ctx) => {
        ctx.fillStyle = '#d9483b'; ctx.beginPath(); ctx.arc(32, 32, 28, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 7; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(21, 21); ctx.lineTo(43, 43); ctx.moveTo(43, 21); ctx.lineTo(21, 43); ctx.stroke();
      }); break;
      case 'ui_icon_check': icon(64, (ctx) => {
        ctx.fillStyle = '#5cc86a'; ctx.beginPath(); ctx.arc(32, 32, 28, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 7; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(18, 33); ctx.lineTo(28, 43); ctx.lineTo(46, 22); ctx.stroke();
      }); break;
      case 'ui_icon_backpack': icon(64, (ctx) => {
        ctx.fillStyle = '#8a5a33'; rr(ctx, 14, 14, 36, 42, 12); ctx.fill();
        ctx.fillStyle = '#c98f55'; rr(ctx, 18, 30, 28, 18, 6); ctx.fill();
        ctx.strokeStyle = '#6b4a2e'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(32, 16, 8, Math.PI, 0); ctx.stroke();
      }); break;
      case 'ui_icon_speed': icon(64, (ctx) => {
        ctx.fillStyle = '#3d8be0'; ctx.beginPath(); ctx.moveTo(36, 6); ctx.lineTo(14, 36); ctx.lineTo(30, 36); ctx.lineTo(26, 58); ctx.lineTo(50, 26); ctx.lineTo(34, 26); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5; ctx.stroke();
      }); break;
      case 'ui_icon_worker': icon(64, (ctx) => {
        ctx.fillStyle = '#f6cfae'; ctx.beginPath(); ctx.arc(32, 22, 11, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#3d8be0'; rr(ctx, 16, 34, 32, 22, 10); ctx.fill();
      }); break;
      case 'ui_arrow': this.canvas(textures, tk, 96, 112, (ctx) => {
        ctx.fillStyle = 'rgba(0,0,0,0.15)';
        ctx.beginPath(); ctx.moveTo(30, 8); ctx.lineTo(66, 8); ctx.lineTo(66, 50); ctx.lineTo(88, 50); ctx.lineTo(48, 104); ctx.lineTo(8, 50); ctx.lineTo(30, 50); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#ffc83d'; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 6; ctx.lineJoin = 'round';
        ctx.beginPath(); ctx.moveTo(30, 4); ctx.lineTo(66, 4); ctx.lineTo(66, 46); ctx.lineTo(88, 46); ctx.lineTo(48, 100); ctx.lineTo(8, 46); ctx.lineTo(30, 46); ctx.closePath(); ctx.stroke(); ctx.fill();
      }); break;
      case 'ui_bubble': this.canvas(textures, tk, 112, 96, (ctx) => {
        ctx.fillStyle = 'rgba(30,40,60,0.18)'; rr(ctx, 4, 8, 104, 68, 26); ctx.fill();
        ctx.fillStyle = '#ffffff'; rr(ctx, 4, 4, 104, 68, 26); ctx.fill();
        ctx.beginPath(); ctx.moveTo(44, 70); ctx.lineTo(56, 90); ctx.lineTo(68, 70); ctx.closePath(); ctx.fill();
      }); break;
      case 'ui_badge_max': this.canvas(textures, tk, 96, 44, (ctx) => {
        ctx.fillStyle = '#d9483b'; rr(ctx, 2, 2, 92, 40, 20); ctx.fill(); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 3; rr(ctx, 3.5, 3.5, 89, 37, 18); ctx.stroke();
      }); break;
      case 'ui_ring_bg': icon(96, (ctx) => { ctx.fillStyle = 'rgba(43,47,58,0.45)'; ctx.beginPath(); ctx.arc(48, 48, 44, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 10; ctx.beginPath(); ctx.arc(48, 48, 36, 0, Math.PI * 2); ctx.stroke(); }); break;
      case 'ui_ring_fill': icon(96, (ctx) => { ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 10; ctx.beginPath(); ctx.arc(48, 48, 36, 0, Math.PI * 2); ctx.stroke(); }); break;
      case 'ui_joystick_base': icon(192, (ctx) => {
        ctx.fillStyle = 'rgba(255,255,255,0.22)'; ctx.beginPath(); ctx.arc(96, 96, 90, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(96, 96, 86, 0, Math.PI * 2); ctx.stroke();
      }); break;
      case 'ui_joystick_knob': icon(96, (ctx) => {
        ctx.fillStyle = 'rgba(30,40,60,0.2)'; ctx.beginPath(); ctx.arc(48, 52, 40, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(48, 46, 40, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#e3ecf6'; ctx.beginPath(); ctx.arc(48, 50, 30, 0, Math.PI * 2); ctx.fill();
      }); break;
      case 'ui_pad_unlock': pad('rgba(61,139,224,0.30)'); break;
      case 'ui_pad_input': pad('rgba(255,255,255,0.22)', (ctx) => { ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.moveTo(-26, -22); ctx.lineTo(26, -22); ctx.lineTo(0, 22); ctx.closePath(); ctx.fill(); }); break;
      case 'ui_pad_output': pad('rgba(255,255,255,0.22)', (ctx) => { ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.moveTo(-26, 22); ctx.lineTo(26, 22); ctx.lineTo(0, -22); ctx.closePath(); ctx.fill(); }); break;
      case 'ui_pad_cash': pad('rgba(255,200,61,0.30)', (ctx) => { ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(0, 0, 26, 0, Math.PI * 2); ctx.stroke(); }); break;
      case 'ui_pad_hire': pad('rgba(92,200,106,0.30)'); break;
      case 'ui_pad_upgrade': pad('rgba(255,200,61,0.30)'); break;
      case 'ui_title_bg': this.canvas(textures, tk, 360, 640, (ctx) => {
        const g = ctx.createLinearGradient(0, 0, 0, 640); g.addColorStop(0, '#bcd6f0'); g.addColorStop(0.55, '#e9f1f9'); g.addColorStop(1, '#f4f7fb'); ctx.fillStyle = g; ctx.fillRect(0, 0, 360, 640);
        ctx.fillStyle = '#dce7f3'; ctx.beginPath(); ctx.moveTo(0, 430); ctx.quadraticCurveTo(120, 380, 220, 420); ctx.quadraticCurveTo(300, 450, 360, 410); ctx.lineTo(360, 640); ctx.lineTo(0, 640); ctx.fill();
        const r = rng(7);
        for (let i = 0; i < 14; i++) { const x = r() * 360, y = 380 + r() * 60, h = 50 + r() * 50; ctx.fillStyle = i % 2 ? '#2e6b4f' : '#1f4d3a'; ctx.beginPath(); ctx.moveTo(x - h * 0.3, y); ctx.lineTo(x, y - h); ctx.lineTo(x + h * 0.3, y); ctx.fill(); }
      }); break;
      default:
        if (key.startsWith('portrait_')) {
          const col = CHAR_COLORS[key.slice(9)] || '#cccccc';
          icon(128, (ctx) => { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(64, 100, 42, Math.PI, 0); ctx.fill(); ctx.fillStyle = '#f6cfae'; ctx.beginPath(); ctx.arc(64, 54, 30, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#3a2a22'; ctx.beginPath(); ctx.arc(64, 44, 30, Math.PI, 0); ctx.fill(); });
        } else {
          icon(64, (ctx) => { ctx.fillStyle = '#ffffff'; rr(ctx, 6, 6, 52, 52, 12); ctx.fill(); ctx.strokeStyle = '#2b2f3a'; ctx.lineWidth = 3; ctx.stroke(); });
        }
    }
  },

  /** placeholder character atlas: a capsule body with a nose showing facing, per dir 2 frames */
  character(textures, key, dirs) {
    const tk = 'ph_char_' + key;
    if (textures.exists(tk)) return tk;
    const col = CHAR_COLORS[key] || '#cccccc';
    const isAnimal = key === 'deer' || key === 'boar';
    const W = 128, H = 128;
    const ct = textures.createCanvas(tk, W * dirs.length * 2, H);
    const ctx = ct.context;
    const vec = { S: [0, 1], SE: [1, 0.5], E: [1, 0], NE: [1, -0.5], N: [0, -1] };
    dirs.forEach((d, di) => {
      for (let f = 0; f < 2; f++) {
        const ox = (di * 2 + f) * W, bob = f ? -3 : 0;
        ctx.save(); ctx.translate(ox, 0);
        if (isAnimal) {
          ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(64, 88 + bob, 30, 18, 0, 0, Math.PI * 2); ctx.fill();
        } else {
          ctx.fillStyle = col; rr(ctx, 44, 52 + bob, 40, 50, 18); ctx.fill();
          ctx.fillStyle = '#f6cfae'; ctx.beginPath(); ctx.arc(64, 40 + bob, 20, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = '#3a2a22'; ctx.beginPath(); ctx.arc(64, 34 + bob, 20, Math.PI, 0); ctx.fill();
        }
        const v = vec[d] || [0, 1];
        ctx.fillStyle = '#d9483b'; ctx.beginPath(); ctx.arc(64 + v[0] * 18, (isAnimal ? 84 : 44) + bob + v[1] * 8, 6, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = 'rgba(40,30,20,0.5)'; ctx.lineWidth = 2;
        if (!isAnimal) { rr(ctx, 44, 52 + bob, 40, 50, 18); ctx.stroke(); }
        ctx.restore();
        ct.add(d + '_' + f, 0, (di * 2 + f) * W, 0, W, H);
      }
    });
    ct.refresh();
    return tk;
  },

  shadow(textures) {
    return this.canvas(textures, 'fv_shadow', 64, 32, (ctx) => {
      const g = ctx.createRadialGradient(32, 32, 2, 32, 32, 32);
      g.addColorStop(0, 'rgba(40,55,90,0.42)'); g.addColorStop(0.6, 'rgba(40,55,90,0.22)'); g.addColorStop(1, 'rgba(40,55,90,0)');
      ctx.save(); ctx.scale(1, 0.5); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(32, 32, 32, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    });
  },

  white(textures) {
    return this.canvas(textures, 'fv_white', 8, 8, (ctx) => { ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 8, 8); });
  },
};

function guessKind(key) {
  if (key.startsWith('station_')) return 'station';
  if (key.startsWith('item_')) return 'item';
  if (key.startsWith('ui_')) return 'ui';
  if (key.startsWith('fx_')) return 'fx';
  if (/lodge|hut|tent|counter|trade|bench|net|pier|mine_/.test(key)) return 'building';
  return 'decor';
}

export { rr, star, heart, diamond, rng, hashStr };
