"""Frost Village - background music by procedural synthesis (library + script).

  bgm_village : cosy winter-village loop, F major, 100 bpm, light swing, 32 bars (76.8 s)
                form A1 A2 B A3 (8 bars each), F-major-pentatonic hook "A C D - C A C -".
                A = F | Dm | Bb | C | F | Dm | Bb C | F      (I vi IV V)
                B = Bb | C | Am | Dm | Bb | C | Gm7 | C7     (IV V iii vi ... ii V7)
                marimba lead (A), ocarina lead (B), music-box / glockenspiel doubles,
                nylon-pluck off-beat "chk-a" comping, pizzicato bass, warm saw pad,
                soft kick on 1 & 3, brushed snare, shaker, sleigh bells.
  bgm_title   : warm music-box version of the hook with harp arpeggios, 84 bpm, 8 bars (22.9 s)

Both are rendered with a tail and the tail is folded back onto the loop start
(fold_loop), so reverb and ringing notes cross the loop point seamlessly; the bus
compressor and the limiter run circularly (they see the loop as a loop).

Run:   python3 tools/audio/music.py [village] [title]
       -> writes tools/audio/_cache/bgm_<name>.wav (32-bit float, stereo, -18 LUFS)
Normally called through build_audio.py.  Deterministic (fixed seeds).  Needs numpy + scipy.
Set FV_AUDIO_DEBUG=1 to print per-bus loudness.
"""
from __future__ import annotations

import os
import sys
from itertools import product

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps  # noqa: E402

deps.ensure()
import instruments as I  # noqa: E402
import synth as S  # noqa: E402
from synth import SR, n_of  # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")

# ----------------------------------------------------------------------------- score
# Melody: one string per bar, 8 eighth-note slots. NOTE = new note, '-' = hold, '.' = rest.
MEL_A = [
    "A4 C5 D5 -  C5 A4 C5 -",    # F     "mi sol la~ sol mi sol~"  (the hook)
    "D5 -  F5 D5 C5 -  A4 -",    # Dm
    "D5 C5 D5 -  F5 D5 C5 A4",   # Bb
    "G4 -  -  -  A4 G4 .  .",    # C     (question)
    "A4 C5 D5 -  C5 A4 C5 -",    # F     (hook again)
    "D5 -  F5 G5 F5 -  D5 -",    # Dm    (reaches higher)
    "D5 C5 A4 C5 D5 C5 A4 G4",   # Bb | C
    "F4 -  -  -  -  -  .  .",    # F     (answer)
]
MEL_A_TURN = "F4 -  -  -  .  .  F4 G4"   # last bar of the loop: pickup back into the hook
MEL_B = [
    "D5 -  F5 -  D5 C5 D5 -",    # Bb
    "C5 -  -  A4 C5 D5 C5 -",    # C
    "A4 -  C5 A4 G4 A4 C5 -",    # Am
    "D5 -  -  -  -  -  .  .",    # Dm
    "F5 -  G5 F5 D5 -  F5 -",    # Bb
    "G5 -  -  F5 D5 C5 D5 -",    # C
    "G4 -  A4 C5 D5 -  C5 -",    # Gm7
    "C5 -  -  -  A4 G4 .  .",    # C7
]
CH_A = [("F", "F"), ("Dm", "Dm"), ("Bb", "Bb"), ("C", "C"), ("F", "F"), ("Dm", "Dm"), ("Bb", "C"), ("F", "F")]
CH_A_TURN = ("F", "C7")
CH_B = [("Bb", "Bb"), ("C", "C"), ("Am", "Am"), ("Dm", "Dm"), ("Bb", "Bb"), ("C", "C"), ("Gm7", "Gm7"), ("C7", "C7")]

