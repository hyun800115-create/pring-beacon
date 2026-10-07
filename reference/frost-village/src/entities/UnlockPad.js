// Unlock / hire / upgrade pads: stand on one with coins and they drain into it
// (progress ring + rising tick). When fully paid the pad completes.

import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { BALANCE } from '../data/balance.js';
import { DEPTH } from '../systems/DepthSort.js';
import { Pad } from './Pad.js';
import { t, fmt } from '../data/strings.js';
import { panel } from '../core/Panel.js';

/** a price from balance.js as a whole number >= 1 (0, negative, missing or text would make a pad that never completes) */
export function sanePrice(v) { const n = Math.floor(Number(v)); return Number.isFinite(n) && n >= 1 ? n : 1; }

export class UnlockPad {
  /**
   * opts: kind ('unlock'|'hire'|'upgrade'), cost, paid, label (string key), labelFn, icon (sprite key), onComplete(pad), sizeM
   */
  constructor(gs, id, x, y, opts) {
    this.gs = gs; this.id = id; this.x = x; this.y = y;
    this.opts = opts;
    this.kind = opts.kind || 'unlock';
    this.cost = sanePrice(opts.cost);
    this.paid = Math.max(0, Math.min(Math.floor(Number(opts.paid)) || 0, this.cost));
    this.needsLeave = false;
    this.standT = 0;
    this.acc = 0;
    this.coinT = 0;
    this.tickT = 0;
    this.done = false;
    this.maxed = false;
    this.active = true;
    const sizeM = opts.sizeM || 1.9;
    this.pad = new Pad(gs, x, y, this.kind === 'upgrade' ? 'upgrade' : this.kind === 'hire' ? 'hire' : 'unlock', sizeM, { radiusK: 0.8 });

    // cost on the floor: coin icon + number
    this.costCoin = Assets.image(gs, x - 30, y + 2, 'ui_icon_coin').setDepth(DEPTH.PAD_TEXT);
    const cf = this.costCoin.frame;
    this.costCoin.setScale(30 / Math.max(cf.realWidth, cf.realHeight)).setOrigin(0.5, 0.5);
    this.costText = gs.add.text(x - 10, y + 2, '', { fontFamily: gs.font, fontSize: '30px', fontStyle: '900', color: '#ffffff', stroke: '#2b2f3a', strokeThickness: 6, resolution: 2 }).setOrigin(0, 0.5).setDepth(DEPTH.PAD_TEXT);
    this.maxBadge = null;

    // floating label: icon + title on a little panel
    const lab = gs.add.container(x, y - 62).setDepth(y + 2000);
    const title = gs.add.text(0, 0, '', { fontFamily: gs.font, fontSize: '22px', fontStyle: '800', color: '#2b2f3a', resolution: 2 }).setOrigin(0, 0.5);
    const icon = Assets.image(gs, 0, 0, opts.icon || 'ui_icon_lock').setOrigin(0.5, 0.5);
    const icf = icon.frame;
    icon.setScale((opts.iconSize || 46) / Math.max(icf.realWidth, icf.realHeight));
    const bg = panel(gs, 0, 0, 'ui_panel', 100, 56).setOrigin(0.5, 0.5);
    lab.add([bg, icon, title]);
    this.label = lab; this.labelBg = bg; this.labelIcon = icon; this.labelText = title;
    this.labelBaseY = y - 62;

    // progress ring (drawn while paying)
    this.ringBg = Assets.image(gs, x, y - 118, 'ui_ring_bg').setDepth(DEPTH.LABEL).setVisible(false);
    const rf = this.ringBg.frame;
    this.ringBg.setScale(64 / Math.max(rf.realWidth, rf.realHeight));
    this.ring = gs.add.graphics().setDepth(DEPTH.LABEL + 1).setVisible(false);
    this.refresh();
  }

  get remaining() { return Math.max(0, this.cost - this.paid); }

  setCost(cost, paid = 0) {
    this.cost = sanePrice(cost); this.paid = Math.max(0, Math.min(Math.floor(Number(paid)) || 0, this.cost));
    this.refresh();
  }

