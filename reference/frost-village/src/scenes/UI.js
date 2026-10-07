// HUD overlay: coin counter, settings panel (sound / music / language / reset with in-game
// confirm), toasts, banners, objective text + off-screen indicator, floating joystick.

import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { Input, JOY_RADIUS } from '../core/Input.js';
import { Settings } from '../core/Save.js';
import { FONT, t, setLang, getLang, fmt } from '../data/strings.js';
import { panel } from '../core/Panel.js';
import { View } from '../core/View.js';

const TXT = (size, color = '#ffffff', stroke = '#2b2f3a', st = 7, weight = '900') => ({
  fontFamily: FONT, fontSize: size + 'px', fontStyle: weight, color, stroke, strokeThickness: st, resolution: 2,
});

export class UI extends Phaser.Scene {
  constructor() { super('UI'); }

  create() {
    this.ready = false;
    this.gs = this.scene.get('Game');
    View.applyUI(this.cameras.main);
    const W = View.W, H = View.H;
    this.W = W; this.H = H;
    this.displayCoins = this.gs.economy.coins;
    this.targetCoins = this.displayCoins;
    this.coinDelay = 0;
    this.panelOpen = false;

    // ---- coin HUD
    this.coinBar = panel(this, 0, 0, 'ui_coin_bar', 230, 74).setOrigin(0, 0.5);
    this.coinIcon = Assets.image(this, 0, 0, 'ui_icon_coin');
    this.coinIcon.setScale(64 / Math.max(this.coinIcon.frame.realWidth, 1)).setOrigin(0.5);
    this.coinIcon.__bs = this.coinIcon.scaleX;
    this.coinText = this.add.text(0, 0, '0', TXT(40)).setOrigin(0, 0.5);

    // ---- settings button
    this.setBtn = this.makeIconButton(0, 0, 'ui_icon_settings', 84, () => this.openSettings());

    // ---- objective
    this.objPanel = this.add.container(0, 0).setVisible(false);
    this.objBg = panel(this, 0, 0, 'ui_panel', 400, 62).setOrigin(0.5);
    this.objText = this.add.text(0, 1, '', TXT(26, '#2b2f3a', '#ffffff', 0, '800')).setOrigin(0.5);
    this.objPanel.add([this.objBg, this.objText]);
    this.objKey = null;

    // ---- off-screen indicator
    this.edge = Assets.image(this, 0, 0, 'ui_arrow').setVisible(false);
    this.edge.setScale(50 / Math.max(this.edge.frame.realWidth, 1)).setOrigin(0.5, 0.5);

    // ---- joystick
    this.joyBase = Assets.image(this, 0, 0, 'ui_joystick_base').setVisible(false).setAlpha(0.9);
    this.joyBase.setScale((JOY_RADIUS * 2.2) / Math.max(this.joyBase.frame.realWidth, 1));
    this.joyKnob = Assets.image(this, 0, 0, 'ui_joystick_knob').setVisible(false);
    this.joyKnob.setScale(84 / Math.max(this.joyKnob.frame.realWidth, 1));

    // ---- toast / banner
    this.toastBox = this.add.container(W / 2, H - 230).setVisible(false).setDepth(50);
    this.toastBg = panel(this, 0, 0, 'ui_panel', 300, 64).setOrigin(0.5).setTint(0x2b2f3a).setAlpha(0.88);
    this.toastText = this.add.text(0, 0, '', TXT(28, '#ffffff', '#2b2f3a', 0, '800')).setOrigin(0.5);
    this.toastBox.add([this.toastBg, this.toastText]);
    this.bannerBox = this.add.container(W / 2, H * 0.27).setVisible(false).setDepth(60);
    this.bannerBg = panel(this, 0, 0, 'ui_button_blue', 460, 104).setOrigin(0.5);
    this.bannerText = this.add.text(0, -4, '', TXT(50, '#ffffff', '#1f4f8f', 10)).setOrigin(0.5);
    this.bannerSub = this.add.text(0, 80, '', TXT(26, '#ffffff', '#1f3354', 6, '800')).setOrigin(0.5);
    this.bannerSubBg = this.add.graphics();   // soft dark pill so the subtitle reads over a busy village
    this.bannerBox.add([this.bannerBg, this.bannerText, this.bannerSubBg, this.bannerSub]);

    // coins flying to HUD
    this.flyPool = [];

    // ---- debug
    if (window.__FV_DEBUG) this.fps = this.add.text(12, 0, '', { fontFamily: 'monospace', fontSize: '20px', color: '#2b2f3a', backgroundColor: 'rgba(255,255,255,0.6)' }).setDepth(100);

    this.layout();
    this.scale.on('resize', this.onResize, this);
    this.events.once('shutdown', () => { this.ready = false; this.panelOpen = false; this.scale.off('resize', this.onResize, this); });

    // ---- input (joystick anywhere that is not a button)
    this.input.on('pointerdown', (p, over) => {
      Audio.resume();    // iOS: bring sound back after a call / app switch (needs a user gesture)
      if (this.panelOpen || (over && over.length)) return;
      Input.pointerDown(p);
    });
    this.input.on('pointermove', (p) => Input.pointerMove(p));
    // lifting the steering finger while another finger is down hands the joystick to that finger
    const up = (p) => {
      const mine = Input.joy.active && p.id === Input.joy.id;
      Input.pointerUp(p);
      if (!mine || this.panelOpen) return;
      const other = this.input.manager.pointers.find((q) => q && q !== p && q.isDown && q.id !== p.id);
      if (other) Input.pointerDown(other);
    };
    this.input.on('pointerup', up);
    this.input.on('pointerupoutside', up);
    this.input.on('gameout', () => Input.release());

    this.setCoins(this.gs.economy.coins, 0);
    this.ready = true;
  }

