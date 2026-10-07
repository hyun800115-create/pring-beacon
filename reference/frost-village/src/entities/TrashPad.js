// Discard spot ("버리기") next to the beach campfire: stand on it and the carried items are
// thrown into the fire one by one. A safety valve so a bag full of items that nothing accepts
// (e.g. raw fish while the grill's input AND output are full) can never lock the game.

import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { BALANCE } from '../data/balance.js';
import { Pad } from './Pad.js';
import { t } from '../data/strings.js';
import { panel } from '../core/Panel.js';

export class TrashPad {
  constructor(gs, cfg) {
    this.gs = gs; this.x = cfg.x; this.y = cfg.y;
    this.fire = cfg.fire ? { x: cfg.fire[0], y: cfg.fire[1] } : { x: cfg.x, y: cfg.y - 30 };
    this.pad = new Pad(gs, this.x, this.y, 'input', 1.35, { icon: 'ui_icon_close', iconSize: 30 });
    this.pad.img.setTint(0xffd9c2);
    // small floating label
    const lab = gs.add.container(this.x, this.y - 50).setDepth(this.y + 2000);
    this.labelText = gs.add.text(0, 0, '', { fontFamily: gs.font, fontSize: '20px', fontStyle: '800', color: '#2b2f3a', resolution: 2 }).setOrigin(0.5, 0.5);
    this.labelBg = panel(gs, 0, 0, 'ui_panel', 100, 44).setOrigin(0.5, 0.5).setAlpha(0.92);
    lab.add([this.labelBg, this.labelText]);
    this.label = lab;
    this.labelBaseY = this.y - 50;
    this.refresh();
    this.standT = 0;
    this.t = 0;
    this.enabled = true;
  }

  refresh() {
    this.labelText.setText(t('trash'));
    this.labelBg.setSize(Math.max(84, this.labelText.width + 36), 44);
  }

  setEnabled(v) {
    if (this.enabled === v) return;
    this.enabled = v;
    this.pad.setVisible(v);
    this.label.setVisible(v);
  }

  /** returns true while the player stands on it */
  update(dt) {
    if (!this.enabled) return false;
    const gs = this.gs, p = gs.player;
    this.label.y = this.labelBaseY + Math.sin(gs.time.now / 420 + 1.3) * 3;
    // keep the floating label inside the screen while the pad is visible (same as the unlock pads)
    const v = gs.cameras.main.worldView, hw = this.labelBg.width * 0.5 + 8;
    let lx = this.x;
    if (this.x > v.x - 40 && this.x < v.right + 40 && v.width > hw * 2) lx = Math.max(v.x + hw, Math.min(v.right - hw, this.x));
    if (this.label.x !== lx) this.label.x = lx;
    const on = this.pad.contains(p.x, p.y);
    const la = on ? 0.35 : 1;
    if (Math.abs(this.label.alpha - la) > 0.01) this.label.setAlpha(this.label.alpha + (la - this.label.alpha) * Math.min(1, dt * 10));
    if (!on) { this.standT = 0; return false; }
    this.standT += dt;
    // a deliberate stop is needed (walking across never throws anything away)
    if (this.standT < (BALANCE.player.trashDelay || 0.6)) return true;
    this.t -= dt;
    if (this.t <= 0 && p.stack.count > 0) {
      this.t = 0.1;
      const it = p.stack.pop();
      if (it) {
        const f = this.fire;
        gs.effects.fly(it.spr, it.spr.x, it.spr.y, { x: f.x + (Math.random() - 0.5) * 16, y: f.y }, {
          dur: 320, height: 80, scaleTo: 0.3, spin: 200,
          onDone: (s) => {
            gs.effects.releaseItem(s);
            gs.effects.burst('smoke', f.x, f.y - 10, 1);
            gs.effects.burst('flame', f.x, f.y - 6, 2);
          },
        });
        Audio.play('sfx_whoosh', { volume: 0.35, rate: 1.2 + Math.random() * 0.2, throttle: 90 });
        this.pad.pulse();
      }
    }
    return true;
  }
}

