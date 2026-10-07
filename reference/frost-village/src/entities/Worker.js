// Hired workers: go to a resource -> play the job's work anim -> carry a stack -> walk to the
// station's input pad -> drop items one by one -> repeat. The hunter shoots arrows.
// Couriers (role 'porter', hired after the village is complete) instead pick up the station's
// products at its output pad and carry them to the counter / trade post.

import { Character } from './Character.js';
import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { BALANCE } from '../data/balance.js';
import { gdist } from '../core/Iso.js';
import { DEPTH } from '../systems/DepthSort.js';
import { shoreY } from '../systems/Collision.js';

const STATION_OF = { fisherman: 'grill', lumberjack: 'sawmill', farmer: 'bakery', miner: 'smelter', hunter: 'smokehouse' };
const FOOD_OUT = ['item_fish_cooked', 'item_bread', 'item_meat_cooked'];

export class Worker extends Character {
  /** where a worker waits when there is nothing to do */
  static homeFor(gs, type, index, role) {
    if (role === 'porter') {
      const pad = gs.stations[STATION_OF[type]].outPad;
      const p = { x: pad.x + 34, y: pad.y + 18 };
      gs.collision.resolve(p, 14);
      return [p.x, p.y];
    }
    return gs.workerHome(type, index);
  }

  constructor(gs, type, x, y, index = 0, role = 'worker') {
    super(gs, type, x, y, { radius: 14, capacity: role === 'porter' ? BALANCE.workers.porterCapacity : BALANCE.workers.capacity, carryScale: BALANCE.player.carryScale });
    this.type = type;
    this.role = role;
    this.index = index;
    this.station = gs.stations[STATION_OF[type]];
    this.state = 'seek';
    this.node = null;
    this.cycles = 0;
    this.waitT = 0;
    this.dropT = 0;
    this.speed = BALANCE.workers.speed * (0.95 + Math.random() * 0.1);
    this.stand = { x: 0, y: 0 };
    this.onImpact = () => this.impact();
    this.home = Worker.homeFor(gs, type, index, role);
    if (role === 'porter') {
      this.onImpact = null;
      this.seller = FOOD_OUT.indexOf(this.station.output) >= 0 ? gs.market : gs.trade;
      this.waitT = 0;
    }
    gs.agents.push(this);
  }

  // ------------------------------------------------------------------ courier
  updatePorter(dt) {
    const gs = this.gs, st = this.station, out = st.outStack;
    const shelf = this.seller.shelf;
    switch (this.state) {
      case 'seek':     // walk to the station's output pad
      default: {
        if (this.stack.count > 0 && this.room <= 0) { this.state = 'haul'; break; }
        if (gs.moveAgent(this, this.home[0], this.home[1], this.speed, dt, 10)) {
          this.vx = this.vy = 0;
          this.state = 'load'; this.dropT = 0; this.waitT = 0;
          if (this.dir !== 2) { this.dir = 2; this.play(this.animName, true); }
          this.locomotion(false);
        }
        break;
      }
      case 'load': {  // take products one by one
        this.vx = this.vy = 0;
        this.dropT -= dt;
        if (this.room <= 0) { this.state = 'haul'; break; }
        if (out.count > 0) {
          this.waitT = 0;
          if (this.dropT <= 0 && gs.moveItem(out, this.stack, null, { dur: 230, height: 55 })) this.dropT = 0.14;
        } else {
          this.waitT += dt;
          // carry what we have once the output runs dry for a moment (or right away with a decent load)
          if (this.stack.count > 0 && (this.stack.count >= 3 || this.waitT > 2.5)) this.state = 'haul';
        }
        this.locomotion(false);
        break;
      }
      case 'haul': {  // walk to the counter / trade post shelf
        if (this.stack.count + this.stack.incoming === 0) { this.state = 'seek'; break; }
        if (!this.seller.enabled && this.seller !== gs.market) { this.locomotion(false); break; }
        if (gs.moveAgent(this, shelf.x + (this.index - 0.5) * 22 - 10, shelf.y + 10, this.speed, dt, 12)) {
          this.vx = this.vy = 0;
          this.state = 'unload'; this.dropT = 0.1; this.waitT = 0;
          this.locomotion(false);
        }
        break;
      }
      case 'unload': {
        this.vx = this.vy = 0;
        this.dropT -= dt;
        if (this.dropT <= 0) {
          this.dropT = 0.14;
          if (this.stack.count === 0) { if (this.stack.incoming === 0) this.state = 'seek'; }
          else if (!this.seller.feedFrom(this)) this.dropT = 0.6;     // shelf full: wait for buyers
        }
        this.locomotion(false);
        break;
      }
    }
  }