  onResize(gameSize) {
    this.W = View.W; this.H = View.H;
    this.cameras.main.setSize(gameSize.width, gameSize.height);
    View.applyUI(this.cameras.main);
    this.layout();
  }

  layout() {
    const W = this.W, H = this.H;
    const top = 62 + View.safeTop;
    this.coinBar.setPosition(26, top);
    this.coinIcon.setPosition(64, top);
    this.coinText.setPosition(104, top + 2);
    this.setBtn.setPosition(W - 62, top);
    this.objPanel.setPosition(W / 2, top + 88);
    this.toastBox.setPosition(W / 2, H - 230 - View.safeBottom);
    this.bannerBox.setPosition(W / 2, H * 0.27);
    if (this.fps) this.fps.setPosition(12, H - 34);
    if (this.panel) this.layoutPanel();
  }

  // ---------------------------------------------------------------- widgets
  makeIconButton(x, y, iconKey, size, onClick) {
    const c = this.add.container(x, y);
    const g = this.add.graphics();
    g.fillStyle(0x1f3354, 0.25); g.fillCircle(0, 5, size / 2);
    g.fillStyle(0xffffff, 0.95); g.fillCircle(0, 0, size / 2);
    g.lineStyle(4, 0xd7e3f2, 1); g.strokeCircle(0, 0, size / 2 - 2);
    const ic = Assets.image(this, 0, 0, iconKey).setOrigin(0.5);
    ic.setScale((size * 0.62) / Math.max(ic.frame.realWidth, 1));
    c.add([g, ic]);
    c.icon = ic;
    c.setSize(size, size);
    c.setInteractive({ useHandCursor: true });
    c.on('pointerdown', () => { this.tweens.add({ targets: c, scale: 0.88, duration: 70, yoyo: true }); Audio.play('sfx_click'); onClick(); });
    return c;
  }

  makeButton(x, y, w, h, style, label, onClick, size = 30) {
    const c = this.add.container(x, y);
    const bg = panel(this, 0, 0, 'ui_button_' + style, w, h).setOrigin(0.5);
    const tx = this.add.text(0, -3, label, style === 'gray' ? TXT(size, '#ffffff', '#4a5361', 6, '900') : TXT(size, '#ffffff', 'rgba(0,0,0,0.25)', 4, '900')).setOrigin(0.5);
    c.add([bg, tx]);
    c.bg = bg; c.text = tx;
    c.setSize(w, h);
    c.setInteractive({ useHandCursor: true });
    c.on('pointerdown', () => { this.tweens.add({ targets: c, scale: 0.94, duration: 70, yoyo: true }); Audio.play('sfx_click'); onClick(); });
    return c;
  }

  // ---------------------------------------------------------------- coins
  setCoins(v, delayMs) {
    this.targetCoins = v;
    if (delayMs) this.coinDelay = Math.max(this.coinDelay, delayMs / 1000);
    if (v < this.displayCoins) this.displayCoins = v;
  }

  worldToScreen(wx, wy) {
    const cam = this.gs.cameras.main;
    const v = cam.worldView;
    return { x: ((wx - v.x) * cam.zoom) / View.k, y: ((wy - v.y) * cam.zoom) / View.k };
  }

