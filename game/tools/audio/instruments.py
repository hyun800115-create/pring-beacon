"""Frost Village - synthesized instrument voices (library used by music.py and sfx.py).

Every function returns a mono numpy array (peak roughly <= 1 at vel=1) unless noted.
Requirements: numpy + scipy (see synth.py). Not a script.
"""
from __future__ import annotations

import numpy as np

import synth as S
from synth import SR, n_of


# ----------------------------------------------------------------------------- pitched
def marimba(m: float, vel: float = 0.8, r: np.random.Generator | None = None, dur: float | None = None) -> np.ndarray:
    """Soft-mallet marimba: modal bar (1 : 3.99 : 9.9) + resonator-boosted fundamental + mallet thump."""
    f = float(S.midi_hz(m))
    t60 = float(np.clip(1.9 - (m - 60) * 0.045, 0.45, 2.2))
    n = n_of(dur if dur else t60 * 0.9 + 0.1)
    br = 0.35 + 0.55 * vel
    modes = [(1.0, 1.0, t60), (1.0016, 0.18, t60 * 0.8), (3.99, 0.30 * br, t60 * 0.22), (9.9, 0.07 * br, 0.07)]
    y = S.modal(f, n, modes, r, fmax=8000.0, attack=0.0012)
    if r is not None:
        k = n_of(0.006)
        th = S.lp(r.standard_normal(k), 1800 + 1200 * vel) * np.hanning(k) * 0.12 * vel
        y[:k] += th
    return y * (0.55 + 0.45 * vel) / 1.25


def musicbox(m: float, vel: float = 0.8, r: np.random.Generator | None = None) -> np.ndarray:
    """Toy music-box / celesta tine: fundamental pair (slow beating shimmer) + tine mode 6.27 + soft octave."""
    f = float(S.midi_hz(m))
    t60 = float(np.clip(2.6 - (m - 72) * 0.06, 0.8, 3.0))
    n = n_of(t60 * 0.8)
    modes = [(1.0, 1.0, t60), (1.0021, 0.35, t60 * 0.9), (2.0, 0.07, t60 * 0.35),
             (6.27, 0.16 * (0.4 + vel), 0.22), (3.0, 0.03, 0.3)]
    y = S.modal(f, n, modes, r, fmax=7500.0, attack=0.0008)
    return y * (0.5 + 0.5 * vel) / 1.35


def glock(m: float, vel: float = 0.8, r: np.random.Generator | None = None) -> np.ndarray:
    """Glockenspiel / small bell (free bar modes 1 : 2.76 : 5.40 : 8.93)."""
    f = float(S.midi_hz(m))
    t60 = float(np.clip(2.4 - (m - 76) * 0.05, 0.7, 2.6))
    n = n_of(t60 * 0.75)
    modes = [(1.0, 1.0, t60), (2.76, 0.32 * (0.5 + vel), t60 * 0.3), (5.40, 0.12 * vel, t60 * 0.12),
             (8.93, 0.05 * vel, 0.08)]
    y = S.modal(f, n, modes, r, fmax=7800.0, attack=0.0006)
    return y * (0.5 + 0.5 * vel) / 1.3


def bell_fm(m: float, vel: float = 0.8, t60: float = 2.0, ratio: float = 3.5, index: float = 2.2) -> np.ndarray:
    """FM tubular-ish bell (index decays -> bright strike, pure tail)."""
    f = float(S.midi_hz(m))
    n = n_of(t60 * 0.8)
    t = np.arange(n) / SR
    idx = index * vel * np.exp(-t / (t60 * 0.18))
    y = S.fm(f, n, ratio, idx) * S.env_t60(n, t60, 0.001)
    return S.lp(y, 7500) * (0.5 + 0.5 * vel)