# chord -> (root pc, triad pcs, pad pcs (with colour tones))
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "Bb": 10}
CHORDS = {
    "F":   (5, [5, 9, 0], [5, 9, 0, 7]),      # F add9
    "Dm":  (2, [2, 5, 9], [2, 5, 9, 0]),      # Dm7
    "Bb":  (10, [10, 2, 5], [10, 2, 5, 9]),   # Bbmaj7
    "C":   (0, [0, 4, 7], [0, 4, 7, 2]),      # C add9
    "Am":  (9, [9, 0, 4], [9, 0, 4, 7]),      # Am7
    "Gm7": (7, [7, 10, 2, 5], [7, 10, 2, 5]),
    "C7":  (0, [0, 4, 7, 10], [0, 4, 10, 2]),  # C9 (no 5th)
}
COUNTER_A3 = [("C6", "A5"), ("D6", "F5"), ("D6", "F6"), ("E6", "G5"),
              ("C6", "A5"), ("D6", "A5"), ("D6", "E6"), ("F6", "E6")]


def parse_bar(s: str):
    """-> list of (start_8th, len_8ths, midi)."""
    toks = s.split()
    assert len(toks) == 8, s
    out = []
    for i, tk in enumerate(toks):
        if tk in "-.":
            if tk == "-" and out:
                st, ln, m = out[-1]
                if st + ln == i:
                    out[-1] = (st, ln + 1, m)
            continue
        out.append((i, 1, S.note(tk)))
    return out


def voice(pcs, prev, lo, hi):
    """Closest voicing of pitch classes within [lo, hi] to the previous voicing."""
    opts = []
    for pc in pcs:
        o = [m for m in range(lo, hi + 1) if m % 12 == pc]
        opts.append(o)
    best, bc = None, 1e9
    for combo in product(*opts):
        c = sorted(combo)
        if c[-1] - c[0] > 16:
            continue
        if prev is None:
            cost = abs(np.mean(c) - (lo + hi) / 2)
        else:
            pv = sorted(prev)
            if len(pv) == len(c):
                cost = sum(abs(a - b) for a, b in zip(c, pv))
            else:
                cost = abs(np.mean(c) - np.mean(pv)) * len(c)
        cost += 0.15 * (c[-1] - c[0])
        if cost < bc:
            bc, best = cost, c
    return best


def bass_note(pc, lo=36, hi=47):
    for m in range(lo, hi + 1):
        if m % 12 == pc:
            return m
    return lo


class Song:
    """Timing helper with swing; bar/beat -> seconds."""

    def __init__(self, bpm, swing=0.5, seed=1):
        self.beat = 60.0 / bpm
        self.swing = swing
        self.r = S.rng(seed)

    def t(self, bar, beat):
        b = bar * 4 + beat
        w = np.floor(b + 1e-9)
        f = b - w
        if f <= 0.5:
            f2 = f / 0.5 * self.swing
        else:
            f2 = self.swing + (f - 0.5) / 0.5 * (1 - self.swing)
        return (w + f2) * self.beat

    def hum(self, sd=0.004):
        return float(self.r.normal(0, sd))

    def vel(self, v, sd=0.05):
        return float(np.clip(v + self.r.normal(0, sd), 0.05, 1.0))


# ----------------------------------------------------------------------------- render helpers
def circ(fn, x, pre: int):
    """Run a causal stateful processor as if x were a loop (pre-roll with the loop's end)."""
    pre = min(pre, x.shape[-1])
    return fn(np.concatenate((x[..., -pre:], x), axis=-1))[..., pre:]


class Mixer:
    """Named stereo buses. Events humanised to before t=0 are moved to the end of the loop
    (t + loop) so fold_loop carries them across the loop point instead of cropping their attack."""

    def __init__(self, dur, loop=None):
        self.bus = {}
        self.dur = dur
        self.loop = loop

    def b(self, name):
        if name not in self.bus:
            self.bus[name] = S.Buf(self.dur)
        return self.bus[name]

    def add(self, name, t, sig, gain=1.0, p=0.0):
        if t < 0 and self.loop:
            t += self.loop
        self.b(name).add(t, sig, gain, p)