  coinFly(wx, wy, n) {
    const s = this.worldToScreen(wx, wy);
    const tx = this.coinIcon.x, ty = this.coinIcon.y;
    for (let i = 0; i < n; i++) {
      let c = this.flyPool.pop();
      if (!c) c = Assets.image(this, 0, 0, 'ui_icon_coin').setOrigin(0.5);
      c.setScale(40 / Math.max(c.frame.realWidth, 1)).setVisible(true).setAlpha(1).setDepth(40);
      const sx = s.x + (Math.random() - 0.5) * 40, sy = s.y + (Math.random() - 0.5) * 30;
      c.setPosition(sx, sy);
      const mx = sx + (Math.random() - 0.5) * 160, my = sy - 60 - Math.random() * 80;
      this.tweens.addCounter({
        from: 0, to: 1, duration: 520 + i * 40, delay: i * 45, ease: 'Sine.easeIn',
        onUpdate: (tw) => {
          const p = tw.getValue(), q = 1 - p;
          c.setPosition(q * q * sx + 2 * q * p * mx + p * p * tx, q * q * sy + 2 * q * p * my + p * p * ty);
        },
        onComplete: () => {
          c.setVisible(false); this.flyPool.push(c);
          this.popCoin();
          Audio.play('sfx_coin', { volume: 0.35, rate: 1 + Math.random() * 0.3, throttle: 45 });
        },
      });
    }
  }

  popCoin() {
    const ic = this.coinIcon;
    this.tweens.killTweensOf(ic);
    ic.setScale(ic.__bs * 1.25);
    this.tweens.add({ targets: ic, scale: ic.__bs, duration: 200, ease: 'Back.easeOut' });
  }

  // ---------------------------------------------------------------- messages
  toast(msg) {
    this.toastText.setText(msg);
    this.toastBg.setSize(Math.max(260, this.toastText.width + 70), 64);
    const b = this.toastBox;
    this.tweens.killTweensOf(b);
    b.setVisible(true).setAlpha(1).setScale(0.7);
    this.tweens.add({ targets: b, scale: 1, duration: 200, ease: 'Back.easeOut' });
    this.tweens.add({ targets: b, alpha: 0, delay: 1500, duration: 350, onComplete: () => b.setVisible(false) });
  }

  banner(msg, sub) {
    const b = this.bannerBox;
    this.bannerText.setText(msg);
    this.bannerSub.setText(sub || '');
    this.bannerBg.setSize(Math.max(360, this.bannerText.width + 90), 104);
    const g = this.bannerSubBg;
    g.clear();
    if (sub) {
      const w = this.bannerSub.width + 44, h = 50;
      g.fillStyle(0x1f3354, 0.62); g.fillRoundedRect(-w / 2, 80 - h / 2, w, h, h / 2);
    }
    this.tweens.killTweensOf(b);
    b.setVisible(true).setAlpha(1).setScale(0.3);
    this.tweens.add({ targets: b, scale: 1, duration: 420, ease: 'Back.easeOut' });
    this.tweens.add({ targets: b, alpha: 0, y: { from: this.H * 0.27, to: this.H * 0.25 }, delay: sub ? 3200 : 1700, duration: 400, onComplete: () => { b.setVisible(false); b.y = this.H * 0.27; } });
  }

  celebrate() {
    this.banner(t('villageComplete'), t('villageCompleteSub'));
    const sf = Assets.sprite('fx_star');
    const fr = this.textures.get(sf.tex).get(sf.frame);
    const base = 22 / Math.max(8, fr.width);
    const cfg = {
      x: { min: 0, max: this.W }, y: -30, lifespan: 3200, speedY: { min: 200, max: 420 }, speedX: { min: -80, max: 80 },
      scale: { min: base * 0.7, max: base * 1.3 }, rotate: { start: 0, end: 540 }, frequency: 25, quantity: 2,
      tint: [0xff6f91, 0x3d8be0, 0x5cc86a, 0xffc83d, 0xd9483b, 0xffffff], duration: 2600,
    };
    if (sf.frame !== undefined) cfg.frame = sf.frame;
    const e = this.add.particles(0, 0, sf.tex, cfg).setDepth(55);
    this.time.delayedCall(6500, () => e.destroy());
  }

