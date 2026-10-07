// A flat iso floor pad (input / output / cash / unlock / hire / upgrade).

import { Assets } from '../core/Assets.js';
import { gdist2 } from '../core/Iso.js';
import { DEPTH } from '../systems/DepthSort.js';

export class Pad {
  constructor(gs, x, y, kind, sizeM = 1.5, opts = {}) {
    this.gs = gs; this.x = x; this.y = y; this.kind = kind;
    const w = 90.5 * sizeM;
    this.w = w;
    this.img = Assets.image(gs, x, y, 'ui_pad_' + kind);
    this.img.setOrigin(0.5, 0.5).setDisplaySize(w, w / 2).setDepth(DEPTH.PAD);
    this.bsx = this.img.scaleX; this.bsy = this.img.scaleY;
    this.r = (w / 2) * (opts.radiusK || 0.78);
    if (opts.icon) {
      this.icon = Assets.image(gs, x, y, opts.icon).setDepth(DEPTH.PAD_ITEM - 1);
      const fr = this.icon.frame;
      const s = (opts.iconSize || 40) / Math.max(fr.realWidth, fr.realHeight);
      this.icon.setScale(s, s * 0.62).setOrigin(0.5, 0.6).setAlpha(0.55);
    }
  }
  contains(px, py, extra = 0) {
    const r = this.r + extra;
    return gdist2(px, py, this.x, this.y) < r * r;
  }
  setVisible(v) { this.img.setVisible(v); if (this.icon) this.icon.setVisible(v); }
  pulse() {
    const gs = this.gs, img = this.img;
    gs.tweens.killTweensOf(img);
    img.setScale(this.bsx * 1.08, this.bsy * 1.08);
    gs.tweens.add({ targets: img, scaleX: this.bsx, scaleY: this.bsy, duration: 220, ease: 'Quad.easeOut' });
  }
}