def pluck(m: float, vel: float = 0.7, r: np.random.Generator | None = None, t60: float = 1.4, dur: float | None = None,
          bright: float = 0.45) -> np.ndarray:
    """Warm nylon/ukulele-like Karplus-Strong pluck. ``dur`` = note length (damped after)."""
    r = r or S.rng(0)
    f = float(S.midi_hz(m))
    total = (dur + 0.12) if dur else min(t60, 2.0)
    y = S.ks_pluck(f, total, r, t60=t60, bright=bright * (0.6 + 0.5 * vel), stretch=0.42, pick=0.17 + 0.05 * r.random())
    y = S.lp(y, 3800)
    if dur:
        nd = n_of(dur)
        env = np.ones(len(y))
        env[nd:] = np.exp(-np.arange(len(y) - nd) / (0.03 * SR))
        y *= env
    return y * (0.45 + 0.55 * vel) / max(S.peak(y), 1e-6) * 0.9


def bass(m: float, vel: float = 0.8, dur: float = 0.6, r: np.random.Generator | None = None) -> np.ndarray:
    """Round pizzicato upright-ish bass: dark KS string + sine body, damped at note end."""
    r = r or S.rng(0)
    f = float(S.midi_hz(m))
    total = dur + 0.15
    n = n_of(total)
    ks = S.ks_pluck(f, total, r, t60=2.2, bright=0.22 + 0.15 * vel, stretch=0.5, pick=0.12)
    ks = ks / max(S.peak(ks), 1e-6)
    body = S.sine(f, n) * S.env_exp(n, 0.55, 0.004)
    harm = S.sine(2 * f, n) * S.env_exp(n, 0.25, 0.003) * 0.25
    y = 0.65 * ks + 0.7 * body + harm
    y = S.lp(y, 1400)
    nd = n_of(dur)
    env = np.ones(n)
    env[nd:] = np.exp(-np.arange(n - nd) / (0.04 * SR))
    y *= env
    return y * (0.6 + 0.4 * vel) / max(S.peak(y), 1e-6)


def ocarina(m: float, vel: float = 0.8, dur: float = 0.5, r: np.random.Generator | None = None,
            vib: float = 1.0, scoop: float = -0.3) -> np.ndarray:
    """Breathy ocarina / soft flute: near-sine tone, pitch scoop, delayed vibrato, breath noise."""
    r = r or S.rng(0)
    rel = 0.14
    n = n_of(dur + rel)
    t = np.arange(n) / SR
    f0 = float(S.midi_hz(m))
    semis = scoop * np.exp(-t / 0.035)
    vdepth = 0.18 * vib * np.clip((t - 0.22) / 0.3, 0, 1)
    semis = semis + vdepth * np.sin(S.TAU * 5.2 * t)
    f = f0 * 2 ** (semis / 12)
    tone = S.additive(f, n, [(1, 1.0), (2, 0.10), (3, 0.05), (4, 0.015)], fmax=7000)
    breath = S.bp(r.standard_normal(n), f0, 6.0) * 0.10 + S.bp(r.standard_normal(n), 2500, 0.8) * 0.012
    env = S.env_adsr(n, 0.045, 0.12, 0.82, rel, gate=dur)
    benv = S.env_adsr(n, 0.02, 0.08, 0.35, rel, gate=dur)
    y = tone * env + breath * benv
    return y * (0.6 + 0.4 * vel)


def pad_chord(ms, dur: float, r: np.random.Generator, cutoff: float = 1200.0, attack: float = 0.55,
              release: float = 1.1) -> np.ndarray:
    """Warm detuned-saw pad for a chord (mono; chorus is applied on the bus)."""
    n = n_of(dur + release)
    acc = np.zeros(n)
    for m in ms:
        f = float(S.midi_hz(m))
        for cents in (-7.0, 0.0, 6.5):
            acc += S.saw(f * 2 ** (cents / 1200), n, ph0=r.random()) * (0.8 if cents else 1.0)
    acc /= (len(ms) * 2.6)
    acc = S.lp(acc, cutoff, 0.6, order=2)
    acc = S.hp(acc, 120)
    env = S.env_adsr(n, attack, 0.6, 0.85, release, gate=dur)
    return acc * env


