// 봄날의 행진 — 시제품 시작점.
import { Assets } from './core/assets.js';
import { Play } from './scenes/Play.js';

const MAX_DPR = 2;
export const Screen = { dpr: 1 };

function cssSize() { return { w: Math.max(320, window.innerWidth), h: Math.max(240, window.innerHeight) }; }

class Preload extends Phaser.Scene {
  constructor() { super('Preload'); }
  preload() {
    Assets.queueManifests(this.load);
  }
  create() {
    Assets.queueFiles(this);
    const txt = document.getElementById('sm-loading-txt');
    this.load.on('progress', (v) => { if (txt) txt.textContent = `불러오는 중… ${Math.round(v * 100)}%`; });
    this.load.once('complete', () => {
      Assets.makeAnims(this);
      Assets.makeGenerated(this);
      const el = document.getElementById('sm-loading');
      if (el) { el.classList.add('hide'); setTimeout(() => el.remove(), 400); }
      const perf = new URLSearchParams(location.search).get('perf') === '1';
      this.scene.start('Play', { perf });
    });
    this.load.start();
  }
}

const s = cssSize();
Screen.dpr = Math.min(MAX_DPR, window.devicePixelRatio || 1);
const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: Math.round(s.w * Screen.dpr),
  height: Math.round(s.h * Screen.dpr),
  backgroundColor: '#e8eef6',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  render: { antialias: true, roundPixels: false, powerPreference: 'high-performance' },
  input: { activePointers: 3 },
  fps: { target: 60 },
  disableContextMenu: true,
  banner: false,
  scene: [Preload, Play],
});
window.__SM = { game, Screen };

let rt = 0;
function onResize() {
  clearTimeout(rt);
  rt = setTimeout(() => {
    const c = cssSize();
    game.scale.resize(Math.round(c.w * Screen.dpr), Math.round(c.h * Screen.dpr));
    game.scale.refresh();
  }, 100);
}
window.addEventListener('resize', onResize);
window.addEventListener('orientationchange', onResize);