  refresh() {
    const txt = this.opts.labelFn ? this.opts.labelFn() : t(this.opts.label || this.id);
    this.labelText.setText(txt);
    const iconW = this.labelIcon.displayWidth;
    const w = Math.max(120, this.labelText.width + iconW + 34);
    this.labelBg.setSize(w, 60);
    this.labelIcon.setPosition(-w / 2 + 14 + iconW / 2, -2);
    this.labelText.setPosition(-w / 2 + 22 + iconW, 0);
    if (this.maxed) {
      this.costText.setVisible(false); this.costCoin.setVisible(false);
      if (!this.maxBadge) {
        const gs = this.gs;
        const c = gs.add.container(this.x, this.y).setDepth(DEPTH.PAD_TEXT);
        const b = Assets.image(gs, 0, 0, 'ui_badge_max').setOrigin(0.5);
        b.setScale(96 / Math.max(b.frame.realWidth, 1));
        const tx = gs.add.text(0, -1, t('max'), { fontFamily: gs.font, fontSize: '24px', fontStyle: '900', color: '#ffffff', stroke: '#7a2a1a', strokeThickness: 5, resolution: 2 }).setOrigin(0.5);
        c.add([b, tx]);
        this.maxBadge = c;
      }
      this.maxBadge.setVisible(this.active);
    } else {
      this.costText.setText(fmt(this.remaining));
      // [coin] gap [digits], centred as a group (the text stroke needs a few px of air)
      const tw = this.costText.width + 42;
      this.costCoin.setPosition(this.x - tw / 2 + 15, this.y + 1);
      this.costText.setPosition(this.x - tw / 2 + 38, this.y + 1);
      this.costText.setVisible(this.active); this.costCoin.setVisible(this.active);
      if (this.maxBadge) this.maxBadge.setVisible(false);
    }
  }

  setActive(v) {
    this.active = v;
    this.pad.setVisible(v);
    this.label.setVisible(v);
    if (!v) { this.ring.setVisible(false); this.ringBg.setVisible(false); }
    this.refresh();
  }

  /** returns true while the player is standing on it (for tutorial / UI) */
  update(dt) {
    if (!this.active || this.done) return false;
    const gs = this.gs, p = gs.player;
    this.label.y = this.labelBaseY + Math.sin(gs.time.now / 420 + this.x * 0.01) * 4;
    // keep the floating label inside the screen while its pad is visible
    const v = gs.cameras.main.worldView, hw = this.labelBg.width * 0.5 + 8;
    let lx = this.x;
    if (this.x > v.x - 40 && this.x < v.right + 40 && v.width > hw * 2) lx = Math.max(v.x + hw, Math.min(v.right - hw, this.x));
    if (this.label.x !== lx) this.label.x = lx;
    // "ready" highlight when the player can afford it
    const afford = !this.maxed && this.remaining > 0 && gs.economy.coins >= this.remaining;
    if (afford && !this.sparkle) {
      this.sparkle = gs.effects.loop('fx_sparkle', this.x, this.y - 30, 150, DEPTH.PAD_TEXT + 1) || 'none';
    }
    if (this.sparkle && this.sparkle !== 'none') this.sparkle.setVisible(afford);
    if (afford) {
      const k = 1 + Math.sin(gs.time.now / 180) * 0.035;
      this.pad.img.setScale(this.pad.bsx * k, this.pad.bsy * k);
      if (this.sparkle === 'none') { this.spT = (this.spT || 0) - dt; if (this.spT <= 0) { this.spT = 0.35; gs.effects.burst('spark', this.x + (Math.random() - 0.5) * 120, this.y - 10 - Math.random() * 30, 1); } }
    } else if (this.wasAfford) this.pad.img.setScale(this.pad.bsx, this.pad.bsy);
    this.wasAfford = afford;
    const on = this.pad.contains(p.x, p.y);
    const la = on ? 0.3 : 1;
    if (Math.abs(this.label.alpha - la) > 0.01) this.label.setAlpha(this.label.alpha + (la - this.label.alpha) * Math.min(1, dt * 10));
    if (!on || this.maxed) {
      this.standT = 0;
      this._warned = false;
      if (!on) this.needsLeave = false;
      if (this.ring.visible) { this.ring.setVisible(false); this.ringBg.setVisible(false); }
      return on;
    }
    // after an upgrade the player has to step off before the next level starts draining coins
    if (this.needsLeave) return true;
    this.standT += dt;
    if (this.standT < (Number(BALANCE.player.padDelay) || 0)) return true;
    // already fully paid (e.g. the price was lowered in balance.js below a saved partial payment)
    if (!(this.remaining > 0)) { this.complete(); return true; }
    if (!this.ring.visible) this.drawRing();
    const eco = gs.economy;
    if (eco.coins > 0) {
      const rate = Math.max(12, this.cost / Math.max(0.1, Number(BALANCE.payDuration) || 1.6));
      this.acc += rate * dt;
      let amt = Math.floor(this.acc);
      if (amt >= 1) {
        this.acc -= amt;
        amt = Math.min(amt, this.remaining, eco.coins);
        eco.spend(amt);
        this.paid += amt;
        this.refresh();
        this.drawRing();
        // visual coins
        this.coinT -= dt;
        if (this.coinT <= 0) {
          this.coinT = 0.06;
          const spr = gs.effects.takeItem('item_coin');
          spr.setScale(0.7);
          gs.effects.fly(spr, p.x, p.y - 60, { x: this.x, y: this.y }, { dur: 220, height: 40, scaleTo: 0.35, onDone: (s) => gs.effects.releaseItem(s) });
        }
        this.tickT -= dt;
        if (this.tickT <= 0) {
          this.tickT = 0.07;
          Audio.play('sfx_pad_fill', { volume: 0.5, rate: 0.85 + 0.7 * (this.paid / this.cost), throttle: 60 });
        }
      }
      if (this.remaining <= 0) this.complete();
    } else if (this.remaining > 0 && eco.coins <= 0 && this.standT > BALANCE.player.padDelay + 0.05 && !this._warned) {
      this._warned = true;
      gs.ui.toast(t('notEnoughCoins'));
      Audio.play('sfx_error', { volume: 0.5 });
    }
    return true;
  }

