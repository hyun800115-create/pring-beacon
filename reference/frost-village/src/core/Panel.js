// Nine-slice panels / buttons. With WebGL this is Phaser's NineSlice. Phaser only renders
// NineSlice in WebGL, so with the Canvas renderer (WebGL blocked / unavailable) a small
// rounded-rectangle stand-in with the same API (setSize, setOrigin, setTint, alpha, scale) is used
// instead, so the coin bar, settings panel and buttons never disappear.

import { Assets } from './Assets.js';

const FLAT = {
  ui_panel: { fill: 0xfff8ec, line: 0xe2d3b5 },
  ui_button_blue: { fill: 0x3d8be0, line: 0x2a64a8 },
  ui_button_green: { fill: 0x5cc86a, line: 0x3c9a4a },
  ui_button_gray: { fill: 0x8e99a8, line: 0x6a7584 },
  ui_coin_bar: { fill: 0x26364f, line: 0x16213a, alpha: 0.85 },
  ui_bubble_body: { fill: 0xffffff, line: 0xd7e3f2 },
};

class FlatPanel extends Phaser.GameObjects.Graphics {
  constructor(scene, x, y, w, h, style) {
    super(scene, { x, y });
    scene.add.existing(this);
    this._w = w; this._h = h; this._ox = 0.5; this._oy = 0.5;
    this._style = style; this._tint = null;
    this.redraw();
  }
  get width() { return this._w; }
  set width(v) { /* size is set with setSize */ }
  get height() { return this._h; }
  set height(v) { /* size is set with setSize */ }
  setSize(w, h) { this._w = w; this._h = h; this.redraw(); return this; }
  setOrigin(ox, oy) { this._ox = ox; this._oy = oy === undefined ? ox : oy; this.redraw(); return this; }
  setTint(c) { this._tint = c; this.redraw(); return this; }
  clearTint() { this._tint = null; this.redraw(); return this; }
  redraw() {
    const w = this._w, h = this._h, x = -w * this._ox, y = -h * this._oy, r = Math.min(20, h / 2, w / 2);
    const st = this._style;
    this.clear();
    this.fillStyle(0x1f3354, 0.18); this.fillRoundedRect(x, y + 4, w, h, r);
    this.fillStyle(this._tint !== null ? this._tint : st.fill, st.alpha !== undefined ? st.alpha : 1); this.fillRoundedRect(x, y, w, h, r);
    this.lineStyle(3, st.line, 1); this.strokeRoundedRect(x + 1.5, y + 1.5, w - 3, h - 3, r);
  }
}

/** a resizable panel / button background for sprite key `key` (ui_panel, ui_button_blue, ...) */
export function panel(scene, x, y, key, w, h) {
  const canvas = scene.sys.game.renderer && scene.sys.game.renderer.type === Phaser.CANVAS;
  if (canvas || typeof scene.add.nineslice !== 'function') return new FlatPanel(scene, x, y, w, h, FLAT[key] || FLAT.ui_panel);
  const n = Assets.nine(key);
  return scene.add.nineslice(x, y, n.tex, n.frame, w, h, n.l, n.r, n.t, n.b);
}