  get room() { return this.stack.max - this.stack.count - this.stack.incoming; }

  /** the fisherman fishes the open sea with a rod, so the net's stock does not matter to him */
  nodeOk(n) { return this.type === 'fisherman' ? n.enabled : n.ready(); }

  release() {
    if (this.node) {
      if (this.node.reservedBy === this) this.node.reservedBy = null;
      if (this.node.targetedBy === this) this.node.targetedBy = null;
    }
    this.node = null;
  }

  pickNode() {
    const gs = this.gs;
    if (this.type === 'fisherman') {
      const n = gs.net;
      const off = this.index * 78;
      this.stand.x = n.fisherSpot.x - off; this.stand.y = n.fisherSpot.y + off * 0.12;
      return n;
    }
    let list;
    if (this.type === 'lumberjack') list = gs.trees;
    else if (this.type === 'farmer') list = gs.wheat;
    else if (this.type === 'miner') list = gs.rocks;
    else list = gs.animals;
    let best = null, bd = 1e12;
    for (const n of list) {
      if (!n.ready() || (n === this.avoid && this.avoidT > 0)) continue;
      if (this.type === 'hunter' ? (n.targetedBy && n.targetedBy !== this) : (n.reservedBy && n.reservedBy !== this)) continue;
      const d = gdist(this.x, this.y, n.x, n.y) + (this.type === 'hunter' ? 0 : gdist(n.x, n.y, this.station.inPad.x, this.station.inPad.y) * 0.35);
      if (d < bd) { bd = d; best = n; }
    }
    if (!best) return null;
    if (this.type === 'hunter') best.targetedBy = this; else best.reservedBy = this;
    best.standPoint(this.x, this.y, this.stand);
    return best;
  }

  update(dt) {
    const gs = this.gs;
    if (this.role === 'porter') { this.updatePorter(dt); this.sync(dt); return; }
    if (this.avoidT > 0) this.avoidT -= dt;
    if (this.state === 'goto') {
      this.gotoT = (this.gotoT || 0) + dt;
      if (this.gotoT > 7 && this.node && this.type !== 'fisherman') {
        // could not reach it: try something else for a while
        this.avoid = this.node; this.avoidT = 15;
        this.release(); this.state = 'seek';
      }
    } else this.gotoT = 0;
    switch (this.state) {
      case 'seek': {
        if (this.room <= 0) { this.state = 'deliver'; break; }
        this.node = this.pickNode();
        if (this.node) { this.state = 'goto'; }
        else if (this.stack.count > 0) this.state = 'deliver';
        else {
          // nothing to do: wait at home
          this.waitT -= dt;
          if (gs.moveAgent(this, this.home[0], this.home[1], this.speed * 0.7, dt, 10)) {
            this.vx = this.vy = 0;
            if (this.dir !== 2) { this.dir = 2; this.play(this.animName, true); }
            this.locomotion(false);
          }
          if (this.waitT <= 0) this.waitT = 0.5;
        }
        break;
      }
      case 'goto': {
        const n = this.node;
        if (!n || !this.nodeOk(n)) { this.release(); this.state = 'seek'; break; }
        if (this.type === 'hunter') {
          // get within shooting range
          const d = gdist(this.x, this.y, n.x, n.y);
          if (d < BALANCE.workers.hunterRange) { this.vx = this.vy = 0; this.state = 'work'; this.cycles = 0; this.faceTo(n.x, n.y); this.play('work', true); break; }
          gs.moveAgent(this, n.x, n.y, this.speed, dt, 10);
          break;
        }
        if (gs.moveAgent(this, this.stand.x, this.stand.y, this.speed, dt, 8)) {
          this.vx = this.vy = 0;
          this.state = 'work'; this.cycles = 0;
          if (this.type === 'fisherman') this.dir = 5;   // cast up-left into the sea (side-on reads better than from behind)
          else this.faceTo(n.x, n.y);
          this.play('work', true);
        }
        break;
      }
      case 'work': {
        const n = this.node;
        this.vx = this.vy = 0;
        if (!n || !this.nodeOk(n) || this.room <= 0) {
          this.release();
          this.state = this.room <= 0 ? 'deliver' : 'seek';
          this.locomotion(false);
          break;
        }
        if (this.type === 'hunter') {
          if (gdist(this.x, this.y, n.x, n.y) > BALANCE.workers.hunterRange + 60) { this.state = 'goto'; break; }
          this.faceTo(n.x, n.y);
        }
        this.play('work');
        break;
      }
      case 'deliver': {
        const pad = this.station.inPad;
        if (this.stack.count + this.stack.incoming === 0) { this.state = 'seek'; break; }
        if (gs.moveAgent(this, pad.x + (this.index - 0.5) * 18, pad.y + 4, this.speed, dt, 10)) {
          this.vx = this.vy = 0;
          this.state = 'drop'; this.dropT = 0.15;
          this.locomotion(false);
        }
        break;
      }
      case 'drop': {
        this.vx = this.vy = 0;
        this.dropT -= dt;
        if (this.dropT <= 0) {
          this.dropT = 0.14;
          if (this.stack.count === 0) {
            if (this.stack.incoming === 0) { this.state = 'seek'; this.locomotion(false); }
            break;
          }
          if (!this.station.feedFrom(this)) {
            // station input full: wait patiently
            this.dropT = 0.6;
          }
        }
        this.locomotion(false);
        break;
      }
    }
    this.sync(dt);
  }