  setObjective(key, tg, text) {
    this.objTarget = tg;
    if (key !== this.objKey) {
      this.objKey = key;
      this.objCustom = text || null;
      if (!key) { this.objPanel.setVisible(false); }
      else {
        this.objText.setText(text || t(key));
        this.objBg.setSize(this.objText.width + 60, 62);
        this.objPanel.setVisible(true).setScale(0.8);
        this.tweens.add({ targets: this.objPanel, scale: 1, duration: 220, ease: 'Back.easeOut' });
      }
    }
  }

  // ---------------------------------------------------------------- settings
  openSettings(instant) {
    if (this.panelOpen) return;
    this.panelOpen = true;
    Input.release();
    const W = this.W, H = this.H;
    const c = this.add.container(0, 0).setDepth(80);
    const dim = this.add.rectangle(W / 2, H / 2, W * 2, H * 2, 0x1b2638, 0.5).setInteractive();
    dim.on('pointerdown', () => {});
    const bg = panel(this, W / 2, H / 2, 'ui_panel', 560, 640).setOrigin(0.5);
    c.add([dim, bg]);
    this.panel = c; this.panelBg = bg; this.panelDim = dim;
    this.buildPanelContent(false);
    if (!instant) {
      c.setAlpha(0);
      this.tweens.add({ targets: c, alpha: 1, duration: 160 });
      bg.setScale(0.8);
      this.tweens.add({ targets: bg, scale: 1, duration: 240, ease: 'Back.easeOut' });
    }
    if (!this.gs.scene.isPaused()) this.gs.scene.pause();
  }

  buildPanelContent(confirm) {
    this.panelConfirm = confirm;
    if (this.panelItems) for (const o of this.panelItems) o.destroy();
    this.panelItems = [];
    const W = this.W, H = this.H, cx = W / 2, cy = H / 2;
    const add = (o) => { this.panel.add(o); this.panelItems.push(o); return o; };
    if (!confirm) {
      add(this.add.text(cx, cy - 262, t('settings'), TXT(44, '#2b2f3a', '#ffffff', 0, '900')).setOrigin(0.5));
      const row = (y, label, value, style, cb, icon) => {
        if (icon) { const ic = add(Assets.image(this, cx - 200, y, icon).setOrigin(0.5)); ic.setScale(54 / Math.max(ic.frame.realWidth, 1)); }
        add(this.add.text(cx - 160, y, label, TXT(32, '#2b2f3a', '#ffffff', 0, '800')).setOrigin(0, 0.5));
        add(this.makeButton(cx + 130, y, 200, 76, style, value, cb, 28));
      };
      const S = Settings.data;
      row(cy - 150, t('sound'), S.sound ? t('on') : t('off'), S.sound ? 'green' : 'gray', () => { Audio.setSoundEnabled(!S.sound); this.buildPanelContent(false); }, S.sound ? 'ui_icon_sound_on' : 'ui_icon_sound_off');
      row(cy - 50, t('music'), S.music ? t('on') : t('off'), S.music ? 'green' : 'gray', () => { Audio.setMusicEnabled(!S.music); this.buildPanelContent(false); }, S.music ? 'ui_icon_music_on' : 'ui_icon_music_off');
      // globe icon for the language row (drawn, there is no icon sprite for it)
      const gl = add(this.add.graphics());
      gl.fillStyle(0x3d8be0, 1); gl.fillCircle(cx - 200, cy + 50, 25);
      gl.lineStyle(3, 0xffffff, 0.95); gl.strokeCircle(cx - 200, cy + 50, 25);
      gl.strokeEllipse(cx - 200, cy + 50, 22, 50); gl.lineBetween(cx - 225, cy + 50, cx - 175, cy + 50);
      gl.lineBetween(cx - 221, cy + 37, cx - 179, cy + 37); gl.lineBetween(cx - 221, cy + 63, cx - 179, cy + 63);
      row(cy + 50, t('language'), t('langName'), 'blue', () => {
        const l = getLang() === 'ko' ? 'en' : 'ko';
        setLang(l); Settings.data.lang = l; Settings.save();
        this.onLanguage();
        this.buildPanelContent(false);
      });
      add(this.makeButton(cx, cy + 170, 380, 80, 'gray', t('reset'), () => this.buildPanelContent(true), 28));
      add(this.makeButton(cx, cy + 262, 260, 80, 'blue', t('close'), () => this.closeSettings(), 30));
    } else {
      add(this.add.text(cx, cy - 120, t('resetConfirm'), Object.assign(TXT(32, '#2b2f3a', '#ffffff', 0, '800'), { align: 'center', lineSpacing: 10 })).setOrigin(0.5));
      add(this.makeButton(cx, cy + 60, 360, 84, 'gray', t('yes'), () => { this.closeSettings(true); this.gs.resetProgress(); }, 30));
      add(this.makeButton(cx, cy + 160, 360, 84, 'green', t('no'), () => this.buildPanelContent(false), 30));
    }
    const close = add(this.makeIconButton(cx + 250, cy - 290, 'ui_icon_close', 70, () => this.closeSettings()));
    void close;
  }