def brass(m: float, vel: float = 0.8, dur: float = 0.4, bright: float = 1.0) -> np.ndarray:
    """Soft cartoon brass: saw + square through an enveloped lowpass (filter 'blat')."""
    rel = 0.12
    n = n_of(dur + rel)
    t = np.arange(n) / SR
    f0 = float(S.midi_hz(m))
    f = f0 * 2 ** ((-0.25 * np.exp(-t / 0.03) + 0.06 * np.sin(S.TAU * 5.5 * t) * np.clip((t - 0.2) / 0.2, 0, 1)) / 12)
    x = 0.7 * S.saw(f, n) + 0.3 * S.square(f * 1.003, n, 0.42)
    fenv = 700 + (2400 * bright) * np.exp(-t / 0.12) + 900 * bright
    y = S.tv_filter(x, "lp", np.minimum(fenv, f0 * 9), 0.9)
    y *= S.env_adsr(n, 0.02, 0.15, 0.75, rel, gate=dur)
    return y * (0.55 + 0.45 * vel)


# ----------------------------------------------------------------------------- percussion
def kick(vel: float = 0.8, r: np.random.Generator | None = None) -> np.ndarray:
    n = n_of(0.42)
    t = np.arange(n) / SR
    f = 54 + 120 * np.exp(-t / 0.022)
    body = S.sine(f, n) * S.env_exp(n, 0.16, 0.0015)
    r = r or S.rng(0)
    k = n_of(0.004)
    click = np.zeros(n)
    click[:k] = S.lp(r.standard_normal(k), 3000) * np.hanning(k) * 0.25
    y = np.tanh(1.6 * (body + click)) / np.tanh(1.6)
    return y * vel


def snare_soft(vel: float = 0.7, r: np.random.Generator | None = None) -> np.ndarray:
    """Brushy, rounded snare / rim hit."""
    r = r or S.rng(0)
    n = n_of(0.35)
    nz = r.standard_normal(n)
    crack = S.bp(nz, 2200, 0.8) * S.env_exp(n, 0.045, 0.001)
    brush = S.lp(S.hp(nz, 1500), 6500) * S.env_exp(n, 0.11, 0.004) * 0.35
    t = np.arange(n) / SR
    body = S.sine(205 - 25 * (1 - np.exp(-t / 0.03)), n) * S.env_exp(n, 0.05, 0.001) * 0.6
    y = crack + brush + body
    return y / max(S.peak(y), 1e-6) * vel


def shaker(vel: float = 0.6, r: np.random.Generator | None = None, length: float = 0.11) -> np.ndarray:
    r = r or S.rng(0)
    n = n_of(length + 0.05)
    nz = S.lp(S.bp(r.standard_normal(n), 5200, 1.1), 7600)
    env = S.env_pts([(0, 0), (0.012, 1.0), (0.03, 0.55), (length, 0.0), (length + 0.05, 0)], n)
    y = nz * env ** 1.5
    return y / max(S.peak(y), 1e-6) * vel


def sleigh(vel: float = 0.6, r: np.random.Generator | None = None, nbells: int = 6) -> np.ndarray:
    """Jingle / sleigh bells cluster (kept below ~8 kHz)."""
    r = r or S.rng(0)
    n = n_of(0.45)
    y = np.zeros(n)
    for _ in range(nbells):
        f = r.uniform(2300, 3500)
        b = S.modal(f, n, [(1, 1, r.uniform(0.15, 0.3)), (1.47, 0.5, 0.15), (2.09, 0.22, 0.09)], r, fmax=7800)
        off = n_of(r.uniform(0, 0.028))
        y[off:] += b[:n - off] * r.uniform(0.4, 1.0)
    sh = shaker(0.5, r, 0.08)
    y[:len(sh)] += sh[:n]
    y = S.lp(y, 7500)
    return y / max(S.peak(y), 1e-6) * vel


def woodblock(m: float = 79, vel: float = 0.7, r: np.random.Generator | None = None) -> np.ndarray:
    f = float(S.midi_hz(m))
    n = n_of(0.25)
    y = S.modal(f, n, [(1, 1, 0.16), (2.57, 0.35, 0.05), (4.1, 0.12, 0.025)], r, fmax=8000, attack=0.0004)
    return y * vel


