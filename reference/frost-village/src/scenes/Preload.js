// Preload: manifests first, then every atlas / image / sheet / audio file they list.
import { Assets } from '../core/Assets.js';
import { FONT, t } from '../data/strings.js';
import { Audio } from '../core/Audio.js';
import { View } from '../core/View.js';

export class Preload extends Phaser.Scene {
  constructor() { super('Preload'); }

  preload() {
    this.load.on('loaderror', (f) => Assets.onLoadError(f, this.load));
    Assets.queueManifests(this.load);
  }

  create() {
    const el = document.getElementById('fv-loading');
    if (el) { el.classList.add('hide'); setTimeout(() => el.remove(), 400); }
    View.applyUI(this.cameras.main);
    const W = View.W, H = View.H;
    this.cameras.main.setBackgroundColor('#dbe6f2');
    this.add.text(W / 2, H * 0.42, '❄', { resolution: 2, fontFamily: FONT, fontSize: '72px', color: '#3d8be0' }).setOrigin(0.5);
    this.add.text(W / 2, H * 0.5, t('title'), { resolution: 2, fontFamily: FONT, fontSize: '44px', fontStyle: '900', color: '#2b2f3a' }).setOrigin(0.5);
    const barW = 420;
    this.add.rectangle(W / 2, H * 0.58, barW + 8, 26, 0xffffff, 0.8).setStrokeStyle(3, 0x9fb3cc);
    const bar = this.add.rectangle(W / 2 - barW / 2, H * 0.58, 2, 18, 0x3d8be0).setOrigin(0, 0.5);
    const label = this.add.text(W / 2, H * 0.62, t('loading'), { resolution: 2, fontFamily: FONT, fontSize: '22px', fontStyle: '700', color: '#5d6b80' }).setOrigin(0.5, 0);

    Assets.mergeManifests(this.cache.json);
    // in-game music / ambience are loaded later by the Game scene (faster first screen)
    Assets.queueAssets(this.load, { musicFilter: (k) => !Assets.isDeferredAudio(k) });
    this.load.on('progress', (p) => { bar.width = Math.max(2, barW * p); });
    this.load.once('complete', () => {
      Assets.finalize(this.game);
      Audio.trimLoops();
      label.setText('');
      this.scene.start('Title');
    });
    this.load.start();
  }
}
