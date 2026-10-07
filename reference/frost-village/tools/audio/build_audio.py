"""Frost Village - build every game sound: render -> encode (.ogg + .mp3) -> measure -> manifest.

Run from anywhere (takes ~1.5 min on 3 cores; deterministic, safe to re-run):
    python3 tools/audio/build_audio.py                    # render + encode + manifest + QA
    python3 tools/audio/build_audio.py --only sfx_coin,amb_sea   # re-render just these keys
    python3 tools/audio/build_audio.py --skip-render      # re-encode from tools/audio/_cache/*.wav
    python3 tools/audio/build_audio.py --no-check         # skip check_audio.py at the end
Outputs
    assets/audio/<key>.ogg  Vorbis q4, 44.1 kHz (mono sfx, stereo music/ambience)
    assets/audio/<key>.mp3  LAME CBR 128 kbps (music, ambience) / 96 kbps (sfx), gapless header
    assets/audio/manifest.json   CONTRACT section 2 fragment: audio{} + audioGroups{}
    docs/previews/audio_preview.html  listening page (open through the game's local web server)
Mix: every file is mastered hot (sfx peak -1.5 dBFS, music -18 LUFS, ambience -20/-21 LUFS) and the
per-key manifest `volume` brings it to its TARGET loudness, measured with ffmpeg ebur128 on the
decoded .ogg (integrated LUFS for loops, max momentary LUFS for sfx). Edit TARGET below to rebalance
without re-rendering:  python3 tools/audio/build_audio.py --skip-render
Needs numpy + scipy + ffmpeg (see deps.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deps  # noqa: E402

deps.ensure()
import ffmpeg_tools as F  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))           # frost-village/
CACHE = os.path.join(HERE, "_cache")
OUT = os.path.join(ROOT, "assets", "audio")
PREV = os.path.join(ROOT, "docs", "previews")

# ----------------------------------------------------------------------------- the sound list
# key: (kind, loop, target loudness (LUFS) at game call volume 1, before HEADROOM_DB, extra manifest fields)
#   music / ambience target = integrated LUFS ; sfx target = max momentary LUFS (400 ms)
#   Game call sites multiply on top (e.g. footsteps x0.32, station sfx x0.45).
SOUNDS = {
    "bgm_village":        ("music", True, -24.5, {"bars": 32}),
    "bgm_title":          ("music", True, -23.5, {"bars": 8}),
    "amb_wind":           ("ambience", True, -32.5, {}),
    "amb_sea":            ("ambience", True, -31.5, {}),
    "amb_fire":           ("ambience", True, -31.0, {}),
    "sfx_chop_1":         ("sfx", False, -16.0, {}),
    "sfx_chop_2":         ("sfx", False, -16.0, {}),
    "sfx_chop_3":         ("sfx", False, -16.0, {}),
    "sfx_mine_1":         ("sfx", False, -16.0, {}),
    "sfx_mine_2":         ("sfx", False, -16.0, {}),
    "sfx_mine_3":         ("sfx", False, -16.0, {}),
    "sfx_harvest_1":      ("sfx", False, -17.0, {}),
    "sfx_harvest_2":      ("sfx", False, -17.0, {}),
    "sfx_splash":         ("sfx", False, -17.0, {}),
    "sfx_reel":           ("sfx", False, -18.0, {}),
    "sfx_bow":            ("sfx", False, -17.0, {}),
    "sfx_hit_animal":     ("sfx", False, -17.0, {}),
    "sfx_animal_deer":    ("sfx", False, -18.0, {}),
    "sfx_animal_boar":    ("sfx", False, -18.0, {}),
    "sfx_pickup":         ("sfx", False, -17.0, {"pitch": "C5", "pitchHz": 523.25}),
    "sfx_drop":           ("sfx", False, -18.0, {}),
    "sfx_coin":           ("sfx", False, -17.0, {}),
    "sfx_coins_many":     ("sfx", False, -16.0, {}),
    "sfx_cash":           ("sfx", False, -16.0, {}),
    "sfx_unlock":         ("sfx", False, -15.0, {}),
    "sfx_build":          ("sfx", False, -16.0, {}),
    "sfx_levelup":        ("sfx", False, -15.0, {}),
    "sfx_hire":           ("sfx", False, -15.0, {}),
    "sfx_click":          ("sfx", False, -18.0, {}),
    "sfx_error":          ("sfx", False, -17.0, {}),
    "sfx_whoosh":         ("sfx", False, -18.0, {}),
    "sfx_step_snow_1":    ("sfx", False, -17.5, {}),
    "sfx_step_snow_2":    ("sfx", False, -17.5, {}),
    "sfx_step_snow_3":    ("sfx", False, -17.5, {}),
    "sfx_saw":            ("sfx", False, -18.0, {}),
    "sfx_smelt":          ("sfx", False, -18.0, {}),
    "sfx_sizzle":         ("sfx", False, -19.0, {}),
    "sfx_oven":           ("sfx", False, -18.0, {}),
    "sfx_customer_happy": ("sfx", False, -17.0, {}),
    "sfx_pad_fill":       ("sfx", False, -20.0, {}),
    "sfx_complete":       ("sfx", False, -14.0, {}),
}
GROUPS = {
    "sfx_chop": ["sfx_chop_1", "sfx_chop_2", "sfx_chop_3"],
    "sfx_mine": ["sfx_mine_1", "sfx_mine_2", "sfx_mine_3"],
    "sfx_harvest": ["sfx_harvest_1", "sfx_harvest_2"],
    "sfx_step_snow": ["sfx_step_snow_1", "sfx_step_snow_2", "sfx_step_snow_3"],
}
MP3_KBPS = {"music": 128, "ambience": 80, "sfx": 96}
# Ambience beds are mono: the game decodes every loop to PCM up front, and three stereo 24 s beds
# cost ~23 MB of phone memory for width nobody hears under the music. Music stays stereo.
CHANNELS = {"music": 2, "ambience": 1, "sfx": 1}
OGG_Q = 4
PEAK_MAX = -1.0          # dBFS, decoded sample peak of every delivered file
HEADROOM_DB = -2.0       # global trim on every volume: WebAudio sums sources and hard-clips at 0 dBFS
VOL_MIN, VOL_MAX = 0.05, 1.0


# ----------------------------------------------------------------------------- render
LOOPS = {"bgm_village": ("music", "render_village"), "bgm_title": ("music", "render_title"),
         "amb_wind": ("ambience", "render_wind"), "amb_sea": ("ambience", "render_sea"),
         "amb_fire": ("ambience", "render_fire")}


def _render_loop(key: str, n):
    import importlib
    mod, fn = LOOPS[key]
    return getattr(importlib.import_module(mod), fn)(loop_samples=n)


def fit_loop(key: str, max_iter: int = 10):
    """Render a loop whose length lands exactly on a Vorbis block boundary.

    libvorbis pads the final block and marks the excess with an end-trim; Chromium's
    decodeAudioData ignores that trim and would play the padding (up to 23 ms of fading junk)
    at every loop. So: render, encode, read the block boundaries near the end, and use the
    boundary nearest to the nominal length as the loop length; repeat until the padding is 0.
      music    : the performance is rendered once; only the loop point moves (fold + master),
                 so the downbeat after the wrap shifts by a few ms at most;
      ambience : regenerated at the new length (everything is periodic in the loop length).
    Deterministic for a given libvorbis build."""
    import synth as S
    tmp_wav, tmp_ogg = os.path.join(CACHE, f"{key}.fit.wav"), os.path.join(CACHE, f"{key}.fit.ogg")
    mod_name, fn = LOOPS[key]
    import importlib
    mod = importlib.import_module(mod_name)
    if mod_name == "music":
        mix, meta0 = getattr(mod, fn)(premix_only=True)
        L0 = meta0["nominalSamples"]

        def make(n):
            n = n or L0
            meta = dict(meta0, loopSamples=n)
            return mod.finish(mix, n, meta0["target"]), meta
    else:
        L0 = None

        def make(n):
            return getattr(mod, fn)(loop_samples=n)
    n, tried = None, []
    try:
        for it in range(max_iter):
            x, meta = make(n)
            L = x.shape[1]
            L0 = L0 or L
            tried.append(L)
            S.write_wav(tmp_wav, x)
            F.encode_ogg(tmp_wav, tmp_ogg, 2, OGG_Q)
            tail = F.ogg_tail(tmp_ogg)
            if tail["discard"] == 0:
                meta.update(fitIterations=it, nominalSamples=L0)
                return x, meta
            bounds = [b for b in tail["bounds"] + [L + tail["discard"]] if b > 0 and b not in tried]
            if not bounds:
                break
            n = min(bounds, key=lambda c: abs(c - L0))
    finally:
        for p in (tmp_wav, tmp_ogg):
            if os.path.exists(p):
                os.remove(p)
    print(f"  WARNING {key}: could not land on a Vorbis block boundary (tried {tried})", flush=True)
    meta.update(fitIterations=-1, nominalSamples=L0)
    return x, meta


def _render_job(key: str) -> str:
    """Runs in a worker process: render one key (or one music/ambience piece) to _cache."""
    sys.path.insert(0, HERE)
    import synth as S
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    meta = {}
    if key in LOOPS:
        x, meta = fit_loop(key)
    else:
        import sfx
        x = sfx.render(key)
    S.write_wav(os.path.join(CACHE, f"{key}.wav"), x)
    with open(os.path.join(CACHE, f"{key}.json"), "w") as f:
        json.dump(meta, f)
    extra = f"  loop {meta['loopSamples']} smp (fit x{meta['fitIterations']})" if key in LOOPS else ""
    return f"  rendered {key:20s} {x.shape[-1] / S.SR:6.2f}s  ({time.time() - t0:4.1f}s){extra}"


def render(keys, workers: int):
    heavy = [k for k in keys if not k.startswith("sfx_")]
    light = [k for k in keys if k.startswith("sfx_")]
    order = sorted(heavy, key=lambda k: k != "bgm_village") + light       # long pole first
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for line in ex.map(_render_job, order):
            print(line, flush=True)


# ----------------------------------------------------------------------------- encode + measure
def _encode_one(key: str):
    kind = SOUNDS[key][0]
    src = os.path.join(CACHE, f"{key}.wav")
    if not os.path.exists(src):
        raise FileNotFoundError(f"{src} missing - run without --skip-render")
    ch = CHANNELS[kind]
    ogg, mp3 = os.path.join(OUT, f"{key}.ogg"), os.path.join(OUT, f"{key}.mp3")
    gain = 0.0
    for _ in range(4):                       # codecs can overshoot the source peak: trim if needed
        F.encode_ogg(src, ogg, ch, OGG_Q, gain)
        F.encode_mp3(src, mp3, ch, MP3_KBPS[kind], gain)
        m_ogg, m_mp3 = F.ebur128(ogg, ch), F.ebur128(mp3, ch)
        worst = max(m_ogg["peak"], m_mp3["peak"])
        if worst <= PEAK_MAX:
            break
        gain += PEAK_MAX - 0.15 - worst
    return key, {"ogg": m_ogg, "mp3": m_mp3, "trim_db": round(gain, 2), "channels": ch,
                 "duration": wav_seconds(src)}


def wav_seconds(path) -> float:
    """Exact length of a rendered _cache wav (header only)."""
    import struct
    with open(path, "rb") as f:
        raw = f.read(256)
    fmt = raw.find(b"fmt ")
    ch, sr, bits = struct.unpack("<H", raw[fmt + 10:fmt + 12])[0], struct.unpack("<I", raw[fmt + 12:fmt + 16])[0], \
        struct.unpack("<H", raw[fmt + 22:fmt + 24])[0]
    d = raw.find(b"data")
    size = struct.unpack("<I", raw[d + 4:d + 8])[0]
    return size / (ch * bits // 8) / sr


def encode_all(keys, workers: int):
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(_encode_one, keys))


# ----------------------------------------------------------------------------- manifest
def volume_for(key: str, meas) -> float:
    kind, _, target, _ = SOUNDS[key]
    level = meas["ogg"]["I"] if kind != "sfx" else meas["ogg"]["M"]
    v = 10 ** ((target + HEADROOM_DB - level) / 20.0)
    return round(min(VOL_MAX, max(VOL_MIN, v)), 3)


def write_manifest(meas):
    audio = {}
    for key, (kind, loop, target, extra) in SOUNDS.items():
        m = meas[key]
        entry = {"files": [f"audio/{key}.ogg", f"audio/{key}.mp3"], "volume": volume_for(key, m),
                 "loop": loop, "kind": kind, "duration": round(m["duration"], 4)}
        entry.update(extra)
        mp = os.path.join(CACHE, f"{key}.json")
        if loop and os.path.exists(mp):
            with open(mp) as f:
                meta = json.load(f)
            entry["loopSamples"] = meta.get("loopSamples")
            if "bpm" in meta:
                entry["bpm"] = round(meta["bpm"], 3)
        if loop:
            gl = F.mp3_gapless(os.path.join(OUT, f"{key}.mp3"))
            if gl:
                entry["mp3StartPad"] = gl[0] + 529        # only for decoders that ignore the LAME tag
        audio[key] = entry
    man = {"version": 1,
           "generator": "tools/audio/build_audio.py (procedural synthesis: music.py, ambience.py, sfx.py)",
           "audio": audio, "audioGroups": GROUPS}
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    return man


def load_measurements(keys):
    """Measurements for keys we did not re-encode this run (reads the existing files)."""
    out = {}
    for key in keys:
        ch = CHANNELS[SOUNDS[key][0]]
        ogg, mp3 = os.path.join(OUT, f"{key}.ogg"), os.path.join(OUT, f"{key}.mp3")
        src = os.path.join(CACHE, f"{key}.wav")
        out[key] = {"ogg": F.ebur128(ogg, ch), "mp3": F.ebur128(mp3, ch), "trim_db": 0.0, "channels": ch,
                    "duration": wav_seconds(src) if os.path.exists(src) else F.probe(ogg)["duration"]}
    return out


# ----------------------------------------------------------------------------- listening page
def write_preview_html(man):
    rows = {"music": [], "ambience": [], "sfx": []}
    for key, a in man["audio"].items():
        rows[a["kind"]].append((key, a))
    parts = []
    for kind, title in (("music", "배경음악 Music (loops)"), ("ambience", "환경음 Ambience (loops)"),
                        ("sfx", "효과음 Sound effects")):
        parts.append(f"<h2>{title}</h2><div class='grid'>")
        for key, a in rows[kind]:
            parts.append(
                f"<div class='card'><button data-key='{key}' data-vol='{a['volume']}' data-loop='{int(a['loop'])}'>"
                f"&#9654;</button><div><b>{key}</b><small>{a['duration']:.2f}s &middot; vol {a['volume']}"
                f"{' &middot; loop' if a['loop'] else ''}</small></div></div>")
        parts.append("</div>")
    html = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Frost Village Sounds</title>
<style>
:root{--bg:#F4F7FB;--card:#FFF8EC;--ink:#2B2F3A;--accent:#3D8BE0;--muted:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#1b2130;--card:#262e40;--ink:#eef2f8;--accent:#6aa9f0;--muted:#9aa3b2}}
body{margin:0;padding:16px;font:15px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
h1{font-size:22px;margin:4px 0 2px} h2{font-size:17px;margin:22px 0 8px} p{color:var(--muted);margin:4px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(230px,100%),1fr));gap:8px}
code{overflow-wrap:anywhere}
.card{display:flex;gap:10px;align-items:center;background:var(--card);border-radius:12px;padding:8px 10px}
.card b{display:block;font-size:14px} .card small{color:var(--muted)}
button{width:40px;height:40px;border-radius:50%;border:0;background:var(--accent);color:#fff;font-size:16px;cursor:pointer;flex:none}
button.on{background:#5CC86A} .bar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.bar button{width:auto;border-radius:10px;padding:0 14px;font-size:14px}
</style></head><body>
<h1>서리마을 개척기 &mdash; 사운드 미리듣기 (Frost Village sounds)</h1>
<p>버튼을 누르면 게임과 같은 기본 볼륨으로 재생됩니다 (반복음은 한 번 더 누르면 정지).
Each sound plays at its in-game base volume through Web Audio, like the game (loops are sample-accurate).
Open this page through the game's local web server (e.g. <code>http://localhost:8000/docs/previews/audio_preview.html</code>).</p>
<div class="bar"><button id="mix">&#9654; Mix test: village music + wind + random sfx</button><button id="stop">&#9632; Stop all</button></div>
""" + "\n".join(parts) + """
<script>
const BASE='../../assets/audio/'; let ctx=null; const bufs={}; const playing={};
const ogg=(()=>{try{return new Audio().canPlayType('audio/ogg; codecs="vorbis"')!==''}catch(e){return false}})();
function ac(){if(!ctx)ctx=new (window.AudioContext||window.webkitAudioContext)();if(ctx.state==='suspended')ctx.resume();return ctx}
async function load(k){if(bufs[k])return bufs[k];const r=await fetch(BASE+k+(ogg?'.ogg':'.mp3'));
 const ab=await r.arrayBuffer();bufs[k]=await new Promise((ok,no)=>ac().decodeAudioData(ab,ok,no));return bufs[k]}
async function play(k,vol,loop,btn){const c=ac();const b=await load(k);const s=c.createBufferSource();const g=c.createGain();
 s.buffer=b;s.loop=!!loop;g.gain.value=vol;s.connect(g).connect(c.destination);s.start();
 if(loop){playing[k]={s,btn};if(btn)btn.classList.add('on')}
 s.onended=()=>{if(btn)btn.classList.remove('on');if(playing[k]&&playing[k].s===s)delete playing[k]};return s}
function stop(k){const p=playing[k];if(p){try{p.s.stop()}catch(e){}if(p.btn)p.btn.classList.remove('on');delete playing[k]}}
function stopAll(){Object.keys(playing).forEach(stop);if(window._mixT){clearInterval(window._mixT);window._mixT=null}}
document.querySelectorAll('.card button').forEach(b=>b.onclick=()=>{const k=b.dataset.key;
 if(playing[k]){stop(k);return} play(k,+b.dataset.vol,b.dataset.loop==='1',b).catch(e=>alertMsg(e))});
function alertMsg(e){const p=document.createElement('p');p.textContent='Could not load audio ('+e+'). Open via http://, not file://';document.body.prepend(p)}
document.getElementById('stop').onclick=stopAll;
document.getElementById('mix').onclick=async()=>{stopAll();const vol=k=>+document.querySelector(`[data-key="${k}"]`).dataset.vol;
 await play('bgm_village',vol('bgm_village'),true,null);await play('amb_wind',vol('amb_wind')*0.6,true,null);
 const sfx=['sfx_chop_1','sfx_pickup','sfx_coin','sfx_step_snow_2','sfx_drop','sfx_mine_2','sfx_customer_happy','sfx_harvest_1','sfx_unlock'];
 let i=0;window._mixT=setInterval(()=>{const k=sfx[i++%sfx.length];play(k,vol(k),false,null)},900)};
</script></body></html>
"""
    os.makedirs(PREV, exist_ok=True)
    with open(os.path.join(PREV, "audio_preview.html"), "w") as f:
        f.write(html)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="comma-separated keys to (re)build")
    ap.add_argument("--skip-render", action="store_true", help="reuse tools/audio/_cache/*.wav")
    ap.add_argument("--no-check", action="store_true", help="do not run check_audio.py afterwards")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    keys = [k.strip() for k in a.only.split(",") if k.strip()] or list(SOUNDS)
    bad = [k for k in keys if k not in SOUNDS]
    if bad:
        sys.exit(f"unknown keys: {bad}")
    t0 = time.time()
    if not a.skip_render:
        print(f"[1/4] rendering {len(keys)} sounds ...", flush=True)
        render(keys, a.workers)
    print("[2/4] encoding ogg + mp3 ...", flush=True)
    meas = encode_all(keys, max(1, a.workers + 1))
    rest = [k for k in SOUNDS if k not in meas]
    if rest:
        meas.update(load_measurements(rest))
    print("[3/4] manifest ...", flush=True)
    man = write_manifest(meas)
    write_preview_html(man)
    print(f"  {'key':20s} {'dur':>6s} {'I':>6s} {'Mmax':>6s} {'peak':>6s} {'trim':>5s} {'vol':>6s}")
    for key in SOUNDS:
        m = meas[key]
        o = m["ogg"]
        print(f"  {key:20s} {m['duration']:6.2f} {o['I']:6.1f} {o['M']:6.1f} {max(o['peak'], m['mp3']['peak']):6.1f}"
              f" {m['trim_db']:5.1f} {man['audio'][key]['volume']:6.3f}")
    print(f"  done in {time.time() - t0:.0f}s -> {os.path.relpath(OUT, ROOT)}/manifest.json")
    if not a.no_check:
        print("[4/4] check_audio.py ...", flush=True)
        import check_audio
        sys.exit(check_audio.main([]))


if __name__ == "__main__":
    main()
