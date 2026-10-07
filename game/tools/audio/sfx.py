"""Frost Village - sound effects by procedural synthesis (library + script).

Every CONTRACT section 8 SFX key is a small layered design: a transient (click / crack),
a body (modal resonator, pitch-dropping thump, bell partials), a texture (noise sweeps,
granular crunch, bubbles) and optionally a short room reverb. Musical SFX (coin, unlock,
level-up, hire, complete ...) are in F major so they sit with the background music.
sfx_pickup is a bright pop whose settled pitch is exactly C5 (523.25 Hz) - the game raises
its playback rate as the carried stack grows.

Run:   python3 tools/audio/sfx.py [key ...]        (no key = all)
       -> tools/audio/_cache/<key>.wav  (mono 44.1 kHz float, trimmed, faded, peak -1.5 dBFS)
Normally called through build_audio.py.  Deterministic (each key has a fixed seed).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps  # noqa: E402

deps.ensure()
import numpy as np  # noqa: E402

import instruments as I  # noqa: E402
import synth as S  # noqa: E402
from synth import SR, TAU, n_of  # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")


# ============================================================================ helpers
class Mono:
    """Growable mono mix buffer: add(t_sec, signal, gain)."""

    def __init__(self, dur: float = 1.0):
        self.x = np.zeros(max(1, n_of(dur)))

    def add(self, t: float, sig, g: float = 1.0):
        sig = np.asarray(sig, dtype=float)
        i = n_of(max(0.0, t))
        need = i + len(sig)
        if need > len(self.x):
            self.x = np.concatenate((self.x, np.zeros(need - len(self.x))))
        self.x[i:need] += g * sig
        return self


def mix(*parts) -> np.ndarray:
    """Sum signals of different lengths: mix((sig, gain), (sig, gain), ...)."""
    n = max(len(p[0]) for p in parts)
    out = np.zeros(n)
    for sig, g in parts:
        out[:len(sig)] += g * np.asarray(sig, dtype=float)
    return out


def tax(n: int) -> np.ndarray:
    return np.arange(n) / SR


def blip(f0: float, f1: float, dur: float, tau_f: float, tau_a: float, attack: float = 0.0008,
         harm=()) -> np.ndarray:
    """Sine whose pitch glides exponentially from f0 to f1 (tau_f), exp amplitude decay (tau_a).
    harm = [(k, amp), ...] adds phase-locked harmonics."""
    n = n_of(dur)
    t = tax(n)
    f = f1 + (f0 - f1) * np.exp(-t / tau_f)
    p = S.phase(f, n)
    y = np.sin(TAU * p)
    for k, a in harm:
        y = y + a * np.sin(TAU * k * p)
    return y * S.env_exp(n, tau_a, attack)


def burst(r, dur: float, fc: float, q: float = 0.8, tau: float | None = None, kind: str = "bp",
          attack: float = 0.0004) -> np.ndarray:
    """Filtered noise burst with exponential decay (clicks, cracks, puffs)."""
    n = n_of(dur)
    x = S.filt(r.standard_normal(n), kind, fc, q)
    return x * S.env_exp(n, tau or dur / 4.0, attack)


def puff(r, dur: float, cutoff: float, pts) -> np.ndarray:
    """Low-passed noise with a piecewise envelope (soft 'poof' / 'fwoomp')."""
    n = n_of(dur)
    return S.lp(r.standard_normal(n), cutoff, order=2) * S.env_pts(pts, n)


def bubble(r, f0: float, dur: float = 0.05, rise: float = 0.7, tau: float | None = None) -> np.ndarray:
    """Minnaert bubble 'blup': sine with rising pitch and fast decay."""
    n = n_of(dur)
    t = tax(n)
    f = f0 * (1.0 + rise * t / dur)
    return np.sin(TAU * S.phase(f, n) + r.uniform(0, TAU)) * S.env_exp(n, tau or dur / 3.0, 0.0015)


def nsweep(r, dur: float, f0: float, f1: float, q: float, pts, mid: float | None = None) -> np.ndarray:
    """Band-pass noise whose centre sweeps f0 -> (mid ->) f1 exponentially (whooshes, swishes)."""
    n = n_of(dur)
    u = np.linspace(0.0, 1.0, n)
    if mid is None:
        fc = f0 * (f1 / f0) ** u
    else:
        fc = np.where(u < 0.5, f0 * (mid / f0) ** (2 * u), mid * (f1 / mid) ** (2 * u - 1))
    y = S.tv_filter(r.standard_normal(n), "bp", fc, q)
    return y * S.env_pts(pts, n)


def chime(f: float, t60: float = 0.5, bright: float = 1.0, r=None) -> np.ndarray:
    """Bright bell / coin chime (near-harmonic partials, upper ones decay faster)."""
    n = n_of(t60 * 0.9 + 0.02)
    modes = [(1.0, 1.0, t60), (2.0, 0.5 * bright, t60 * 0.6), (3.0, 0.22 * bright, t60 * 0.4),
             (4.2, 0.12 * bright, t60 * 0.25), (5.43, 0.07 * bright, t60 * 0.15), (1.003, 0.3, t60 * 0.9)]
    return S.modal(f, n, modes, r, fmax=12500.0, attack=0.0004)


def coin_hit(r, f: float, t60: float = 0.15) -> np.ndarray:
    """Small metal disc clink (inharmonic plate modes) for coin showers / jingles."""
    n = n_of(t60 * 0.9 + 0.01)
    modes = [(1.0, 1.0, t60), (1.506, 0.6, t60 * 0.7), (2.24, 0.45, t60 * 0.5), (2.98, 0.25, t60 * 0.35)]
    y = S.modal(f, n, modes, r, fmax=12500.0, attack=0.0003)
    y[:n_of(0.004)] += burst(r, 0.004, 6000, 1.0, tau=0.0006) * 0.4
    return y


def soft_square(m: float, dur: float, vel: float = 0.8, cutoff: float = 2600.0, bend: float = 0.0) -> np.ndarray:
    """Rounded chip-tune square (square + triangle through a low-pass), optional downward bend."""
    rel = 0.05
    n = n_of(dur + rel)
    t = tax(n)
    f = float(S.midi_hz(m)) * 2 ** (bend * np.clip(t / max(dur, 1e-3), 0, 1) / 12.0)
    x = 0.6 * S.square(f, n, 0.5) + 0.5 * S.tri(f, n)
    x = S.lp(x, cutoff, 0.7, order=2)
    return x * S.env_adsr(n, 0.004, 0.06, 0.7, rel, gate=dur) * vel


PENT_HI = [84, 86, 89, 91, 93, 96, 98, 101]   # C6 D6 F6 G6 A6 C7 D7 F7  (F-major pentatonic)


def sparkles(m: Mono, r, t0: float, count: int, spacing: float, gain: float = 0.22, decay: float = 7.0,
             notes=PENT_HI):
    """Twinkling music-box notes after a fanfare."""
    for k in range(count):
        tt = t0 + k * spacing + r.uniform(-0.25, 0.25) * spacing
        mm = int(r.choice(notes))
        m.add(tt, I.musicbox(mm, r.uniform(0.35, 0.7), r), gain * np.exp(-k / decay))


def room(x, rt60: float = 0.4, mix: float = 0.08, tail: float = 0.15, size: float = 0.55) -> np.ndarray:
    return I.verb_mono(x, rt60=rt60, mix=mix, tail=tail, predelay=0.006, size=size)


def smooth_noise(r, n: int, hz: float) -> np.ndarray:
    """Zero-mean, unit-std random wobble band-limited to ~hz."""
    w = S.lp(r.standard_normal(n + n_of(0.3)), hz, order=2)[n_of(0.3):]
    return w / max(np.std(w), 1e-9)


# ============================================================================ gathering
def sfx_chop(v: int):
    """Axe into a log: crack + chunky mid crunch + wooden 'tok' + low thump + splinters."""
    r = S.rng(100 + v)
    ps = {1: 1.0, 2: 0.89, 3: 1.13}[v]
    m = Mono(0.5)
    m.add(0, burst(r, 0.03, 2900 * ps, 0.9, tau=0.0035), 0.95)
    m.add(0, burst(r, 0.09, 1150 * ps, 1.4, tau=0.017), 0.95)
    m.add(0, burst(r, 0.06, 1900 * ps, 1.6, tau=0.009), 0.5)
    body = S.modal(345 * ps, n_of(0.3), [(1, 1, 0.21), (1.62, 0.65, 0.13), (2.43, 0.5, 0.08), (3.71, 0.3, 0.045),
                                          (5.2, 0.15, 0.03)], r, attack=0.0007)
    m.add(0.001, body, 0.85)
    m.add(0, blip(620 * ps, 290 * ps, 0.16, 0.016, 0.04), 0.6)
    m.add(0, blip(130, 80, 0.2, 0.035, 0.05, attack=0.002), 0.14)
    for _ in range(int(r.integers(4, 8))):
        m.add(r.uniform(0.012, 0.12), burst(r, 0.012, r.uniform(3500, 7500), 1.5, tau=0.0014), r.uniform(0.08, 0.25))
    return room(m.x, 0.35, 0.07, 0.12, 0.5)


def sfx_mine(v: int):
    """Pickaxe on ore rock: metallic tink + stone crack + thud + pebble debris + gravel rustle."""
    r = S.rng(200 + v)
    ps = {1: 1.0, 2: 1.12, 3: 0.9}[v]
    m = Mono(0.7)
    tink = S.modal(1850 * ps, n_of(0.45), [(1, 1, 0.32), (2.31, 0.55, 0.2), (3.73, 0.35, 0.12), (5.12, 0.18, 0.07),
                                            (0.53, 0.3, 0.1)], r, fmax=12000, attack=0.0003)
    m.add(0, tink, 0.42)
    m.add(0, burst(r, 0.05, 2300, 0.7, tau=0.0055), 1.0)
    m.add(0, burst(r, 0.12, 720 * ps, 1.0, tau=0.02), 0.5)
    m.add(0, blip(155, 85, 0.25, 0.03, 0.05, attack=0.0015), 0.6)
    t0 = 0.022
    for _ in range(14):
        t0 += r.exponential(0.026)
        if t0 > 0.42:
            break
        peb = burst(r, 0.016, r.uniform(1800, 5200), 2.5, tau=0.0022)
        m.add(t0, peb, 0.42 * np.exp(-t0 / 0.15) * r.uniform(0.4, 1.0))
    m.add(0.01, burst(r, 0.36, 2600, 0.6, tau=0.07, attack=0.01), 0.12)
    return room(m.x, 0.5, 0.1, 0.18, 0.6)


def sfx_harvest(v: int):
    """Sickle through wheat: rising swish + 'snip' + stalk rustle + tiny bright 'pip'."""
    r = S.rng(300 + v)
    m = Mono(0.6)
    d = 0.17
    f0, f1 = (900, 5200) if v == 1 else (1300, 3900)
    m.add(0, nsweep(r, d, f0, f1, 1.6, [(0, 0), (0.05, 1), (0.11, 0.5), (d, 0)]), 0.75)
    ts = 0.06 if v == 1 else 0.075
    m.add(ts, burst(r, 0.02, 5200, 1.2, tau=0.0025), 0.9)
    m.add(ts + 0.006, burst(r, 0.02, 3800, 1.2, tau=0.003), 0.6)
    for t0 in np.sort(r.uniform(0.06, 0.32, 46)):
        g = r.uniform(0.05, 0.3) * np.exp(-(t0 - 0.06) / 0.12)
        m.add(t0, burst(r, 0.01, r.uniform(2500, 7500), 1.5, tau=r.uniform(0.0008, 0.003)), g)
    m.add(ts + 0.004, blip(1400, 1900 if v == 1 else 1720, 0.1, 0.012, 0.026), 0.22)
    return room(m.x, 0.4, 0.08, 0.12, 0.5)


def sfx_splash():
    """Fish/water splash: plunge thud + slap + broadband body + spray + Minnaert bubbles."""
    r = S.rng(400)
    m = Mono(1.0)
    m.add(0, blip(260, 110, 0.2, 0.03, 0.05, attack=0.002), 0.5)
    m.add(0, burst(r, 0.06, 1800, 0.6, tau=0.012), 0.8)
    n = n_of(0.6)
    m.add(0.004, S.lp(S.hp(r.standard_normal(n), 600), 7000) *
          S.env_pts([(0, 0), (0.015, 1), (0.08, 0.55), (0.25, 0.18), (0.6, 0)], n), 0.5)
    m.add(0.02, S.hp(r.standard_normal(n), 3500) * S.env_pts([(0, 0), (0.03, 0.6), (0.15, 0.3), (0.5, 0)], n) ** 1.5,
          0.45)
    for _ in range(10):
        t0 = 0.04 + r.exponential(0.12)
        m.add(t0, bubble(r, r.uniform(650, 2000), r.uniform(0.03, 0.07), r.uniform(0.4, 1.0)),
              r.uniform(0.15, 0.35) * np.exp(-t0 / 0.4))
    for t0 in np.sort(0.12 + r.exponential(0.12, 14)):     # droplets falling back
        m.add(t0, burst(r, 0.01, r.uniform(2500, 6000), 2.0, tau=0.0015), 0.12 * np.exp(-t0 / 0.35))
    return room(m.x, 0.6, 0.12, 0.25, 0.7)


def sfx_reel():
    """Fishing-reel ratchet (slowing clicks) over a spool whirr, then a little 'plip'."""
    r = S.rng(500)
    m = Mono(0.8)
    dur = 0.42
    t, k = 0.0, 0
    while t < dur:
        rate = 34 - 12 * (t / dur)
        a = min(1.0, t / 0.04 + 0.2) * (1 - 0.45 * t / dur)
        clk = mix((burst(r, 0.006, 3600, 1.5, tau=0.0008), 1.0),
                  (S.modal(2500, n_of(0.02), [(1, 1, 0.015), (1.8, 0.5, 0.01)], r), 0.4))
        m.add(t, clk, a * (0.8 if k % 2 == 0 else 0.6))
        t += 1.0 / rate
        k += 1
    n = n_of(dur)
    hum = S.lp(S.saw(180 - 40 * np.linspace(0, 1, n), n), 900) * S.env_pts([(0, 0), (0.04, 1), (dur - 0.06, 0.7),
                                                                          (dur, 0)], n)
    m.add(0, hum, 0.12)
    m.add(dur, burst(r, 0.08, 1500, 0.7, tau=0.015), 0.25)
    m.add(dur + 0.02, bubble(r, 900, 0.06, 0.8), 0.4)
    return room(m.x, 0.4, 0.08, 0.15, 0.5)


def sfx_bow():
    """Bow release: string snap + low 'thwung' + arrow 'fwip'."""
    r = S.rng(600)
    m = Mono(0.6)
    m.add(0, burst(r, 0.01, 2400, 1.0, tau=0.0012), 0.8)
    tw = S.ks_pluck(150, 0.35, r, t60=0.28, bright=0.7, stretch=0.35, pick=0.1)
    m.add(0, tw / max(S.peak(tw), 1e-9), 0.55)
    m.add(0, blip(195, 140, 0.25, 0.02, 0.07), 0.45)
    m.add(0.012, nsweep(r, 0.2, 3200, 900, 2.2, [(0, 0), (0.02, 1), (0.08, 0.4), (0.2, 0)]), 0.6)
    return room(m.x, 0.4, 0.06, 0.12, 0.5)


def sfx_hit_animal():
    """Arrow hits an animal - soft, cartoony, non-violent: body thump + muffled thud + little 'bonk'."""
    r = S.rng(700)
    m = Mono(0.5)
    m.add(0, blip(300, 140, 0.22, 0.03, 0.055, attack=0.001), 0.6)
    m.add(0, burst(r, 0.08, 1100, 0.8, tau=0.018), 0.75)
    m.add(0, burst(r, 0.02, 2600, 1.2, tau=0.002), 0.4)
    m.add(0.006, blip(820, 460, 0.13, 0.025, 0.045, harm=[(2, 0.25)]), 0.6)
    m.add(0.01, puff(r, 0.2, 2500, [(0, 0), (0.02, 1), (0.2, 0)]) ** 1, 0.18)
    return room(m.x, 0.35, 0.06, 0.1, 0.5)


def sfx_animal_deer():
    """Cute fawn bleat 'meeh': formant voice with a 17 Hz bleat flutter."""
    r = S.rng(800)
    dur = 0.42
    n = n_of(dur)
    t = tax(n)
    f0 = S.env_pts([(0, 560), (0.06, 700), (0.16, 665), (0.32, 600), (dur, 520)], n)
    flut = 0.5 + 0.5 * np.sin(TAU * 17 * t)
    f0 = f0 * (1 + 0.025 * np.sin(TAU * 17 * t))
    amp = S.env_pts([(0, 0), (0.025, 1), (0.28, 0.8), (dur, 0)], n) * (1 - 0.32 * flut)
    F1 = S.env_pts([(0, 450), (0.05, 620), (dur, 560)], n)
    F2 = S.env_pts([(0, 2100), (0.05, 1850), (dur, 1700)], n)
    y = I.formant_voice(f0, amp, [(F1, 160, 1.0), (F2, 240, 0.6), (2900, 380, 0.25)], r,
                        breath=0.06, tilt=0.6, jitter=0.008)
    y = S.hp(y, 250)
    return room(y, 0.6, 0.1, 0.2, 0.7)


def _grunt(r, dur, fs, fp, fe, rough_hz=38.0):
    n = n_of(dur)
    t = tax(n)
    f0 = S.env_pts([(0, fs), (dur * 0.35, fp), (dur, fe)], n)
    am = 1 - 0.42 * (0.5 + 0.5 * np.sin(TAU * rough_hz * t))
    amp = S.env_pts([(0, 0), (0.018, 1), (dur * 0.6, 0.85), (dur, 0)], n) * am
    return I.formant_voice(f0, amp, [(520, 180, 1.0), (1250, 260, 0.75), (2600, 420, 0.25)], r,
                           breath=0.15, tilt=0.45, jitter=0.02)


def sfx_animal_boar():
    """Cute round boar: little snort then 'oink-oink' (nasal formant grunts with roughness)."""
    r = S.rng(900)
    m = Mono(0.8)
    m.add(0, burst(r, 0.09, 900, 1.5, tau=0.03, attack=0.012), 0.3)
    m.add(0.07, _grunt(r, 0.15, 190, 262, 170), 0.9)
    m.add(0.265, _grunt(r, 0.17, 212, 300, 182), 1.0)
    return room(S.hp(m.x, 120), 0.5, 0.08, 0.15, 0.6)


# ============================================================================ items & money
def sfx_pickup():
    """Bright 'pop' that settles exactly on C5 (523.25 Hz): quick upward scoop + 2nd/3rd harmonic
    sparkle + tiny click. The game raises the playback rate as the stack grows."""
    r = S.rng(1000)
    f = 523.25
    n = n_of(0.17)
    t = tax(n)
    fr = f * (1 - 0.4 * np.exp(-t / 0.009))
    p = S.phase(fr, n)
    y = (np.sin(TAU * p) + 0.45 * np.sin(TAU * 2 * p) * np.exp(-t / 0.035)
         + 0.12 * np.sin(TAU * 3 * p) * np.exp(-t / 0.016))
    y *= S.env_exp(n, 0.055, 0.0012)
    y[:n_of(0.005)] += burst(r, 0.005, 3200, 0.8, tau=0.0008) * 0.22
    return y


def sfx_drop():
    """Item set down on a pile: soft wooden 'tup'."""
    r = S.rng(1100)
    m = Mono(0.3)
    m.add(0, blip(560, 270, 0.15, 0.018, 0.032, attack=0.001), 0.75)
    m.add(0, S.modal(780, n_of(0.12), [(1, 1, 0.06), (2.3, 0.4, 0.03), (3.9, 0.18, 0.018)], r, attack=0.0006), 0.55)
    m.add(0, burst(r, 0.02, 1700, 0.7, tau=0.003), 0.45)
    m.add(0, blip(200, 120, 0.1, 0.02, 0.03, attack=0.0015), 0.25)
    return m.x


def sfx_coin():
    """Bright double chime 'ding-DING' a fourth apart (C6 -> F6) with a soft chip-square edge."""
    r = S.rng(1200)
    m = Mono(0.9)
    c1 = chime(1046.5, 0.3, 1.0, r)
    c1 *= np.exp(-np.maximum(0, tax(len(c1)) - 0.07) / 0.02)       # damp the first note
    m.add(0, c1, 1.0)
    m.add(0, S.lp(S.square(1046.5, n_of(0.07)), 5000) * S.env_exp(n_of(0.07), 0.02, 0.0005), 0.12)
    m.add(0.072, chime(1396.9, 0.75, 1.1, r), 0.9)
    m.add(0.072, S.lp(S.square(1396.9, n_of(0.12)), 5500) * S.env_exp(n_of(0.12), 0.03, 0.0005), 0.12)
    m.add(0, burst(r, 0.004, 7000, 1.0, tau=0.0005), 0.2)
    m.add(0.072, burst(r, 0.004, 7000, 1.0, tau=0.0005), 0.2)
    return room(m.x, 0.8, 0.12, 0.3, 0.6)


def sfx_coins_many():
    """Collecting a pile of coins: quick rising chime arpeggio over a shower of coin clinks."""
    r = S.rng(1300)
    m = Mono(1.2)
    for i, mm in enumerate([84, 89, 93, 96]):          # C6 F6 A6 C7
        m.add(i * 0.055, chime(float(S.midi_hz(mm)), 0.32 + 0.12 * i, 0.9, r), 0.32 + 0.04 * i)
    times = np.sort(np.concatenate((r.uniform(0.0, 0.25, 10), r.uniform(0.2, 0.55, 7))))
    for t0 in times:
        m.add(t0, coin_hit(r, r.uniform(2600, 4800), r.uniform(0.08, 0.2)), r.uniform(0.2, 0.5) * (1 - 0.55 * t0 / 0.6))
    return room(m.x, 0.7, 0.12, 0.3, 0.6)


def sfx_cash():
    """Cash register 'ka-CHING': drawer clack, then a shimmering bell + coin jingle."""
    r = S.rng(1400)
    m = Mono(1.3)
    m.add(0, burst(r, 0.03, 1500, 1.0, tau=0.005), 0.8)
    m.add(0, blip(180, 110, 0.12, 0.02, 0.035), 0.5)
    m.add(0.045, burst(r, 0.03, 2600, 1.2, tau=0.004), 0.6)
    m.add(0.05, S.modal(900, n_of(0.1), [(1, 1, 0.06), (2.6, 0.4, 0.03)], r), 0.25)
    t0 = 0.1
    for f, a in [(1760, 1.0), (2637, 0.6), (1765.5, 0.55), (3520, 0.25)]:
        m.add(t0, S.modal(f, n_of(0.9), [(1, 1, 0.85), (2.76, 0.3, 0.25), (5.4, 0.1, 0.1)], r, fmax=12500) * a, 0.35)
    for _ in range(7):
        m.add(t0 + 0.02 + r.uniform(0, 0.28), coin_hit(r, r.uniform(3000, 5200), 0.12), 0.2)
    return room(m.x, 0.8, 0.15, 0.35, 0.6)


def sfx_pad_fill():
    """Soft coin 'tik' while paying into an unlock pad (retriggered ~every 70 ms, rising rate)."""
    r = S.rng(2500)
    n = n_of(0.075)
    y = S.modal(1046.5, n, [(1, 1, 0.06), (2.0, 0.22, 0.03), (2.76, 0.12, 0.02)], r, attack=0.0004)
    y[:n_of(0.005)] += burst(r, 0.005, 5200, 1.0, tau=0.0005) * 0.15
    return y


# ============================================================================ progression fanfares
def sfx_unlock():
    """New area unlocked: whoosh riser + glittering F-major arpeggio -> soft brass/pad bloom + sparkles."""
    r = S.rng(1500)
    m = Mono(2.6)
    m.add(0, nsweep(r, 0.45, 500, 6000, 1.4, [(0, 0), (0.33, 1), (0.45, 0)]), 0.22)
    for i, mm in enumerate([77, 81, 84, 89, 93]):        # F5 A5 C6 F6 A6
        tt = i * 0.065
        m.add(tt, I.glock(mm, 0.72 + 0.05 * i, r), 0.5)
        m.add(tt + 0.003, I.musicbox(mm, 0.6, r), 0.3)
    tb = 0.36
    for mm in (65, 69, 72, 77):                           # F4 A4 C5 F5
        m.add(tb, I.brass(mm, 0.7, 0.55, bright=0.8), 0.17)
    m.add(tb, I.pad_chord([65, 69, 72, 77, 81], 0.6, r, cutoff=2600, attack=0.04, release=0.8), 0.55)
    m.add(tb, I.glock(101, 0.8, r), 0.32)                 # F7 ping
    m.add(tb, I.bell_fm(89, 0.6, t60=1.6), 0.22)          # F6 bell
    m.add(tb - 0.01, I.cymbal_soft(0.35, 1.3, r), 0.3)
    sparkles(m, r, tb + 0.06, 10, 0.075, 0.22)
    return room(m.x, 1.4, 0.24, 0.6, 1.0)


def sfx_levelup():
    """Upgrade / level-up power-up: soft chip-square arpeggio + rising glide -> bright 'ding-ding' + sparkles."""
    r = S.rng(1600)
    m = Mono(2.0)
    notes = [65, 69, 72, 77, 81, 84, 89]                 # F4 A4 C5 F5 A5 C6 F6
    for i, mm in enumerate(notes):
        tt = i * 0.045
        m.add(tt, soft_square(mm + 12, 0.07, 0.6 + 0.04 * i, 3200), 0.35)
        m.add(tt, I.glock(mm + 12, 0.5, r), 0.18)
    n = n_of(0.34)
    glide = S.sine(350 * (1400 / 350) ** (np.linspace(0, 1, n) ** 1.3), n) * S.env_pts([(0, 0), (0.05, 1), (0.34, 0)], n)
    m.add(0, glide, 0.2)
    td = 0.33
    m.add(td, I.glock(96, 0.85, r), 0.5)                  # C7
    m.add(td + 0.09, I.glock(101, 0.9, r), 0.55)          # F7
    m.add(td + 0.09, chime(float(S.midi_hz(89)), 0.9, 0.8, r), 0.35)
    m.add(td + 0.09, I.pad_chord([65, 72, 77, 81], 0.4, r, cutoff=2400, attack=0.03, release=0.6), 0.35)
    sparkles(m, r, td + 0.14, 8, 0.07, 0.2)
    return room(m.x, 1.2, 0.2, 0.5, 0.9)


def sfx_hire():
    """Worker hired: brass 'ta-DAA!' (C5 -> F major) with a snare flam, claps and a glock sparkle."""
    r = S.rng(1700)
    m = Mono(2.0)
    m.add(0, I.brass(72, 0.75, 0.1, bright=0.9), 0.5)             # ta (C5)
    m.add(0, I.snare_soft(0.55, r), 0.35)
    m.add(0, I.woodblock(84, 0.6, r), 0.25)
    t2 = 0.16
    for mm, g in ((65, 0.3), (69, 0.3), (72, 0.32), (77, 0.5)):   # DAA (F4 A4 C5 F5)
        m.add(t2, I.brass(mm, 0.85, 0.55, bright=1.0), g)
    m.add(t2, I.bass(41, 0.8, 0.5, r), 0.35)                       # F2
    m.add(t2, I.kick(0.6, r), 0.35)
    m.add(t2 - 0.012, I.snare_soft(0.4, r), 0.3)
    m.add(t2, I.snare_soft(0.7, r), 0.4)
    m.add(t2, I.glock(89, 0.8, r), 0.35)
    m.add(t2 + 0.07, I.glock(93, 0.7, r), 0.3)
    m.add(t2 + 0.14, I.glock(96, 0.75, r), 0.32)
    for k, tc in enumerate((0.42, 0.56)):
        m.add(tc, I.clap_soft(0.6, r), 0.3)
    sparkles(m, r, t2 + 0.2, 6, 0.08, 0.16)
    return room(m.x, 1.0, 0.16, 0.45, 0.8)


def sfx_build():
    """Construction: three hammer knocks, a dust 'poof' and a sparkle ding."""
    r = S.rng(1800)
    m = Mono(1.6)
    for k, tt in enumerate((0.0, 0.12, 0.24)):
        f = 560 * (1.0, 1.06, 1.12)[k]
        m.add(tt, S.modal(f, n_of(0.2), [(1, 1, 0.1), (1.73, 0.5, 0.06), (2.6, 0.35, 0.04), (4.1, 0.15, 0.02)], r,
                          attack=0.0005), 0.5)
        m.add(tt, burst(r, 0.02, 2500, 1.0, tau=0.0025), 0.6)
        m.add(tt, blip(210, 120, 0.12, 0.02, 0.035), 0.45)
    tp = 0.34
    m.add(tp, puff(r, 0.42, 1400, [(0, 0), (0.03, 1), (0.12, 0.45), (0.42, 0)]), 0.6)
    m.add(tp, nsweep(r, 0.3, 700, 2400, 1.0, [(0, 0), (0.05, 1), (0.3, 0)]), 0.2)
    m.add(tp + 0.03, chime(1396.9, 0.8, 0.9, r), 0.38)               # F6
    m.add(tp + 0.03, chime(2093.0, 0.6, 0.7, r), 0.2)                # C7
    sparkles(m, r, tp + 0.1, 5, 0.07, 0.16)
    return room(m.x, 0.8, 0.14, 0.4, 0.7)


def sfx_complete():
    """Village complete: snare roll + swell -> the village hook played as a brass/glock fanfare
    (F | Bb | C) -> big F major chord with crash, bass, bell and a sparkle shower."""
    r = S.rng(2600)
    m = Mono(5.0)
    t = 0.0
    while t < 0.42:
        m.add(t, I.snare_soft(0.25 + 0.6 * t / 0.42, r), 0.3)
        t += 0.033
    m.add(0.0, I.cymbal_soft(0.6, 0.45, r, swell=True), 0.35)
    T0, e = 0.45, 0.15
    mel = [(0, 1, 81), (1, 1, 84), (2, 2, 86), (4, 1, 84), (5, 1, 81), (6, 2, 84), (8, 1, 86), (9, 1, 88)]
    for st, ln, mm in mel:
        tt = T0 + st * e
        m.add(tt, I.brass(mm, 0.85, ln * e * 0.92, bright=1.0), 0.4)
        m.add(tt, I.glock(mm + 12, 0.7, r), 0.22)
        m.add(tt, I.marimba(mm, 0.7, r), 0.22)
    chords = [(0, [65, 69, 72], 41), (4, [62, 65, 70], 46), (8, [64, 67, 72], 48)]   # F, Bb, C
    for st, notes, bm in chords:
        tt = T0 + st * e
        for mm in notes:
            m.add(tt, I.brass(mm, 0.7, 0.12, bright=0.7), 0.16)
            m.add(tt + 2 * e, I.brass(mm, 0.6, 0.1, bright=0.6), 0.12)
        m.add(tt, I.bass(bm, 0.85, 3.5 * e, r), 0.4)
        m.add(tt, I.kick(0.7, r), 0.4)
    m.add(T0, I.cymbal_soft(0.5, 1.2, r), 0.35)
    tf = T0 + 10 * e                                                     # final F major
    for mm in (65, 69, 72, 77, 89):
        m.add(tf, I.brass(mm, 0.9, 1.0, bright=1.0), 0.22 if mm < 80 else 0.3)
    m.add(tf, I.pad_chord([53, 65, 69, 72, 77, 81], 1.2, r, cutoff=2400, attack=0.03, release=1.0), 0.6)
    m.add(tf, I.bass(29 + 12, 0.95, 1.4, r), 0.5)
    m.add(tf, I.kick(0.9, r), 0.5)
    m.add(tf, I.tom(41, 0.7), 0.4)
    m.add(tf, I.cymbal_soft(0.7, 2.2, r), 0.45)
    m.add(tf, I.bell_fm(89, 0.7, t60=2.2), 0.25)
    m.add(tf, I.glock(101, 0.9, r), 0.35)
    for k, mm in enumerate([89, 93, 96, 101]):                           # rising glock flourish
        m.add(tf + 0.06 + k * 0.05, I.glock(mm, 0.6, r), 0.2)
    sparkles(m, r, tf + 0.25, 14, 0.08, 0.2, decay=9.0)
    return room(m.x, 1.6, 0.22, 1.0, 1.0)


# ============================================================================ UI
def sfx_click():
    """UI button: short soft 'tock-pop'."""
    r = S.rng(1900)
    y = blip(1500, 900, 0.07, 0.006, 0.012, attack=0.0004) + 0.45 * blip(620, 400, 0.07, 0.01, 0.018, attack=0.0006)
    y[:n_of(0.004)] += burst(r, 0.004, 4200, 1.0, tau=0.0007) * 0.3
    return y


def sfx_error():
    """Gentle 'nuh-uh': two soft square notes falling a fourth (D4 -> A3), second one bends down."""
    m = Mono(0.5)
    m.add(0, soft_square(62, 0.085, 0.8, 1700), 1.0)
    m.add(0.12, soft_square(57, 0.17, 0.85, 1500, bend=-0.6), 1.0)
    return m.x


def sfx_whoosh():
    """Swoosh (UI transitions, item throws): band-pass noise up-and-down sweep + low air."""
    r = S.rng(2000)
    d = 0.38
    y = nsweep(r, d, 380, 700, 1.8, [(0, 0), (0.15, 1), (0.24, 0.6), (d, 0)], mid=2300)
    y = y + 0.35 * nsweep(r, d, 900, 1500, 2.5, [(0, 0), (0.16, 1), (0.22, 0.4), (d, 0)], mid=5200)
    y = y + 0.5 * puff(r, d, 550, [(0, 0), (0.16, 1), (d, 0)])
    return y


# ============================================================================ footsteps
def sfx_step_snow(v: int):
    """Snow crunch footstep: dense granular crackle + compressed-snow hush + soft thud."""
    r = S.rng(2100 + v)
    m = Mono(0.25)
    ng = int(r.integers(30, 46))
    times = 0.004 + r.gamma(2.0, 0.017, ng)
    times = times[times < 0.11]                          # drop stragglers (clipping would pile them up)
    for t0 in times:
        g = 1.6 * (r.uniform(0.25, 1.0) ** 2) * np.exp(-t0 / 0.07)
        m.add(t0, burst(r, 0.006, r.uniform(1500, 6500), 1.3, tau=r.uniform(0.0004, 0.0015)), g)
    m.add(0, burst(r, 0.13, 1000 + 150 * v, 0.8, tau=0.03, attack=0.008), 0.35)
    m.add(0, blip(140, 90, 0.08, 0.02, 0.022, attack=0.002), 0.14)
    return m.x


# ============================================================================ stations
def sfx_saw():
    """Sawmill: circular-blade whine that dips in pitch while biting the plank + tooth rasp + chips."""
    r = S.rng(2200)
    dur = 0.85
    n = n_of(dur)
    t = tax(n)
    cut = S.env_pts([(0, 0), (0.12, 0), (0.22, 1), (0.6, 1), (0.7, 0), (dur, 0)], n)
    f0 = 330 * (1 - 0.1 * cut) * (1 + 0.004 * np.sin(TAU * 7 * t))
    whine = S.lp(S.additive(f0, n, [(k, 1.0 / k ** 1.2) for k in range(1, 14)], fmax=6500), 2600)
    tooth = 0.5 + 0.5 * np.sin(TAU * S.phase(f0 * 0.5, n))
    rasp = S.bp(r.standard_normal(n), 2800, 0.8) * (0.4 + 0.6 * tooth) * cut
    env = S.env_pts([(0, 0), (0.04, 1), (dur - 0.12, 1), (dur, 0)], n)
    y = (0.32 * whine * (0.6 + 0.4 * cut) + 0.5 * rasp / max(np.std(rasp), 1e-9) * 0.25) * env
    m = Mono(dur + 0.1)
    m.add(0, y, 1.0)
    for t0 in np.sort(r.uniform(0.2, 0.62, 22)):
        m.add(t0, burst(r, 0.01, r.uniform(2500, 6000), 1.4, tau=0.0012), r.uniform(0.05, 0.18))
    return room(S.lp(m.x, 7000), 0.4, 0.08, 0.15, 0.5)


def sfx_smelt():
    """Smelter: furnace 'fwoomp' + molten bloops + ingot clink."""
    r = S.rng(2300)
    m = Mono(1.4)
    n = n_of(0.7)
    x = r.standard_normal(n)
    m.add(0, S.lp(x, 700, order=2) * S.env_pts([(0, 0), (0.07, 1), (0.25, 0.45), (0.7, 0)], n), 0.9)
    m.add(0, S.bp(x, 1800, 0.7) * S.env_pts([(0, 0), (0.05, 1), (0.2, 0.2), (0.7, 0)], n), 0.25)
    for t0, f0 in [(0.15, 260), (0.27, 340), (0.36, 300)]:
        m.add(t0, bubble(r, f0, 0.08, rise=1.2, tau=0.03), 0.4)
    m.add(0.5, S.modal(1650, n_of(0.5), [(1, 1, 0.35), (2.71, 0.5, 0.2), (4.4, 0.25, 0.1)], r, fmax=11000), 0.35)
    m.add(0.5, burst(r, 0.02, 3000, 1.0, tau=0.002), 0.3)
    return room(m.x, 0.6, 0.12, 0.25, 0.6)


def sfx_sizzle():
    """Frying sizzle (grill / smokehouse): flickering hiss + dense fat crackles + low fry."""
    r = S.rng(2400)
    dur = 0.9
    n = n_of(dur)
    env = S.env_pts([(0, 0), (0.03, 1), (0.45, 0.7), (dur, 0)], n)
    flick = np.clip(0.65 + 0.3 * smooth_noise(r, n, 12.0), 0.15, 1.3)
    hiss = S.lp(S.hp(r.standard_normal(n), 3000, order=2), 8000) * env * flick * 0.3
    imp = np.zeros(n)
    k = int(140 * dur)
    pos = r.integers(0, n, k)
    imp[pos] = r.standard_normal(k) * (r.pareto(2.5, k) + 0.3)
    crack = S.hp(imp, 1500, order=2) * env
    crack /= max(S.peak(crack), 1e-9)
    fry = S.bp(r.standard_normal(n), 1300, 0.7) * env * flick
    fry = fry / max(np.std(fry[n // 4:n // 2]), 1e-9) * 0.05
    return hiss / max(np.std(hiss[n // 4:n // 2]), 1e-9) * 0.1 + crack * 0.6 + fry


def sfx_oven():
    """Bread oven: warm 'whoomph' of heat + tray thunk + soft kitchen-timer 'ding'."""
    r = S.rng(2450)
    m = Mono(1.5)
    m.add(0, puff(r, 0.45, 500, [(0, 0), (0.06, 1), (0.45, 0)]) , 0.55)
    m.add(0.02, blip(200, 120, 0.15, 0.02, 0.04), 0.4)
    m.add(0.02, S.modal(700, n_of(0.15), [(1, 1, 0.08), (2.4, 0.4, 0.04)], r), 0.2)
    m.add(0.12, chime(float(S.midi_hz(93)), 0.9, 0.6, r), 0.5)       # A6
    m.add(0.12, chime(float(S.midi_hz(89)), 0.7, 0.5, r), 0.2)       # F6
    return room(m.x, 0.7, 0.12, 0.3, 0.6)


def sfx_customer_happy():
    """Customer served: cute little voiced 'yay!' (formant voice) over a music-box sparkle."""
    r = S.rng(2550)
    dur = 0.36
    n = n_of(dur)
    t = tax(n)
    vib = 1 + 0.02 * np.sin(TAU * 7 * t) * np.clip((t - 0.12) / 0.1, 0, 1)
    f0 = S.env_pts([(0, 420), (0.07, 560), (0.16, 640), (0.27, 620), (dur, 520)], n) * vib
    F1 = S.env_pts([(0, 330), (0.06, 780), (0.2, 760), (0.3, 480), (dur, 420)], n)
    F2 = S.env_pts([(0, 2300), (0.06, 1450), (0.2, 1500), (0.3, 2000), (dur, 2100)], n)
    amp = S.env_pts([(0, 0), (0.02, 0.6), (0.06, 1), (0.26, 0.85), (dur, 0)], n)
    v = I.formant_voice(f0, amp, [(F1, 140, 1.0), (F2, 220, 0.6), (2900, 350, 0.3)], r,
                        breath=0.04, tilt=0.8, jitter=0.006)
    m = Mono(1.0)
    m.add(0, S.hp(v, 200), 0.75)
    for i, mm in enumerate([89, 93, 96]):                               # F6 A6 C7
        m.add(0.05 + i * 0.06, I.musicbox(mm, 0.6, r), 0.25)
    return room(m.x, 0.6, 0.1, 0.25, 0.6)


# ============================================================================ registry
SFX = {
    "sfx_chop_1": lambda: sfx_chop(1), "sfx_chop_2": lambda: sfx_chop(2), "sfx_chop_3": lambda: sfx_chop(3),
    "sfx_mine_1": lambda: sfx_mine(1), "sfx_mine_2": lambda: sfx_mine(2), "sfx_mine_3": lambda: sfx_mine(3),
    "sfx_harvest_1": lambda: sfx_harvest(1), "sfx_harvest_2": lambda: sfx_harvest(2),
    "sfx_splash": sfx_splash, "sfx_reel": sfx_reel, "sfx_bow": sfx_bow, "sfx_hit_animal": sfx_hit_animal,
    "sfx_animal_deer": sfx_animal_deer, "sfx_animal_boar": sfx_animal_boar,
    "sfx_pickup": sfx_pickup, "sfx_drop": sfx_drop, "sfx_coin": sfx_coin, "sfx_coins_many": sfx_coins_many,
    "sfx_cash": sfx_cash, "sfx_unlock": sfx_unlock, "sfx_build": sfx_build, "sfx_levelup": sfx_levelup,
    "sfx_hire": sfx_hire, "sfx_click": sfx_click, "sfx_error": sfx_error, "sfx_whoosh": sfx_whoosh,
    "sfx_step_snow_1": lambda: sfx_step_snow(1), "sfx_step_snow_2": lambda: sfx_step_snow(2),
    "sfx_step_snow_3": lambda: sfx_step_snow(3),
    "sfx_saw": sfx_saw, "sfx_smelt": sfx_smelt, "sfx_sizzle": sfx_sizzle, "sfx_oven": sfx_oven,
    "sfx_customer_happy": sfx_customer_happy, "sfx_pad_fill": sfx_pad_fill, "sfx_complete": sfx_complete,
}

# per-key mastering: punch = dB of fast (3 ms look-ahead) limiting before normalisation -> denser,
# punchier transients that still read on phone speakers; other keys go to finish_sfx.
FINISH = {
    "sfx_chop_1": dict(punch=7), "sfx_chop_2": dict(punch=7), "sfx_chop_3": dict(punch=7),
    "sfx_mine_1": dict(punch=4), "sfx_mine_2": dict(punch=4), "sfx_mine_3": dict(punch=4),
    "sfx_harvest_1": dict(punch=2), "sfx_harvest_2": dict(punch=2),
    "sfx_drop": dict(punch=4), "sfx_hit_animal": dict(punch=4), "sfx_bow": dict(punch=3),
    "sfx_splash": dict(punch=2), "sfx_build": dict(punch=3),
    "sfx_pickup": dict(punch=2, fout=0.01),
    "sfx_pad_fill": dict(punch=2, fout=0.008),
    "sfx_click": dict(punch=3, fout=0.008),
    "sfx_step_snow_1": dict(punch=6, fout=0.01), "sfx_step_snow_2": dict(punch=6, fout=0.01),
    "sfx_step_snow_3": dict(punch=6, fout=0.01),
}


def render(key: str) -> np.ndarray:
    y = np.asarray(SFX[key](), dtype=float)
    opts = dict(FINISH.get(key, {}))
    punch = opts.pop("punch", 0)
    if punch:
        y = S.hp(y, 30, order=2)
        y = S.limiter(y / max(S.peak(y), 1e-12), -float(punch), window_ms=3.0)
    return S.finish_sfx(y, peak_db=-1.5, **opts)


def main(keys):
    os.makedirs(CACHE, exist_ok=True)
    for k in keys:
        y = render(k)
        p = os.path.join(CACHE, f"{k}.wav")
        S.write_wav(p, y)
        print(f"{k:20s} {len(y) / SR:5.2f}s  peak {S.db(S.peak(y)):6.2f} dBFS  Mmax {S.momentary_max(y):6.1f}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(SFX))
