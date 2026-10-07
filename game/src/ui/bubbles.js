// 주민 머리 위 말풍선과 감정 아이콘 (HTML 을 3D 위치에 맞춰 띄움). 감정 그림은 서리마을 emotes 아틀라스.

export class Bubbles {
  constructor(stage) {
    this.stage = stage;
    this.layer = document.createElement('div');
    this.layer.id = 'bubbles';
    document.body.appendChild(this.layer);
    this.list = [];
    this.frames = null;
    fetch('assets/emotes/emotes.json').then((r) => r.json()).then((j) => { this.frames = j.frames; this.sheet = j.meta && j.meta.size; }).catch(() => {});
  }

  emoteHtml(name) {
    const f = this.frames && this.frames[name];
    if (!f) return '';
    const fr = f.frame, sw = this.sheet ? this.sheet.w : 1024, sh = this.sheet ? this.sheet.h : 1024;
    const s = 46 / Math.max(fr.w, fr.h);
    return `<i class="em" style="width:${fr.w * s}px;height:${fr.h * s}px;background-size:${sw * s}px ${sh * s}px;background-position:-${fr.x * s}px -${fr.y * s}px"></i>`;
  }

  /** p: {x,y,z} 를 따라다니는 말풍선 */
  show(p, text, emote, secs = 2.4) {
    if (this.list.length > 9) { const old = this.list.shift(); old.el.remove(); }
    for (const b of this.list) if (b.p === p) { b.el.remove(); b.dead = true; }
    this.list = this.list.filter((b) => !b.dead);
    const el = document.createElement('div');
    el.className = 'bub' + (text ? '' : ' only');
    el.innerHTML = (emote ? this.emoteHtml(emote) : '') + (text ? `<span>${escape(text)}</span>` : '');
    this.layer.appendChild(el);
    this.list.push({ p, el, t: secs });
  }

  update(dt) {
    for (let i = this.list.length - 1; i >= 0; i--) {
      const b = this.list[i];
      b.t -= dt;
      if (b.t <= 0 || b.p.dead) { b.el.remove(); this.list.splice(i, 1); continue; }
      const s = this.stage.toScreen(b.p.x, (b.p.y || 0) + (b.p.headY || 1.55), b.p.z);
      if (!s.vis || b.p.hidden) { b.el.style.display = 'none'; continue; }
      b.el.style.display = '';
      b.el.style.transform = `translate(${s.x}px, ${s.y}px) translate(-50%, -100%)`;
      b.el.style.opacity = Math.min(1, b.t * 2);
    }
  }
}

function escape(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