  drawRing() {
    const g = this.ring;
    const pct = this.cost > 0 ? this.paid / this.cost : 1;
    g.clear();
    g.setVisible(true); this.ringBg.setVisible(true);
    const cx = this.x, cy = this.y - 118, r = 23;
    g.lineStyle(9, 0x5cc86a, 1);
    g.beginPath();
    g.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct, false);
    g.strokePath();
  }

  complete() {
    if (this.done) return;
    const gs = this.gs;
    this.done = true;
    if (this.sparkle && this.sparkle !== 'none') this.sparkle.setVisible(false);
    this.pad.img.setScale(this.pad.bsx, this.pad.bsy);
    this.ring.setVisible(false); this.ringBg.setVisible(false);
    gs.effects.sheet('fx_unlock', this.x, this.y - 20, { size: 260 });
    gs.effects.burst('star', this.x, this.y - 30, 18);
    Audio.play(this.kind === 'hire' ? 'sfx_hire' : this.kind === 'upgrade' ? 'sfx_levelup' : 'sfx_unlock', { volume: 1 });
    gs.effects.shake(160, 0.005);
    gs.effects.vibrate(40);
    if (this.opts.onComplete) this.opts.onComplete(this);
  }

  /** remove from the world with a little shrink */
  vanish() {
    const gs = this.gs;
    const objs = [this.pad.img, this.label, this.costText, this.costCoin];
    if (this.pad.icon) objs.push(this.pad.icon);
    gs.tweens.add({ targets: objs, alpha: 0, duration: 300, onComplete: () => this.destroy() });
  }

  destroy() {
    this.pad.img.destroy(); if (this.pad.icon) this.pad.icon.destroy();
    this.label.destroy(); this.costText.destroy(); this.costCoin.destroy();
    this.ring.destroy(); this.ringBg.destroy();
    if (this.maxBadge) this.maxBadge.destroy();
    if (this.sparkle && this.sparkle !== 'none') this.sparkle.destroy();
    this.sparkle = null;
    this.active = false;
  }

  /** allow paying again (upgrades): reset completion state */
  rearm(cost) {
    this.done = false; this.cost = sanePrice(cost); this.paid = 0; this.acc = 0;
    this.needsLeave = true; this.standT = 0;
    this.ring.setVisible(false); this.ringBg.setVisible(false);
    this.refresh();
  }
}
