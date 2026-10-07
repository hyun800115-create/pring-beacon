// Frost Village (서리마을 개척기) — entry point.
import { Boot } from './scenes/Boot.js';
import { Preload } from './scenes/Preload.js';
import { Title } from './scenes/Title.js';
import { Game } from './scenes/Game.js';
import { UI } from './scenes/UI.js';
import { View, MAX_RENDER_SCALE } from './core/View.js';
import { checkBalance } from './data/balanceCheck.js';

const W = 720;
const MIN_H = 1280, MAX_H = 1600;

// Logical width is always 720. The logical height follows the device's aspect ratio
// (1280 .. 1600) so tall phones are filled instead of letter-boxed; Scale.FIT then fits it.
function logicalHeight() {
  const iw = window.innerWidth || W, ih = window.innerHeight || MIN_H;
  const h = Math.round((W * ih) / Math.max(1, iw));
  return Math.max(MIN_H, Math.min(MAX_H, h));
}

function cssInset(name) {
  try { return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)) || 0; } catch (e) { return 0; }
}

/** logical size, render scale (device pixels per logical pixel) and safe-area insets */
function updateView() {
  const h = logicalHeight();
  const iw = window.innerWidth || W, ih = window.innerHeight || h;
  const cssW = Math.max(1, Math.min(iw, (ih * W) / h));          // CSS width of the fitted canvas
  const dpr = window.devicePixelRatio || 1;
  View.W = W; View.H = h;
  View.k = View.forceK || Math.round(Math.max(1, Math.min(MAX_RENDER_SCALE, (cssW * dpr) / W)) * 20) / 20;
  const perCss = W / cssW;                                        // logical px per CSS px
  View.safeTop = cssInset('--sat') * perCss;
  View.safeBottom = cssInset('--sab') * perCss;
}

checkBalance();
updateView();

const params = new URLSearchParams(window.location.search);
window.__FV_DEBUG = params.get('debug') === '1';

const config = {
  type: Phaser.AUTO,
  parent: 'game',
  width: Math.round(View.W * View.k),
  height: Math.round(View.H * View.k),
  backgroundColor: '#dbe6f2',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  render: { antialias: true, pixelArt: false, roundPixels: false, powerPreference: 'high-performance' },
  input: { activePointers: 3, keyboard: true, windowEvents: true },
  audio: { disableWebAudio: false },
  fps: { target: 60, smoothStep: true },
  disableContextMenu: true,
  banner: false,
  scene: [Boot, Preload, Title, Game, UI],
};

const game = new Phaser.Game(config);
window.__FV_BOOTED = true;

let resizeTimer = 0;
function onResize() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    updateView();
    const gw = Math.round(View.W * View.k), gh = Math.round(View.H * View.k);
    const gs = game.scale.gameSize;
    if (Math.abs(gs.width - gw) > 1 || Math.abs(gs.height - gh) > 2) game.scale.setGameSize(gw, gh);
    game.scale.refresh();
  }, 120);
}
window.addEventListener('resize', onResize);
window.addEventListener('orientationchange', onResize);

// Weak GPU: if the village runs below ~30 fps at the sharper render scale, drop to 1x for this session
// (checked a few times once the village is running; the first seconds are skipped: warm-up, decoding).
let perfChecks = 0;
const perfTimer = setInterval(() => {
  try {
    const loop = game.loop;
    if (!loop || !loop.running || document.visibilityState !== 'visible' || !game.scene.isActive('Game')) return;
    if (++perfChecks < 2) return;
    if (View.k > 1.05 && loop.actualFps < 30) { View.forceK = 1; onResize(); clearInterval(perfTimer); }
    if (perfChecks >= 5) clearInterval(perfTimer);
  } catch (e) { clearInterval(perfTimer); }
}, 3000);

// 120/144 Hz screens: cap the game at ~60-72 fps (same look, half the battery / GPU work).
// 60 and 90 Hz screens are left alone (a fixed limit would make 90 Hz judder at 45 fps).
setTimeout(() => {
  try {
    const loop = game.loop;
    if (!loop || !loop.running || loop.hasFpsLimit || !(loop.actualFps > 100)) return;
    loop.sleep();
    loop.fpsLimit = 80; loop.hasFpsLimit = true; loop._limitRate = 1000 / 80;
    loop.wake();
  } catch (e) { /* keep running unlimited */ }
}, 4000);

// minimal test hooks until the Game scene installs the full set
window.__FV = window.__FV || { game };
window.__FV.game = game;
