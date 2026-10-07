// Deer & boar: roam inside the hunting ground, shy away from the chief, get caught
// (player) or shot (hunter), drop raw meat, respawn later.

import { Character } from './Character.js';
import { Audio } from '../core/Audio.js';
import { BALANCE } from '../data/balance.js';
import { isoPt, inIsoRect } from '../core/Iso.js';

export class Animal extends Character {
  constructor(gs, kind, zone) {
    const p = Animal.randomPoint(zone, 1.2);
    super(gs, kind, p.x, p.y, { radius: 18 });
    this.kind = kind;
    this.zone = zone;
    this.item = 'item_meat_raw';
    this.playerAnim = 'harvest';
    this.hpMax = BALANCE.resources.animal.hp;
    this.hp = this.hpMax;
    this.state = 'idle';
    this.t = Math.random() * 2;
    this.target = { x: p.x, y: p.y };
    this.enabled = true;
    this.dead = false;
    this.respawnT = 0;
    this.targetedBy = null;
    this.reservedBy = null;
    this.lastYield = 0;
    this.standDist = 40;
    this.callT = 3 + Math.random() * 8;
    this._p = { x: 0, y: 0 };
    this.dir = Math.floor(Math.random() * 8);
    this.play('idle', true);
  }

  static randomPoint(zone, margin) {
    const [w, h] = zone.size;
    const mx = (Math.random() - 0.5) * (w - margin * 2), my = (Math.random() - 0.5) * (h - margin * 2);
    return isoPt(zone.center[0], zone.center[1], mx, my);
  }

  ready() { return this.enabled && !this.dead; }

  standPoint(fx, fy, out) {
    let dx = fx - this.x, dy = (fy - this.y) * 2;
    const d = Math.hypot(dx, dy) || 1;
    out = out || {};
    out.x = this.x + (dx / d) * this.standDist; out.y = this.y + ((dy / d) * this.standDist) / 2;
    return out;
  }

  setEnabled(v) {
    this.enabled = v;
    this.sprite.setVisible(v && !this.dead); this.shadow.setVisible(v && !this.dead);
  }

  /** returns item type when the animal is caught/killed by this hit */
  hit(by) {
    if (!this.ready()) return null;
    const gs = this.gs;
    this.hp--;
    gs.effects.sheet('fx_hit', this.x, this.y - 30, { size: 90 });
    gs.effects.burst('spark', this.x, this.y - 30, 4);
    gs.sfxAt('sfx_hit_animal', this.x, this.y, { volume: 0.8 }, by === gs.player);
    this.sprite.setTintFill(0xffffff);
    gs.time.delayedCall(80, () => this.sprite.clearTint());
    if (by === gs.player) {
      // caught by the chief: stunned on the spot (stars), easy to finish
      this.state = 'stun'; this.t = 1.4;
      this.vx = this.vy = 0;
    } else {
      // hit by an arrow: startled hop away
      this.state = 'flee';
      this.t = 0.6;
      const dx = this.x - by.x, dy = this.y - by.y, d = Math.hypot(dx, dy) || 1;
      this.target.x = this.x + (dx / d) * 90; this.target.y = this.y + (dy / d) * 45;
    }
    if (this.hp > 0) return null;
    this.die();
    this.lastYield = BALANCE.resources.animal.meat;
    return this.item;
  }

  die() {
    const gs = this.gs;
    this.dead = true;
    this.targetedBy = null; this.reservedBy = null;
    gs.effects.sheet('fx_poof', this.x, this.y - 30, { size: 160 });
    gs.effects.burst('snowhit', this.x, this.y - 20, 10);
    gs.sfxAt(this.kind === 'deer' ? 'sfx_animal_deer' : 'sfx_animal_boar', this.x, this.y, { volume: 0.6 });
    this.sprite.setVisible(false); this.shadow.setVisible(false);
    this.respawnT = BALANCE.resources.animal.respawn;
  }

  respawn() {
    const gs = this.gs;
    const p = Animal.randomPoint(this.zone, 1.0);
    this.x = p.x; this.y = p.y;
    this.dead = false; this.hp = this.hpMax; this.state = 'idle'; this.t = 1;
    this.sprite.setVisible(this.enabled); this.shadow.setVisible(this.enabled);
    this.sprite.setScale(0.2);
    gs.tweens.add({ targets: this.sprite, scale: 1, duration: 400, ease: 'Back.easeOut' });
    gs.effects.sheet('fx_poof', this.x, this.y - 25, { size: 120 });
  }

  update(dt) {
    if (!this.enabled) return;
    if (this.dead) {
      this.respawnT -= dt;
      if (this.respawnT <= 0) this.respawn();
      return;
    }
    const gs = this.gs, A = BALANCE.resources.animal;
    const p = gs.player;
    const pd = Math.hypot(p.x - this.x, (p.y - this.y) * 2);
    if (pd < A.fleeRange && this.state !== 'flee' && this.state !== 'stun' && p.vx * p.vx + p.vy * p.vy > 400) {
      this.state = 'flee'; this.t = 0.9;
      const dx = this.x - p.x, dy = this.y - p.y, d = Math.hypot(dx, dy) || 1;
      this.target.x = this.x + (dx / d) * 130; this.target.y = this.y + (dy / d) * 65;
    }
    this.t -= dt;
    let speed = 0;
    if (this.state === 'idle') {
      if (this.t <= 0) {
        const q = Animal.randomPoint(this.zone, 1.0);
        this.target.x = q.x; this.target.y = q.y;
        this.state = 'walk'; this.t = 6;
      }
    } else if (this.state === 'walk') {
      speed = A.speed;
      if (this.t <= 0) { this.state = 'idle'; this.t = 1 + Math.random() * 2.5; }
    } else if (this.state === 'flee') {
      speed = A.fleeSpeed;
      if (this.t <= 0) { this.state = 'idle'; this.t = 0.8 + Math.random(); }
    } else if (this.state === 'stun') {
      if (this.t <= 0) { this.state = 'idle'; this.t = 0.5; }
      else if (Math.random() < dt * 3) gs.effects.burst('star', this.x, this.y + this.headTop, 1);
    }
    if (speed > 0) {
      const dx = this.target.x - this.x, dy = this.target.y - this.y;
      const d = Math.hypot(dx, dy);
      if (d < 6) { this.state = 'idle'; this.t = 1 + Math.random() * 2.5; this.vx = this.vy = 0; }
      else {
        this.vx = (dx / d) * speed; this.vy = (dy / d) * speed;
        const q = this._p;
        q.x = this.x + this.vx * dt; q.y = this.y + this.vy * dt;
        // stay inside the hunting ground
        const z = this.zone;
        if (!inIsoRect(q.x, q.y, z.center[0], z.center[1], z.size[0], z.size[1], 0.6)) {
          this.state = 'idle'; this.t = 0.4; this.vx = this.vy = 0;
        } else {
          gs.collision.resolve(q, this.radius);
          this.x = q.x; this.y = q.y;
        }
        this.face(this.vx, this.vy);
      }
    } else { this.vx = this.vy = 0; }
    this.play(speed > 0 && (this.vx || this.vy) ? 'walk' : 'idle');
    if (this.state === 'flee') this.sprite.anims.timeScale = 1.6; else this.sprite.anims.timeScale = 1;
    // occasional call when the player is near
    this.callT -= dt;
    if (this.callT <= 0) {
      this.callT = 6 + Math.random() * 10;
      if (pd < 420) Audio.play(this.kind === 'deer' ? 'sfx_animal_deer' : 'sfx_animal_boar', { volume: 0.35, throttle: 2000 });
    }
    this.sync(dt);
  }
}
