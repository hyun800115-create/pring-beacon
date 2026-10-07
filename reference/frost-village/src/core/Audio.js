// Audio: music / sfx / ambience with persisted mute toggles. Every call is a safe no-op
// when the audio file is missing, failed to decode or the context is still locked.

import { Assets } from './Assets.js';
import { Settings } from './Save.js';

export const Audio = {
  game: null,
  started: false,         // set after the first user tap
  musicKey: null,
  music: null,
  amb: {},                // key -> sound
  ambTarget: {},          // key -> target volume (0..1)
  lastPlay: new Map(),    // key -> time (throttle)
  lastVariant: {},

  init(game) { this.game = game; },

  exists(key) {
    const g = this.game;
    return !!(g && g.cache && g.cache.audio && g.cache.audio.exists(key));
  },

  get sm() { return this.game && this.game.sound; },

  /** called from the title tap (a user gesture) */
  start() {
    this.started = true;
    this.resume();
  },

  /** resume a suspended / interrupted context (iOS after a call or app switch); call from any user tap */
  resume() {
    try { const c = this.sm && this.sm.context; if (c && c.state !== 'running' && c.state !== 'closed') c.resume(); } catch (e) { /* ignore */ }
  },

  /** false while WebAudio is suspended (window blurred, iOS interruption): sounds started then would pile up */
  get live() {
    const sm = this.sm;
    if (!sm) return false;
    const c = sm.context;
    if (c && c.state !== 'running') return false;
    return !sm.locked;
  },

  baseVolume(key) { const d = Assets.audioDef(key); return d && d.volume !== undefined ? d.volume : 0.7; },

  /** play a one-shot sfx (or a random variant of an audioGroup) */
  play(key, opts) {
    if (!this.started || !Settings.data.sound || !this.live) return;
    if (opts && opts.volume !== undefined && opts.volume <= 0.001) return;
    let k = key;
    const grp = Assets.audioGroup(key);
    if (grp && grp.length) {
      let i = Math.floor(Math.random() * grp.length);
      if (grp.length > 1 && i === this.lastVariant[key]) i = (i + 1) % grp.length;
      this.lastVariant[key] = i;
      k = grp[i];
    }
    if (!this.exists(k)) return;
    const now = this.game.loop.time;
    const throttle = (opts && opts.throttle) || 35;
    const last = this.lastPlay.get(k) || -1e9;
    if (now - last < throttle) return;
    this.lastPlay.set(k, now);
    try {
      const vol = this.baseVolume(k) * ((opts && opts.volume) !== undefined ? opts.volume : 1);
      const cfg = { volume: vol };
      if (opts && opts.rate) cfg.rate = opts.rate;
      if (opts && opts.detune) cfg.detune = opts.detune;
      this.sm.play(k, cfg);
    } catch (e) { /* ignore */ }
  },

  playMusic(key) {
    if (this.musicKey === key && this.music) { this.applyMusic(); return; }
    this.stopMusic(900);
    this.musicKey = key;
    this.applyMusic();
  },

  applyMusic() {
    if (!this.started) return;
    const on = Settings.data.music;
    const key = this.musicKey;
    if (!key) return;
    if (!on) { if (this.music) { try { this.music.pause(); } catch (e) { /* */ } } return; }
    if (!this.exists(key)) return;
    try {
      if (!this.music) {
        this.music = this.sm.add(key, { loop: true, volume: 0 });
        this.music.play();
        this.fade(this.music, this.baseVolume(key), 1200);
      } else if (this.music.isPaused) this.music.resume();
      else if (!this.music.isPlaying) this.music.play();
    } catch (e) { /* ignore */ }
  },

  stopMusic(fadeMs = 0) {
    const m = this.music;
    this.music = null; this.musicKey = null;
    if (!m) return;
    if (fadeMs > 0) {
      try {
        const scene = this.game.scene.getScenes(true)[0];
        if (scene && scene.tweens) { scene.tweens.add({ targets: m, volume: 0, duration: fadeMs, onComplete: () => { try { m.stop(); m.destroy(); } catch (e) { /* */ } } }); return; }
      } catch (e) { /* fall through */ }
    }
    try { m.stop(); m.destroy(); } catch (e) { /* */ }
  },

  fade(snd, to, ms) {
    try {
      const scene = this.game.scene.getScenes(true)[0];
      if (scene && scene.tweens) scene.tweens.add({ targets: snd, volume: to, duration: ms });
      else snd.setVolume(to);
    } catch (e) { /* */ }
  },

  /** ambience loops; volume 0..1 relative to manifest volume. Follows the sound toggle. */
  setAmbience(key, vol) { this.ambTarget[key] = vol; },

  updateAmbience(dt) {
    if (!this.started) return;
    const on = Settings.data.sound;
    for (const key in this.ambTarget) {
      let s = this.amb[key];
      const target = on ? this.ambTarget[key] * this.baseVolume(key) : 0;
      if (!s) {
        if (target <= 0.001 || !this.exists(key) || !this.live) continue;
        try { s = this.sm.add(key, { loop: true, volume: 0 }); s.play(); this.amb[key] = s; } catch (e) { continue; }
      }
      const v = s.volume + (target - s.volume) * Math.min(1, dt * 2.5);
      try { s.setVolume(v); } catch (e) { /* */ }
    }
  },

  setSoundEnabled(on) {
    Settings.data.sound = !!on; Settings.save();
    // silence the ambience loops right away (their fade only runs while the village is not paused)
    if (!on) for (const k in this.amb) { try { this.amb[k].setVolume(0); } catch (e) { /* */ } }
  },
  setMusicEnabled(on) {
    Settings.data.music = !!on; Settings.save();
    this.applyMusic();
  },

  /**
   * Seamless loops: decoders that ignore the mp3 gapless header (some Safari versions) return the
   * encoder delay as silence at the start, which clicks at every loop. Cut decoded loops that are
   * longer than the manifest duration back to exactly [mp3StartPad, + duration).
   */
  trimLoops() {
    const g = this.game;
    try {
      const ctx = g && g.sound && g.sound.context;
      if (!ctx || !ctx.createBuffer) return;
      for (const key in Assets.m.audio) {
        const a = Assets.m.audio[key];
        if (!a || !a.loop || !a.duration || !g.cache.audio.exists(key)) continue;
        const buf = g.cache.audio.get(key);
        if (!buf || !buf.getChannelData || buf.__fvChecked) continue;
        const rate = buf.sampleRate, want = Math.round(a.duration * rate);
        if (buf.length > want + rate * 0.01) {
          const off = Math.min(buf.length - want, Math.round(((a.mp3StartPad || 0) * rate) / 44100));
          const out = ctx.createBuffer(buf.numberOfChannels, want, rate);
          for (let c = 0; c < buf.numberOfChannels; c++) out.getChannelData(c).set(buf.getChannelData(c).subarray(off, off + want));
          out.__fvChecked = true;
          g.cache.audio.add(key, out);
        } else buf.__fvChecked = true;
      }
    } catch (e) { /* keep the untrimmed buffers */ }
  },

  vibrate(ms) {
    try { if (Settings.data.sound && navigator.vibrate) navigator.vibrate(ms); } catch (e) { /* */ }
  },
};
