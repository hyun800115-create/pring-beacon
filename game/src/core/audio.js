// 소리: 서리마을 효과음·배경음. 화면 가운데에서 멀수록 작게. (첫 터치 뒤부터 재생 — 브라우저 규칙)

const FILES = {
  build: 'sfx_build', complete: 'sfx_complete', click: 'sfx_click', error: 'sfx_error', drop: 'sfx_drop', pickup: 'sfx_pickup',
  saw: 'sfx_saw', chop: 'sfx_chop_1', mine: 'sfx_mine_1', harvest: 'sfx_harvest_1', oven: 'sfx_oven', coin: 'sfx_coin',
};

export class Audio {
  constructor(stage) {
    this.stage = stage;
    this.ctx = null; this.buf = {}; this.on = true; this.unlocked = false;
    const unlock = () => {
      if (this.unlocked) return;
      this.unlocked = true;
      try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); this.load(); } catch (e) { this.ctx = null; }
    };
    window.addEventListener('pointerdown', unlock, { once: false });
    window.addEventListener('keydown', unlock, { once: false });
  }
  ext() { const a = document.createElement('audio'); return a.canPlayType('audio/ogg; codecs="vorbis"') ? 'ogg' : 'mp3'; }
  async load() {
    const e = this.ext();
    const all = Object.assign({ bgm: 'bgm_village' }, FILES);
    await Promise.all(Object.entries(all).map(async ([k, f]) => {
      try { const r = await fetch(`assets/audio/${f}.${e}`); const ab = await r.arrayBuffer(); this.buf[k] = await this.ctx.decodeAudioData(ab); } catch (err) { /* 소리 없음 */ }
    }));
    this.music();
  }
  music() {
    if (!this.ctx || !this.buf.bgm || this.bgm) return;
    const s = this.ctx.createBufferSource(); s.buffer = this.buf.bgm; s.loop = true;
    const g = this.ctx.createGain(); g.gain.value = 0.18;
    s.connect(g).connect(this.ctx.destination); s.start();
    this.bgm = { s, g };
  }
  setOn(v) { this.on = v; if (this.bgm) this.bgm.g.gain.value = v ? 0.18 : 0; }
  play(name, vol = 1, x, z) {
    if (!this.on || !this.ctx || !this.buf[name]) return;
    let v = vol;
    if (x != null) {
      const r = this.stage.rig, d = Math.hypot(x - r.tx, z - r.tz);
      v *= Math.max(0, 1 - d / (r.dist * 1.3)) * Math.max(0.25, 1 - r.dist / 160);
      if (v < 0.02) return;
    }
    const s = this.ctx.createBufferSource(); s.buffer = this.buf[name];
    s.playbackRate.value = 0.94 + Math.random() * 0.12;
    const g = this.ctx.createGain(); g.gain.value = v * 0.6;
    s.connect(g).connect(this.ctx.destination); s.start();
  }
}