def premix(mx: Mixer, sends: dict, gains: dict, L: int, rt60=1.9, pad_bus=None, extra_tail=6.0):
    """Sum the buses (+ chorus on the pad, shared FDN reverb, master EQ) -> (2, L + tail), not yet looped."""
    total = L + n_of(extra_tail)
    dry = np.zeros((2, total))
    send = np.zeros((2, total))
    for name, buf in mx.bus.items():
        x = buf.get(total)
        if name == pad_bus:
            x = S.chorus(x, rate=0.27, depth_ms=3.0, base_ms=16.0, mix=0.55)
        g = gains.get(name, 1.0)
        if os.environ.get("FV_AUDIO_DEBUG"):
            print(f"   bus {name:7s} lufs {S.lufs(g * x[:, :L]):6.1f}  peak {S.db(S.peak(g * x)):6.1f}")
        dry += g * x
        send += g * sends.get(name, 0.0) * x
    wet = S.reverb(send, rt60=rt60, hf_rt60=0.75, predelay=0.022, lo_cut=180, hi_cut=6000)
    mix = dry + wet
    mix = S.hp(mix, 32, order=2)
    mix = S.shelf_lo(mix, 110, -2.5)
    mix = S.shelf_hi(mix, 8000, -1.0)     # keep a little winter sparkle (bells, shaker)
    mix = S.lp(mix, 15000)
    return mix


def finish(mix, L: int, target=-18.0):
    """Fold the tail onto the start at loop length L, circular bus compression, loudness, limiter.
    L may differ from the nominal bar length by a few hundred samples: build_audio.py picks the
    nearest Vorbis block boundary so browsers that ignore the Ogg end-trim still loop seamlessly
    (the downbeat after the loop point then lands <= ~12 ms early/late - inaudible)."""
    loop = S.fold_loop(mix, L)
    loop = circ(lambda z: S.compress(z, thr_db=-24, ratio=1.7, tau=0.12), loop, n_of(4.0))
    g = S.undb(target - S.lufs(loop))
    loop = loop * g
    loop = S.limiter(loop, -1.6, window_ms=6.0, circular=True)
    return loop


