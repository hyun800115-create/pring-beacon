// Title screen: key art, logo, "탭하여 시작". The first tap unlocks audio (CONTRACT §9).
import { Assets } from '../core/Assets.js';
import { Audio } from '../core/Audio.js';
import { View } from '../core/View.js';
import { FONT, t } from '../data/strings.js';
import { DIR_BASE } from '../core/Iso.js';

export class Title extends Phaser.Scene {
  constructor() { super('Title'); }

  create() {
    View.applyUI(this.cameras.main);
    const W = View.W, H = View.H;
    this.cameras.main.setBackgroundColor('#cfe0f1');
    // backdrop (cover)
    const bg = Assets.image(this, W / 2, H / 2, 'ui_title_bg').setOrigin(0.5, 0.5);
    const bf = bg.frame;
    bg.setScale(Math.max(W / bf.realWidth, H / bf.realHeight));

    // the chief stands on the snow field in front of the village, the crew around him on the same ground
    const ground = H * 0.765;
    const crew = ['fisherman', 'lumberjack', 'farmer', 'miner', 'hunter'];
    const slots = [[-228, -14, 1.24], [-130, -42, 1.14], [130, -42, 1.14], [228, -14, 1.24], [160, 82, 1.32]];
    const order = [0, 1, 2, 3, 4];
    for (const i of order) {
      const k = crew[i], [dx, dy, sc] = slots[i];
      const x = W / 2 + dx, y = ground + dy;
      this.add.image(x, y + 2, 'fv_shadow').setDisplaySize(64 * sc, 22 * sc).setAlpha(0.85).setDepth(y - 1);
      const s = this.add.sprite(x, y, '__WHITE').setDepth(y);
      const def = Assets.charDef(k);
      s.setOrigin(def.anchor[0], def.anchor[1]).setScale(sc);
      const key = Assets.charAnim(k, 'idle', DIR_BASE[2]);
      const an = this.anims.get(key);
      s.play({ key, startFrame: an && an.frames.length ? i % an.frames.length : 0 });
      if (i === 4) s.setFlipX(true);
    }

    // key art: feet on the snow with a soft contact shadow, a gentle hop
    const art = Assets.image(this, W / 2, ground, 'portrait_player_512').setOrigin(0.5, 0.97);
    art.setScale(380 / Math.max(art.frame.realWidth, 1)).setDepth(ground + 1);
    const shadow = this.add.image(W / 2 + 4, ground - 2, 'fv_shadow').setDisplaySize(190, 46).setAlpha(0.95).setDepth(ground);
    this.tweens.add({ targets: art, y: ground - 12, duration: 900, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
    this.tweens.add({ targets: shadow, scaleX: shadow.scaleX * 0.88, scaleY: shadow.scaleY * 0.88, alpha: 0.7, duration: 900, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });

    // logo
    const top = H * 0.14 + View.safeTop;
    const title = this.add.text(W / 2, top, t('title'), {
      fontFamily: FONT, fontSize: '76px', fontStyle: '900', color: '#ffffff', stroke: '#2a64a8', strokeThickness: 14,
      shadow: { offsetX: 0, offsetY: 7, color: 'rgba(20,40,80,0.35)', blur: 6, fill: true, stroke: true }, resolution: 2,
    }).setOrigin(0.5).setDepth(5000);
    const sub = this.add.text(W / 2, top + 70, t('subtitle'), {
      fontFamily: FONT, fontSize: '30px', fontStyle: '800', color: '#2a64a8', stroke: '#ffffff', strokeThickness: 8, resolution: 2,
    }).setOrigin(0.5).setDepth(5000);
    title.setScale(0.6); sub.setAlpha(0);
    this.tweens.add({ targets: title, scale: 1, duration: 700, ease: 'Back.easeOut' });
    this.tweens.add({ targets: sub, alpha: 1, duration: 600, delay: 300 });

    // tap to start, on a soft pill so it reads over trees and snow
    const touch = !!(this.sys.game.device.input.touch);
    const tapY = H * 0.915 - View.safeBottom;
    const tapBox = this.add.container(W / 2, tapY).setDepth(5000);
    const tap = this.add.text(0, 0, t(touch ? 'tapToStart' : 'clickToStart'), {
      fontFamily: FONT, fontSize: '40px', fontStyle: '900', color: '#ffffff', stroke: '#2b2f3a', strokeThickness: 8, resolution: 2,
    }).setOrigin(0.5);
    const pill = this.add.graphics();
    const pw = tap.width + 80, ph = 78;
    pill.fillStyle(0x1f3354, 0.35); pill.fillRoundedRect(-pw / 2, -ph / 2 + 4, pw, ph, ph / 2);
    pill.fillStyle(0x2a64a8, 0.55); pill.fillRoundedRect(-pw / 2, -ph / 2, pw, ph, ph / 2);
    pill.lineStyle(3, 0xffffff, 0.6); pill.strokeRoundedRect(-pw / 2 + 1.5, -ph / 2 + 1.5, pw - 3, ph - 3, ph / 2 - 1.5);
    tapBox.add([pill, tap]);
    this.tweens.add({ targets: tapBox, scale: 1.06, alpha: 0.8, duration: 700, yoyo: true, repeat: -1, ease: 'Sine.easeInOut' });
    if (!touch) {
      this.add.text(W / 2, tapY + 66, t('pcHint'), { fontFamily: FONT, fontSize: '22px', fontStyle: '700', color: '#2b2f3a', stroke: '#ffffff', strokeThickness: 5, resolution: 2 }).setOrigin(0.5).setDepth(5000);
    }

    // snowfall
    const sf = Assets.sprite('fx_snowflake');
    const fr = this.textures.get(sf.tex).get(sf.frame);
    const base = 12 / Math.max(8, fr.width);
    const cfg = {
      x: { min: -20, max: W + 20 }, y: -20, lifespan: 9000, speedY: { min: 40, max: 110 }, speedX: { min: -25, max: 25 },
      scale: { min: base * 0.6, max: base * 1.4 }, alpha: { min: 0.6, max: 1 }, rotate: { min: 0, max: 360 }, frequency: 90, quantity: 1,
    };
    if (sf.frame !== undefined) cfg.frame = sf.frame;
    this.add.particles(0, 0, sf.tex, cfg).setDepth(6000);

    this.started = false;
    this.input.once('pointerdown', () => {
      if (this.started) return;
      this.started = true;
      Audio.start();
      Audio.play('sfx_click');
      Audio.playMusic('bgm_title');
      this.tweens.killTweensOf(tapBox);
      this.tweens.add({ targets: tapBox, scale: 1.4, alpha: 0, duration: 250 });
      this.time.delayedCall(180, () => Audio.play('sfx_whoosh', { volume: 0.6 }));
      this.cameras.main.fadeOut(450, 230, 240, 250);
      this.cameras.main.once('camerafadeoutcomplete', () => this.scene.start('Game'));
    });

    // rotation / resize: lay the title out again for the new size
    const onResize = () => { if (!this.started && this.sys.isActive()) this.scene.restart(); };
    this.scale.on('resize', onResize);
    this.events.once('shutdown', () => this.scale.off('resize', onResize));
    if (window.__FV) window.__FV.title = this;
  }
}
