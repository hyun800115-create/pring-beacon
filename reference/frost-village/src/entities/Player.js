// The chief: joystick movement, auto-gather when standing still near a resource,
// carried item tower, footsteps.

import { Character } from './Character.js';
import { Audio } from '../core/Audio.js';
import { BALANCE } from '../data/balance.js';
import { t } from '../data/strings.js';

export class Player extends Character {
  constructor(gs, x, y) {
    super(gs, 'player', x, y, { radius: 16, carryScale: BALANCE.player.carryScale });
    this.stillT = 0;
    this.node = null;
    this.stepT = 0;
    this.fullWarnT = 0;
    this.onImpact = () => this.impact();
    this._p = { x: 0, y: 0 };
  }

  get capacity() { return this.gs.progress.capacity(); }
  get speed() { return BALANCE.player.speed * this.gs.progress.speedMult(); }
  get room() { return this.capacity - this.stack.count - this.stack.incoming; }

  update(dt, inp) {
    const gs = this.gs;
    this.fullWarnT -= dt;
    if (inp.mag > 0.05) {
      const sp = this.speed;
      // quick acceleration toward the joystick velocity (snappy but not robotic)
      const k = Math.min(1, dt * 16);
      this.vx += (inp.x * sp - this.vx) * k;
      this.vy += (inp.y * sp * BALANCE.player.verticalFactor - this.vy) * k;
      const v = Math.hypot(this.vx, this.vy);
      this.sprite.anims.timeScale = Math.max(0.6, Math.min(1.35, v / 210));
      const p = this._p;
      p.x = this.x + this.vx * dt; p.y = this.y + this.vy * dt;
      gs.collision.resolve(p, this.radius);
      this.x = p.x; this.y = p.y;
      this.stillT = 0;
      this.node = null;
      this.face(this.vx, this.vy);
      this.locomotion(true);
      // footsteps
      this.stepT -= dt * (0.6 + inp.mag * 0.6);
      if (this.stepT <= 0) {
        this.stepT = 0.27;
        gs.effects.burst('dust', this.x + (Math.random() - 0.5) * 10, this.y - 2, 1);
        Audio.play('sfx_step_snow', { volume: 0.32, rate: 0.9 + Math.random() * 0.2, throttle: 120 });
      }
    } else {
      this.vx = this.vy = 0;
      this.sprite.anims.timeScale = 1;
      this.stillT += dt;
      if (this.node && this.node.kind !== 'tree' && this.node.kind !== 'rock' && this.node.kind !== 'wheat' && this.node.kind !== 'net') {
        // moving targets (animals) must stay within reach
        const dx = this.node.x - this.x, dy = (this.node.y - this.y) * 2;
        if (dx * dx + dy * dy > Math.pow(BALANCE.player.gatherRange * 1.5, 2)) this.node = null;
      }
      if (this.node && (!this.node.ready() || this.room <= 0)) {
        if (this.room <= 0) this.warnFull();
        this.node = null;
      }
      if (!this.node && this.stillT > BALANCE.player.stillDelay && !gs.playerOnPad) {
        const n = gs.findGatherable(this.x, this.y, BALANCE.player.gatherRange);
        if (n) {
          if (this.room <= 0) this.warnFull();
          else if (gs.stationBlocked(n.item)) gs.fullToast();   // its station is full both ways: don't fill the bag
          else this.node = n;
        }
      }
      if (this.node) {
        this.faceTo(this.node.x, this.node.y);
        this.play(this.node.playerAnim);
      } else this.locomotion(false);
    }
    this.sync(dt);
  }

  warnFull() {
    if (this.fullWarnT > 0) return;
    this.fullWarnT = 2.5;
    this.gs.ui.toast(t('bagFull'));
    Audio.play('sfx_error', { volume: 0.4 });
  }

  impact() {
    const n = this.node;
    if (!n || this.room <= 0) return;
    const item = n.hit(this);
    if (!item) return;
    const count = n.lastYield || 1;
    n.lastYield = 0;
    const from = n.kind === 'net' ? n.fishPos() : this.impactPoint();
    for (let i = 0; i < count && this.room > 0; i++) {
      this.gs.time.delayedCall(i * 90, () => this.gs.spawnItemTo(item, from.x, from.y, this, true));
    }
    this.gs.effects.vibrate(8);
  }
}