  impact() {
    if (this.state !== 'work' || !this.node) return;
    const gs = this.gs, n = this.node;
    let ip = this.impactPoint();
    if (this.type === 'fisherman') {
      // the line lands in the water, never on the snow in front of him
      ip = { x: ip.x - 10, y: Math.min(ip.y, shoreY(ip.x - 10) - 16) };
      if (gs.isOnScreen(ip.x, ip.y, 40)) gs.effects.sheet('fx_splash', ip.x, ip.y, { size: 70 });
      gs.effects.burst('splash', ip.x, ip.y, 3);
      gs.sfxAt('sfx_splash', this.x, this.y, { volume: 0.35, throttle: 200 });
    }
    if (this.type === 'hunter') { this.shoot(n, ip); return; }
    this.cycles++;
    if (this.cycles < (BALANCE.workers.cyclesPerItem[this.type] || 1)) return;
    this.cycles = 0;
    if (this.type === 'fisherman') {
      // a fish jumps out of the sea onto the stack (does not deplete the player's net)
      if (this.room > 0) { gs.spawnItemTo('item_fish_raw', ip.x, ip.y, this, false); gs.sfxAt('sfx_reel', this.x, this.y, { volume: 0.3, throttle: 300 }); }
      return;
    }
    const item = n.hit(this);
    if (item && this.room > 0) gs.spawnItemTo(item, ip.x, ip.y, this, false);
  }

  shoot(animal, ip) {
    const gs = this.gs;
    gs.sfxAt('sfx_bow', this.x, this.y, { volume: 0.6, throttle: 150 });
    const arrow = Assets.image(gs, ip.x, ip.y, 'projectile_arrow').setDepth(DEPTH.FLY);
    const sx = ip.x, sy = ip.y;
    const tgt = { x: animal.x, y: animal.y - 24 };
    const dist = Math.hypot(tgt.x - sx, tgt.y - sy);
    const dur = Math.max(160, dist * 1.4);
    let px = sx, py = sy;
    gs.tweens.addCounter({
      from: 0, to: 1, duration: dur,
      onUpdate: (tw) => {
        const p = tw.getValue();
        if (animal.ready()) { tgt.x = animal.x; tgt.y = animal.y - 24; }
        const x = sx + (tgt.x - sx) * p, y = sy + (tgt.y - sy) * p - Math.sin(p * Math.PI) * dist * 0.12;
        arrow.setPosition(x, y);
        arrow.setRotation(Math.atan2(y - py, x - px));
        px = x; py = y;
      },
      onComplete: () => {
        arrow.destroy();
        if (!animal.ready()) return;
        const item = animal.hit(this);
        if (item) {
          const cnt = animal.lastYield || 1;
          animal.lastYield = 0;
          for (let i = 0; i < cnt; i++) {
            if (this.room <= 0) break;
            gs.spawnItemTo(item, animal.x, animal.y - 20, this, false, i * 120);
          }
          this.release();
        }
      },
    });
  }
}
