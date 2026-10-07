"""Frost Village - audio QA: verify assets/audio against CONTRACT section 8 and measure everything.

Run:  python3 tools/audio/check_audio.py [--no-png]        (exit code 1 if anything fails)
Checks
  * every CONTRACT section 8 key is in assets/audio/manifest.json with files [.ogg, .mp3] that
    exist and decode (44.1 kHz; stereo music, mono ambience + sfx), kind / loop / volume sane,
    audioGroups sfx_chop / sfx_mine / sfx_harvest / sfx_step_snow complete;
  * per file: duration, sample peak (<= -1 dBFS), true peak, integrated + max momentary LUFS
    (ffmpeg ebur128), DC offset; sfx: no leading silence, clean fade-out;
  * loops: duration inside DUR[key], decoded .ogg length == rendered loop length (sample exact),
    .ogg end padding == 0 (Chromium plays it), manifest loopSamples, no click at the wrap point
    (high-passed energy + 2nd-difference jump at the boundary vs. the rest of the file),
    level continuity across the wrap;
  * total payload <= 8 MB.
Writes docs/previews/audio_report.txt, audio_waveforms.png (labelled thumbnails of every key)
and audio_spectrograms.png (music + ambience loops).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deps  # noqa: E402

deps.ensure()
import numpy as np  # noqa: E402

import ffmpeg_tools as F  # noqa: E402
import synth as S  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
AUD = os.path.join(ROOT, "assets", "audio")
ASSETS = os.path.join(ROOT, "assets")
PREV = os.path.join(ROOT, "docs", "previews")
CACHE = os.path.join(HERE, "_cache")

# CONTRACT section 8, written out independently of build_audio.py on purpose.
CONTRACT = {
    "music": ["bgm_village", "bgm_title"],
    "ambience": ["amb_wind", "amb_sea", "amb_fire"],
    "sfx": ["sfx_chop_1", "sfx_chop_2", "sfx_chop_3", "sfx_mine_1", "sfx_mine_2", "sfx_mine_3",
            "sfx_harvest_1", "sfx_harvest_2", "sfx_splash", "sfx_reel", "sfx_bow", "sfx_hit_animal",
            "sfx_animal_deer", "sfx_animal_boar", "sfx_pickup", "sfx_drop", "sfx_coin", "sfx_coins_many",
            "sfx_cash", "sfx_unlock", "sfx_build", "sfx_levelup", "sfx_hire", "sfx_click", "sfx_error",
            "sfx_whoosh", "sfx_step_snow_1", "sfx_step_snow_2", "sfx_step_snow_3", "sfx_saw", "sfx_smelt",
            "sfx_sizzle", "sfx_oven", "sfx_customer_happy", "sfx_pad_fill", "sfx_complete"],
}
CONTRACT_GROUPS = {"sfx_chop": 3, "sfx_mine": 3, "sfx_harvest": 2, "sfx_step_snow": 3}
DUR = {"bgm_village": (60, 100), "bgm_title": (20, 30), "amb_wind": (15, 30), "amb_sea": (15, 30),
       "amb_fire": (15, 30)}
# Channel count each kind must ship with. Ambience beds are mono on purpose (build_audio.CHANNELS:
# the game pre-decodes loops to PCM, three stereo 24 s beds cost ~23 MB of phone memory).
WANT_CH = {"music": 2, "ambience": 1, "sfx": 1}
MAX_PAYLOAD = 8 * 1024 * 1024


def loop_metrics(x):
    """Click detector for a loop (ch, n): compare the wrap point with every other point of the file."""
    n = x.shape[1]
    hf = S.filt_circ(x, "hp", 5000.0, order=2)
    e = np.sum(hf ** 2, axis=0)
    w = 64
    cs = np.concatenate(([0.0], np.cumsum(np.concatenate((e, e[:w])))))
    win = (cs[w:w + n] - cs[:n]) / w                           # energy of the w samples starting at i
    b = win[(n - w // 2) % n]                                  # window centred on the wrap point
    hf_ratio = float(np.sqrt(b / max(np.percentile(win, 99.0), 1e-20)))
    d2 = np.abs(np.roll(x, 1, axis=1) * -2 + x + np.roll(x, 2, axis=1)).max(axis=0)   # circular 2nd diff
    k = np.arange(n)
    near = (k < 3)                                             # differences that straddle the wrap
    d2_ratio = float(d2[near].max() / max(np.percentile(d2, 99.9), 1e-12))
    m = S.n_of(0.05)
    lvl_end = S.db(np.sqrt(np.mean(x[:, -m:] ** 2)) + 1e-12)
    lvl_start = S.db(np.sqrt(np.mean(x[:, :m] ** 2)) + 1e-12)
    jump = float(np.max(np.abs(x[:, 0] - x[:, -1])))
    return {"hf_ratio": hf_ratio, "d2_ratio": d2_ratio, "lvl_jump_db": float(lvl_start - lvl_end), "wrap_jump": jump}


def waveforms_png(rows, path):
    from PIL import Image, ImageDraw

    import preview as P
    cols, tw, th, lh = 3, 400, 58, 30
    nrow = (len(rows) + cols - 1) // cols
    img = Image.new("RGB", (cols * (tw + 12) + 12, nrow * (th + lh + 10) + 46), P.BG)
    d = ImageDraw.Draw(img)
    d.text((12, 10), "Frost Village audio - waveforms (light = RMS, dark = peak; red lines = -1 dBFS; "
           "orange edges = seamless loop)", fill=P.TXT, font=P.font(15))
    colors = {"music": (255, 196, 92), "ambience": (130, 220, 170), "sfx": (120, 200, 255)}
    for i, r in enumerate(rows):
        cx, cy = 12 + (i % cols) * (tw + 12), 40 + (i // cols) * (th + lh + 10)
        d.text((cx, cy), r["key"], fill=P.TXT, font=P.font(13))
        loud = f"I {r['I']:.1f}" if r["kind"] != "sfx" else f"Mmax {r['M']:.1f}"
        d.text((cx, cy + 15), f"{r['dur']:.2f}s  {loud} LUFS  peak {r['peak']:.1f}  vol {r['vol']}",
               fill=(160, 170, 190), font=P.font(11))
        img.paste(P.waveform(r["x"], tw, th, colors[r["kind"]], loop_marks=r["loop"]), (cx, cy + lh))
    img.save(path)


def spectrograms_png(rows, path):
    """Music + ambience: one spectrogram strip per loop (for humans judging texture / arrangement)."""
    from PIL import Image, ImageDraw

    import preview as P
    loops = [r for r in rows if r["loop"]]
    w, h = 1200, 170
    img = Image.new("RGB", (w + 20, len(loops) * (h + 66) + 44), P.BG)
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Frost Village loops - spectrogram (40 Hz-12 kHz, log) + waveform; the loop wraps at the right edge",
           fill=P.TXT, font=P.font(15))
    for i, r in enumerate(loops):
        y = 40 + i * (h + 66)
        d.text((10, y), f"{r['key']}  {r['dur']:.2f}s  I {r['I']:.1f} LUFS  vol {r['vol']}", fill=P.TXT, font=P.font(13))
        img.paste(P.spectrogram(r["x"], w, h), (10, y + 18))
        img.paste(P.waveform(r["x"], w, 40, (255, 196, 92) if r["kind"] == "music" else (130, 220, 170), True),
                  (10, y + 20 + h))
    img.convert("P", palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    fails, warns, rows, lines = [], [], [], []

    def fail(msg):
        fails.append(msg)

    man_p = os.path.join(AUD, "manifest.json")
    try:
        with open(man_p) as f:
            man = json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: cannot read {man_p}: {e}")
        return 1
    audio, groups = man.get("audio", {}), man.get("audioGroups", {})
    if man.get("version") != 1:
        fail("manifest version != 1")

    # ---- keys / groups
    for kind, keys in CONTRACT.items():
        for k in keys:
            a = audio.get(k)
            if a is None:
                fail(f"{k}: missing from manifest")
                continue
            if a.get("kind") != kind:
                fail(f"{k}: kind {a.get('kind')} != {kind}")
            if bool(a.get("loop")) != (kind != "sfx"):
                fail(f"{k}: loop flag {a.get('loop')} wrong for {kind}")
            v = a.get("volume")
            if not isinstance(v, (int, float)) or not (0 < v <= 1):
                fail(f"{k}: volume {v} not in (0, 1]")
            files = a.get("files", [])
            if [os.path.splitext(f)[1] for f in files] != [".ogg", ".mp3"]:
                fail(f"{k}: files must be [ogg, mp3], got {files}")
    extra = sorted(set(audio) - {k for ks in CONTRACT.values() for k in ks})
    if extra:
        warns.append(f"extra keys (allowed): {extra}")
    for g, cnt in CONTRACT_GROUPS.items():
        members = groups.get(g)
        want = [f"{g}_{i}" for i in range(1, cnt + 1)]
        if members != want:
            fail(f"audioGroups.{g} = {members}, expected {want}")

    # ---- per file
    total = 0
    hdr = f"{'key':20s} {'fmt':4s} {'ch':>2s} {'dur s':>7s} {'peak':>6s} {'TP':>6s} {'I LUFS':>7s} {'Mmax':>6s} {'DC':>8s} {'kB':>6s}"
    lines.append(hdr)
    for kind, keys in CONTRACT.items():
        for k in keys:
            a = audio.get(k)
            if a is None:
                continue
            want_ch = WANT_CH[kind]
            decoded = {}
            for rel in a.get("files", []):
                p = os.path.join(ASSETS, rel)
                if not os.path.exists(p):
                    fail(f"{k}: file missing {rel}")
                    continue
                size = os.path.getsize(p)
                total += size
                info = F.probe(p)
                if info["sample_rate"] != 44100:
                    fail(f"{k}: {rel} sample rate {info['sample_rate']}")
                if info["channels"] != want_ch:
                    fail(f"{k}: {rel} has {info['channels']} ch, want {want_ch}")
                try:
                    x = F.decode(p, info["channels"])
                except Exception as e:  # noqa: BLE001
                    fail(f"{k}: {rel} does not decode: {e}")
                    continue
                m = F.ebur128(p, info["channels"])
                fmt = os.path.splitext(rel)[1][1:]
                decoded[fmt] = (x, m)
                dc = float(np.max(np.abs(x.mean(axis=1))))
                dur = x.shape[1] / 44100
                lines.append(f"{k:20s} {fmt:4s} {info['channels']:2d} {dur:7.3f} {m['peak']:6.1f} {m['tpk']:6.1f} "
                             f"{m['I']:7.1f} {m['M']:6.1f} {dc:8.5f} {size / 1024:6.1f}")
                if m["peak"] > -1.0:
                    fail(f"{k}: {fmt} sample peak {m['peak']:.2f} dBFS > -1")
                if dc > 0.002:
                    fail(f"{k}: {fmt} DC offset {dc:.4f}")
                if k in DUR and fmt == "ogg" and not (DUR[k][0] <= dur <= DUR[k][1]):   # DUR is keyed by sound key
                    fail(f"{k}: duration {dur:.1f}s outside {DUR[k]}")
                if kind == "sfx" and fmt == "ogg":
                    env = np.max(np.abs(x), axis=0)
                    pk = env.max()
                    lead = np.argmax(env > pk * 0.003) / 44100          # true silence (< -50 dB re peak)
                    if lead > 0.004:
                        fail(f"{k}: {lead * 1000:.1f} ms leading silence")
                    tail = np.sqrt(np.mean(x[:, -S.n_of(0.004):] ** 2)) / max(pk, 1e-9)
                    if tail > 0.02:
                        warns.append(f"{k}: tail not faded ({S.db(tail):.0f} dB re peak)")
                    if dur > 5.0:
                        warns.append(f"{k}: long sfx {dur:.1f}s")
            if "ogg" not in decoded:
                continue
            x, m = decoded["ogg"]
            if a.get("loop"):
                lm = loop_metrics(x)
                src = os.path.join(CACHE, f"{k}.wav")
                n_src = S.read_wav(src).shape[1] if os.path.exists(src) else None
                ok_len = n_src is None or n_src == x.shape[1]
                lines.append(f"{'':20s} loop: n={x.shape[1]} (render {n_src}) hf_ratio={lm['hf_ratio']:.2f} "
                             f"d2_ratio={lm['d2_ratio']:.2f} level_jump={lm['lvl_jump_db']:+.1f} dB "
                             f"wrap_jump={lm['wrap_jump']:.4f}")
                if not ok_len:
                    fail(f"{k}: decoded ogg length {x.shape[1]} != rendered loop {n_src} (loop would drift/gap)")
                tail = F.ogg_tail(os.path.join(ASSETS, a["files"][0]))
                lines.append(f"{'':20s} ogg end padding {tail['discard']} smp (must be 0: Chromium ignores the "
                             f"Vorbis end-trim); manifest loopSamples {a.get('loopSamples')}")
                if tail["discard"] != 0:
                    fail(f"{k}: ogg has {tail['discard']} samples of end padding -> gap at every loop in Chrome")
                if a.get("loopSamples") not in (None, x.shape[1]):
                    fail(f"{k}: manifest loopSamples {a.get('loopSamples')} != decoded {x.shape[1]}")
                if lm["hf_ratio"] > 1.0 or lm["d2_ratio"] > 1.0:
                    fail(f"{k}: possible click at loop point (hf {lm['hf_ratio']:.2f}, d2 {lm['d2_ratio']:.2f})")
                if "mp3" in decoded:
                    nm = decoded["mp3"][0].shape[1]
                    if nm != x.shape[1]:
                        warns.append(f"{k}: mp3 decodes to {nm} samples vs ogg {x.shape[1]} "
                                     f"({(nm - x.shape[1]) / 44.1:+.1f} ms) - mp3 loop is not sample exact")
            rows.append({"key": k, "kind": kind, "x": x, "dur": x.shape[1] / 44100, "I": m["I"], "M": m["M"],
                         "peak": max(m["peak"], decoded.get("mp3", (None, m))[1]["peak"]),
                         "vol": a.get("volume"), "loop": bool(a.get("loop"))})
    lines.append(f"total payload: {total / 1024 / 1024:.2f} MB (limit 8 MB)")
    if total > MAX_PAYLOAD:
        fail(f"payload {total / 1024 / 1024:.2f} MB > 8 MB")

    os.makedirs(PREV, exist_ok=True)
    report = "\n".join(lines + [""] + [f"WARN: {w}" for w in warns] + [f"FAIL: {f}" for f in fails] +
                       ["", "RESULT: " + ("FAIL" if fails else "OK")])
    with open(os.path.join(PREV, "audio_report.txt"), "w") as f:
        f.write(report + "\n")
    print(report)
    if "--no-png" not in argv and rows:
        waveforms_png(rows, os.path.join(PREV, "audio_waveforms.png"))
        spectrograms_png(rows, os.path.join(PREV, "audio_spectrograms.png"))
        print("wrote docs/previews/audio_waveforms.png, docs/previews/audio_spectrograms.png")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