# ----------------------------------------------------------------------------- bgm_village
def render_village(seed=11, loop_samples=None, premix_only=False):
    """-> (stereo loop, meta). loop_samples: fold at this length instead of the nominal 32 bars.
    premix_only: return the un-looped mix (for build_audio.fit_loop, which then calls finish())."""
    bars = 32
    song = Song(100, swing=0.58, seed=seed)
    r = song.r
    L = n_of(bars * 4 * song.beat)
    mx = Mixer(L / SR + 8, loop=L / SR)

    # --- section plan
    sections = []  # (bar0, kind, melody bars, chord bars)
    sections.append((0, "A1", MEL_A, CH_A))
    sections.append((8, "A2", MEL_A, CH_A))
    sections.append((16, "B", MEL_B, CH_B))
    sections.append((24, "A3", MEL_A[:7] + [MEL_A_TURN], CH_A[:7] + [CH_A_TURN]))

    prev_tri, prev_pad = None, None
    for bar0, kind, mel, chs in sections:
        for i in range(8):
            bar = bar0 + i
            # ---------------- melody
            for st, ln, m in parse_bar(mel[i]):
                t0 = song.t(bar, st / 2) + song.hum(0.004)
                dur = song.t(bar, (st + ln) / 2) - song.t(bar, st / 2)
                accent = 0.85 if st % 2 == 0 else 0.7
                if kind == "B":
                    mx.add("oca", t0, I.ocarina(m, song.vel(0.8), dur * 0.96, r, vib=1.0 if ln >= 3 else 0.5), 0.42, -0.08)
                    if ln >= 4:  # soft marimba ghost on long notes
                        mx.add("mel", t0, I.marimba(m - 12, song.vel(0.35), r), 0.18, -0.25)
                else:
                    mx.add("mel", t0, I.marimba(m, song.vel(accent), r), 0.52, -0.12)
                    if kind in ("A2", "A3"):
                        mx.add("mbox", t0 + 0.004, I.musicbox(m + 12, song.vel(0.55 if kind == "A2" else 0.65), r),
                               0.20 if kind == "A2" else 0.24, -0.3)
            # ---------------- harmony
            for half in (0, 1):
                ch = chs[i][half]
                root, tri, padpcs = CHORDS[ch]
                tri_v = voice(tri[:3], prev_tri, 55, 70)
                prev_tri = tri_v
                pad_v = voice(padpcs, prev_pad, 52, 72)
                prev_pad = pad_v
                hb = half * 2  # beat offset
                same = chs[i][0] == chs[i][1]
                # pad: one chord per bar if both halves equal
                if half == 0 or not same:
                    pdur = song.beat * (4 if (same and half == 0) else 2)
                    pg = {"A1": 0.11, "A2": 0.14, "B": 0.24, "A3": 0.17}[kind]
                    mx.add("pad", song.t(bar, hb), I.pad_chord(pad_v, pdur * 1.02, r, cutoff=1100 if kind != "B" else 1400), pg)
                # bass
                bm = bass_note(root)
                fifth = bm + 7 if bm + 7 <= 50 else bm - 5
                if kind == "B":
                    if same:
                        if half == 0:
                            mx.add("bass", song.t(bar, 0) + song.hum(0.003), I.bass(bm, song.vel(0.85), song.beat * 1.8, r), 0.62)
                        else:
                            mx.add("bass", song.t(bar, 2) + song.hum(0.003), I.bass(fifth, song.vel(0.7), song.beat * 1.6, r), 0.55)
                    else:
                        mx.add("bass", song.t(bar, hb), I.bass(bm, song.vel(0.8), song.beat * 1.7, r), 0.6)
                else:
                    note1 = bm if (half == 0 or not same) else fifth
                    mx.add("bass", song.t(bar, hb) + song.hum(0.003), I.bass(note1, song.vel(0.85 if half == 0 else 0.72), song.beat * 0.85, r), 0.62)
                    # little walk on beat 2.5/4.5 every other bar
                    if half == 1 and i % 2 == 1 and kind in ("A2", "A3"):
                        mx.add("bass", song.t(bar, 3.5) + song.hum(0.003), I.bass(note1 + (2 if note1 < 44 else -2), song.vel(0.55), song.beat * 0.4, r), 0.5)
                # plucks
                if kind == "B":
                    arp = tri_v + [tri_v[0] + 12]
                    order = [0, 1, 2, 3, 2, 1, 2, 1]
                    for k in range(4):
                        tb = hb + k * 0.5
                        m = arp[order[(k + 4 * half) % 8]]
                        v = 0.62 if k % 2 == 0 else 0.48
                        mx.add("pluck", song.t(bar, tb) + song.hum(0.003), I.pluck(m, song.vel(v), r, t60=1.5, dur=song.beat * 0.9), 0.26,
                               0.35 if k % 2 else 0.15)
                else:
                    for tb, v in ((hb + 1.0, 0.72), (hb + 1.5, 0.5)):
                        tt = song.t(bar, tb) + song.hum(0.003)
                        vv = song.vel(v * (1.08 if kind == "A3" else 1.0))
                        for j, m in enumerate(tri_v):
                            mx.add("pluck", tt + j * 0.011, I.pluck(m, vv, r, t60=1.1, dur=song.beat * 0.32), 0.17,
                                   0.32 + 0.08 * (j - 1))
            # ---------------- counter melody (A3: glock)
            if kind == "A3":
                for half in (0, 1):
                    nm = COUNTER_A3[i][half]
                    mx.add("glock", song.t(bar, half * 2) + 0.006, I.glock(S.note(nm), song.vel(0.6), r), 0.11, 0.38)
            if kind == "B" and i % 2 == 1:  # music-box sparkle arpeggio
                root, tri, _ = CHORDS[chs[i][1]]
                v = voice(tri[:3], None, 79, 92)
                for k, m in enumerate(v + [v[0] + 12]):
                    mx.add("mbox", song.t(bar, 3.0 + k * 0.25), I.musicbox(m, song.vel(0.45), r), 0.12, 0.35)

            # ---------------- drums
            dr = "drm"
            if kind == "B":
                mx.add(dr, song.t(bar, 0), I.kick(song.vel(0.62), r), 0.5)
                if i % 2 == 1:
                    mx.add(dr, song.t(bar, 2.5), I.kick(song.vel(0.4), r), 0.45)
                for b in (1, 3):
                    mx.add("sleigh", song.t(bar, b) + song.hum(0.002), I.sleigh(song.vel(0.6), r), 0.1, -0.4)
                for k in range(8):
                    mx.add("shk", song.t(bar, k * 0.5) + song.hum(0.002), I.shaker(song.vel(0.55 if k % 2 else 0.32), r), 0.07, 0.45)
            else:
                mx.add(dr, song.t(bar, 0), I.kick(song.vel(0.72), r), 0.55)
                mx.add(dr, song.t(bar, 2), I.kick(song.vel(0.62), r), 0.5)
                if kind != "A1" and i % 2 == 1:
                    mx.add(dr, song.t(bar, 2.5), I.kick(song.vel(0.42), r), 0.45)
                if kind in ("A2", "A3"):
                    for b in (1, 3):
                        mx.add("snr", song.t(bar, b) + song.hum(0.002), I.snare_soft(song.vel(0.6), r), 0.2, 0.1)
                if kind == "A3":
                    for b in (1, 3):
                        mx.add("sleigh", song.t(bar, b) + 0.01, I.sleigh(song.vel(0.45), r), 0.06, -0.45)
                for k in range(8):
                    sv = 0.55 if k % 2 else 0.3
                    mx.add("shk", song.t(bar, k * 0.5) + song.hum(0.002), I.shaker(song.vel(sv), r), 0.075, 0.45)
            # ---------------- fills / transitions
            if bar in (7, 31):
                mx.add("wb", song.t(bar, 3.0), I.woodblock(84, 0.7, r), 0.16, 0.3)
                mx.add("wb", song.t(bar, 3.5), I.woodblock(79, 0.6, r), 0.15, 0.2)
            if bar == 15:
                for k, mm in enumerate((55, 52, 50, 47)):
                    mx.add("drm", song.t(bar, 2 + k * 0.5), I.tom(mm, 0.5 + 0.08 * k), 0.38, -0.2 + 0.13 * k)
                sw = I.cymbal_soft(0.5, 1.4, r, swell=True)
                mx.add("cym", song.t(16, 0) - len(sw) / SR, sw, 0.22, 0.0)
            if bar == 23:
                for k in range(4):
                    mx.add("snr", song.t(bar, 3 + k * 0.25), I.snare_soft(0.3 + 0.12 * k, r), 0.2, 0.1)
            if bar in (0, 16, 24):
                mx.add("cym", song.t(bar, 0), I.cymbal_soft(0.28, 1.6, r), 0.18, 0.25)

    sends = {"mel": 0.22, "mbox": 0.38, "glock": 0.42, "oca": 0.32, "pluck": 0.17, "bass": 0.03, "pad": 0.38,
             "drm": 0.05, "snr": 0.16, "shk": 0.1, "sleigh": 0.22, "wb": 0.22, "cym": 0.3}
    gains = {"oca": 0.55, "bass": 0.65, "drm": 0.66, "pluck": 2.0, "pad": 3.4, "snr": 1.95, "shk": 3.9,
             "sleigh": 2.6, "glock": 1.5, "wb": 1.3}
    mix = premix(mx, sends, gains, L, rt60=1.9, pad_bus="pad")
    meta = {"bpm": 100, "bars": bars, "loopSamples": L, "nominalSamples": L, "target": -18.0}
    if premix_only:
        return mix, meta
    meta["loopSamples"] = int(loop_samples or L)
    return finish(mix, meta["loopSamples"], -18.0), meta