  /** after a resize / rotation: rebuild the open settings panel around the new centre */
  layoutPanel() {
    if (!this.panelOpen || !this.panel) return;
    const confirm = !!this.panelConfirm;
    this.closeSettings(true, true);
    this.openSettings(true);
    if (confirm) this.buildPanelContent(true);
  }

  closeSettings(immediate, keepPaused) {
    if (!this.panelOpen) return;
    this.panelOpen = false;
    const c = this.panel;
    this.panel = null; this.panelItems = null;
    if (!keepPaused && this.gs.scene.isPaused()) this.gs.scene.resume();
    if (immediate) { c.destroy(); return; }
    this.tweens.add({ targets: c, alpha: 0, duration: 140, onComplete: () => c.destroy() });
  }

  onLanguage() {
    // refresh world texts that depend on the language
    const gs = this.gs;
    for (const id in gs.progress.pads) gs.progress.pads[id].refresh();
    for (const k in gs.progress.upPads) gs.progress.upPads[k].refresh();
    for (const id in gs.zones) { const z = gs.zones[id]; if (z.outline) z.outline.txt.setText(t(z.cfg.name)); }
    if (this.objKey) { this.objKey = null; }   // the tutorial re-sends the objective (re-translated) within 0.2 s
  }

  // ---------------------------------------------------------------- frame
  update(time, delta) {
    try { this.tick(time, delta); } catch (e) { if (!this._tickErr) { this._tickErr = true; console.error('[FrostVillage] UI error:', e); } }
  }

  tick(time, delta) {
    const dt = delta / 1000;
    // coin counter
    if (this.coinDelay > 0) this.coinDelay -= dt;
    else if (this.displayCoins !== this.targetCoins) {
      const diff = this.targetCoins - this.displayCoins;
      const step = Math.max(1, Math.ceil(Math.abs(diff) * Math.min(1, dt * 10)));
      this.displayCoins += Math.sign(diff) * Math.min(Math.abs(diff), step);
    }
    const s = fmt(this.displayCoins);
    if (this.coinText.text !== s) {
      this.coinText.setText(s);
      this.coinBar.setSize(Math.max(170, this.coinText.width + 128), 74);
    }
    // joystick
    const j = Input.joy;
    if (j.active && !this.panelOpen) {
      this.joyBase.setVisible(true).setPosition(j.bx, j.by);
      const dx = j.kx - j.bx, dy = j.ky - j.by, d = Math.hypot(dx, dy), m = Math.min(d, JOY_RADIUS);
      this.joyKnob.setVisible(true).setPosition(j.bx + (d ? (dx / d) * m : 0), j.by + (d ? (dy / d) * m : 0));
    } else { this.joyBase.setVisible(false); this.joyKnob.setVisible(false); }
    // objective edge indicator
    const tg = this.objTarget;
    if (tg && this.gs.tutorial && this.gs.tutorial.target) {
      const p = this.worldToScreen(tg.x, tg.y - (tg.h || 0) * 0.5);
      const M = 64;
      if (p.x < -10 || p.x > this.W + 10 || p.y < 120 || p.y > this.H + 10) {
        const cx = this.W / 2, cy = this.H / 2;
        const a = Math.atan2(p.y - cy, p.x - cx);
        const ex = Phaser.Math.Clamp(p.x, M, this.W - M), ey = Phaser.Math.Clamp(p.y, 150 + 40, this.H - M);
        const bob = Math.sin(time / 160) * 6;
        this.edge.setVisible(true).setPosition(ex - Math.cos(a) * bob, ey - Math.sin(a) * bob).setRotation(a - Math.PI / 2);
      } else this.edge.setVisible(false);
    } else this.edge.setVisible(false);
    if (this.fps) this.fps.setText('FPS ' + Math.round(this.game.loop.actualFps) + '  objs ' + this.gs.children.length);
  }
}