def tom(m: float = 50, vel: float = 0.7) -> np.ndarray:
    f = float(S.midi_hz(m))
    n = n_of(0.5)
    t = np.arange(n) / SR
    y = S.sine(f * (1 + 0.35 * np.exp(-t / 0.03)), n) * S.env_exp(n, 0.18, 0.002)
    y += S.sine(f * 1.6, n) * S.env_exp(n, 0.06, 0.002) * 0.25
    return y * vel


def clap_soft(vel: float = 0.6, r: np.random.Generator | None = None) -> np.ndarray:
    r = r or S.rng(0)
    n = n_of(0.3)
    y = np.zeros(n)
    nz = S.bp(r.standard_normal(n), 1400, 1.2)
    for i, off in enumerate((0.0, 0.009, 0.019)):
        k = n_of(off)
        e = S.env_exp(n - k, 0.012 if i < 2 else 0.09, 0.0008)
        y[k:] += nz[k:] * e
    return y / max(S.peak(y), 1e-6) * vel


def cymbal_soft(vel: float = 0.5, dur: float = 1.6, r: np.random.Generator | None = None, swell: bool = False) -> np.ndarray:
    """Soft dark cymbal / swell (metallic noise via inharmonic square cluster + noise), lowpassed."""
    r = r or S.rng(0)
    n = n_of(dur)
    fs = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]
    x = sum(np.sign(S.sine(f * 5.3, n, r.random())) for f in fs) / 6.0
    x = 0.6 * x + 0.6 * r.standard_normal(n)
    x = S.lp(S.hp(x, 3000), 7500)
    if swell:
        env = S.env_pts([(0, 0), (dur * 0.85, 1.0), (dur, 0)], n) ** 2
    else:
        env = S.env_exp(n, dur / 4.0, 0.002)
    return x * env * vel / 1.5


# ----------------------------------------------------------------------------- voice / helpers (appended)
def formant_voice(f0, amp, formants, r: np.random.Generator, breath: float = 0.04, tilt: float = 1.0,
                  fmax: float = 7500.0, jitter: float = 0.006) -> np.ndarray:
    """Additive formant voice (animal calls, cute vocal chirps).
    f0: per-sample fundamental (Hz); amp: per-sample amplitude envelope;
    formants: list of (F_hz, bandwidth_hz, gain) where F may be a per-sample array.
    Harmonic k gets amplitude k^-tilt * sum_j gain_j / (1 + ((k f0 - F_j) / (bw_j / 2))^2)."""
    f0 = np.asarray(f0, dtype=float)
    n = len(f0)
    if jitter > 0:
        wob = S.lp(r.standard_normal(n), 18.0, order=2)
        wob /= max(np.std(wob), 1e-9)
        f0 = f0 * (1 + jitter * wob)
    p = S.phase(f0, n)
    out = np.zeros(n)
    kmax = int(fmax / max(f0.min(), 40.0)) + 1
    for k in range(1, kmax + 1):
        fk = k * f0
        live = fk < fmax
        if not live.any():
            break
        a = np.zeros(n)
        for F, bw, g in formants:
            F = np.broadcast_to(np.asarray(F, dtype=float), (n,))
            a += g / (1.0 + ((fk - F) / (bw / 2.0)) ** 2)
        a *= k ** (-tilt) * live * np.clip((fmax - fk) / (0.15 * fmax), 0, 1)
        out += a * np.sin(S.TAU * k * p)
    if breath > 0:
        nz = r.standard_normal(n)
        b = np.zeros(n)
        for F, bw, g in formants:
            Fm = float(np.mean(np.broadcast_to(np.asarray(F, dtype=float), (n,))))
            b += g * S.bp(nz, Fm, max(Fm / bw, 0.5))
        out += breath * b * np.std(out) / max(np.std(b), 1e-9) * 3.0
    out *= np.asarray(amp, dtype=float)
    return out / max(S.peak(out), 1e-9)


def verb_mono(x, rt60: float = 1.0, mix: float = 0.25, tail: float = 1.0, **kw) -> np.ndarray:
    """Dry mono + mono-summed FDN reverb, with ``tail`` seconds appended."""
    x = np.concatenate((np.asarray(x, float), np.zeros(n_of(tail))))
    wet = S.reverb(x, rt60=rt60, **kw).mean(axis=0)
    return x + mix * wet