# ----------------------------------------------------------------------------- bgm_title
def render_title(seed=23, loop_samples=None, premix_only=False):
    """Same interface as render_village."""
    bars = 8
    song = Song(84, swing=0.53, seed=seed)
    r = song.r
    L = n_of(bars * 4 * song.beat)
    mx = Mixer(L / SR + 8, loop=L / SR)
    mel = MEL_A[:7] + [MEL_A_TURN]
    chs = CH_A[:7] + [CH_A_TURN]
    prev_tri, prev_pad = None, None
    for i in range(bars):
        for st, ln, m in parse_bar(mel[i]):
            t0 = song.t(i, st / 2) + song.hum(0.004)
            dur = song.t(i, (st + ln) / 2) - song.t(i, st / 2)
            mx.add("mbox", t0, I.musicbox(m + 12, song.vel(0.78 if st % 2 == 0 else 0.62), r), 0.36, -0.15)
            if i >= 4:
                mx.add("oca", t0, I.ocarina(m, song.vel(0.6), dur * 0.95, r, vib=0.6), 0.16, 0.1)
        for half in (0, 1):
            ch = chs[i][half]
            root, tri, padpcs = CHORDS[ch]
            tri_v = voice(tri[:3], prev_tri, 53, 67)
            prev_tri = tri_v
            pad_v = voice(padpcs, prev_pad, 50, 70)
            prev_pad = pad_v
            same = chs[i][0] == chs[i][1]
            hb = half * 2
            if half == 0 or not same:
                pdur = song.beat * (4 if (same and half == 0) else 2)
                mx.add("pad", song.t(i, hb), I.pad_chord(pad_v, pdur * 1.02, r, cutoff=1000, attack=0.8), 0.24)
                bm = bass_note(root)
                mx.add("bass", song.t(i, hb), I.bass(bm, 0.7, pdur * 0.95, r), 0.5)
            # harp arpeggio, straight 8ths, upward
            arp = tri_v + [tri_v[0] + 12]
            for k in range(4):
                m = arp[(k + (2 if half else 0)) % 4]
                mx.add("pluck", song.t(i, hb + k * 0.5) + song.hum(0.003),
                       I.pluck(m, song.vel(0.55 if k == 0 else 0.42), r, t60=2.2, dur=song.beat * 1.6, bright=0.4), 0.22,
                       0.3 if k % 2 else -0.05)
        for b in (1, 3):
            mx.add("sleigh", song.t(i, b) + song.hum(0.002), I.sleigh(song.vel(0.5), r), 0.07, -0.4)
        if i % 2 == 0:
            mx.add("glock", song.t(i, 0) + 0.01, I.glock(S.note(COUNTER_A3[i][0]), 0.5, r), 0.09, 0.4)
        mx.add("kick", song.t(i, 0), I.kick(0.5, r), 0.35)
    sends = {"mbox": 0.45, "oca": 0.35, "pad": 0.4, "bass": 0.05, "pluck": 0.25, "sleigh": 0.3, "glock": 0.5, "kick": 0.05}
    gains = {"pad": 2.8, "pluck": 1.8, "sleigh": 2.8, "glock": 1.8, "kick": 0.75, "bass": 0.8, "oca": 0.9}
    mix = premix(mx, sends, gains, L, rt60=2.3, pad_bus="pad")
    meta = {"bpm": 84, "bars": bars, "loopSamples": L, "nominalSamples": L, "target": -18.0}
    if premix_only:
        return mix, meta
    meta["loopSamples"] = int(loop_samples or L)
    return finish(mix, meta["loopSamples"], -18.0), meta


def main(names):
    os.makedirs(CACHE, exist_ok=True)
    for nm in names:
        fn = {"village": render_village, "title": render_title}[nm]
        x, meta = fn()
        p = os.path.join(CACHE, f"bgm_{nm}.wav")
        S.write_wav(p, x)
        print(f"bgm_{nm}: {x.shape[1] / SR:.2f}s peak {S.db(S.peak(x)):.2f} dBFS  LUFS {S.lufs(x):.2f}  -> {p}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["village", "title"])
