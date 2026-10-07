// Multi-touch joystick ownership with synthetic TouchEvents (CDP cannot lift one finger of several).
import { newPage, bootToGame, launch, start, writeJSON } from './review_robust_lib.mjs';
const srv = await start(0, { prefix: '/fv/' });
const browser = await launch();
const { page, log } = await newPage(browser);
await bootToGame(page, srv.url + 'index.html');
const r = await page.evaluate(async () => {
  const g = window.__FV.game, ui = g.scene.getScene('UI'), gs = window.__FV.scene;
  gs.cameras.main.setVisible(false);
  const n = window.__FV.where('zone:plaza'); window.__FV.teleport(n.x, n.y + 120);
  const cv = g.canvas;
  const frames = (k) => new Promise((res) => { const f0 = g.loop.frame; const iv = setInterval(() => { if (g.loop.frame - f0 >= k) { clearInterval(iv); res(); } }, 16); });
  const pts = {};
  const mk = (id) => new Touch({ identifier: id, target: cv, clientX: pts[id][0], clientY: pts[id][1], pageX: pts[id][0], pageY: pts[id][1] });
  const fire = (type, changed) => { const touches = Object.keys(pts).map(Number).filter((i) => !(type === 'touchend' && changed.includes(i))).map(mk); const ev = new TouchEvent(type, { touches, targetTouches: touches, changedTouches: changed.map(mk), bubbles: true, cancelable: true }); cv.dispatchEvent(ev); if (type === 'touchend') changed.forEach((i) => delete pts[i]); };
  const joy = () => ({ knob: ui.joyKnob.visible, vx: Math.round(gs.player.vx), vy: Math.round(gs.player.vy) });
  const out = {};
  pts[1] = [120, 600]; fire('touchstart', [1]); pts[1] = [200, 600]; fire('touchmove', [1]); await frames(10);
  out.f1Right = joy();
  pts[2] = [300, 400]; fire('touchstart', [2]); pts[2] = [300, 250]; fire('touchmove', [2]); await frames(10);
  out.f2DragUp_joystickStaysWithF1 = joy();
  fire('touchend', [1]); await frames(10);
  out.f1Lifted_f2StillDown = joy();
  pts[2] = [300, 150]; fire('touchmove', [2]); await frames(10);
  out.f2MovesAlone = joy();
  fire('touchend', [2]); await frames(5);
  out.allUp = joy();
  // finger 2 lifts first, finger 1 keeps steering
  pts[1] = [120, 600]; fire('touchstart', [1]); pts[1] = [200, 600]; fire('touchmove', [1]);
  pts[2] = [300, 400]; fire('touchstart', [2]); fire('touchend', [2]); pts[1] = [200, 680]; fire('touchmove', [1]); await frames(10);
  out.f2TapWhileF1Steers = joy();
  fire('touchend', [1]); await frames(5);
  out.end = joy();
  return out;
});
r.errors = log.errors;
console.log(JSON.stringify(r));
writeJSON('multitouch.json', r);
await browser.close(); await srv.close();
