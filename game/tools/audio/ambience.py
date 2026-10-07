"""Frost Village - ambience loops by procedural synthesis (library + script).

  amb_wind : gentle winter wind - pinkish band of air whose centre and level follow slow
             gust curves, a soft resonant 'howl', faint snow hiss.            24 s, stereo
  amb_sea  : calm shore - low surf bed + 4 gentle waves (swell -> soft break -> foam fizz
             retreating), alternating left/right.                              24 s, stereo
  amb_fire : campfire - flickering low roar, airy flame breath, hiss, and wood crackles /
             pops / occasional bigger snaps scattered in the stereo field.    20 s, stereo

Seamless by construction:
  * continuous beds are built in the frequency domain (synth.noise_fft) -> exactly periodic;
  * every modulation curve is a sum of whole cycles over the loop (synth.periodic_curve);
  * time-varying filters run with a pre-roll taken from the loop's own end (steady state);
  * discrete events (waves, crackles) are rendered past the end and folded onto the start;
  * the final limiter runs circularly.
Run:   python3 tools/audio/ambience.py [wind] [sea] [fire]
       -> tools/audio/_cache/amb_<name>.wav (32-bit float stereo, -20 LUFS (fire -21))
Normally called through build_audio.py.  Deterministic (fixed seeds).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deps  # noqa: E402

deps.ensure()
import numpy as np  # noqa: E402

import synth as S  # noqa: E402
from synth import SR, n_of  # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")


# ----------------------------------------------------------------------------- helpers
def circ_tv(x, kind, f, q=0.7071, pre_sec=1.5):
    """Time-varying biquad on a loop: f/q are per-sample periodic arrays; pre-roll = loop end."""
    x = np.asarray(x, dtype=float)
    L = x.shape[-1]
    pre = min(L, n_of(pre_sec))
    fa = np.broadcast_to(np.asarray(f, dtype=float), (L,))
    qa = np.broadcast_to(np.asarray(q, dtype=float), (L,))
    y = S.tv_filter(np.concatenate((x[..., -pre:], x), axis=-1), kind,
                    np.concatenate((fa[-pre:], fa)), np.concatenate((qa[-pre:], qa)))
    return y[..., pre:]


def unit(x):
    return x / max(float(np.std(x)), 1e-12)


def master_loop(x, target_lufs, ceiling_db=-1.5):
    x = x - x.mean(axis=-1, keepdims=True)
    x = x * S.undb(target_lufs - S.lufs(x))
    return S.limiter(x, ceiling_db, window_ms=5.0, circular=True)


# ----------------------------------------------------------------------------- wind
def render_wind(seed: int = 31, dur: float = 24.0, loop_samples: int | None = None):
    r = S.rng(seed)
    L = int(loop_samples) if loop_samples else n_of(dur)
    dur = L / SR
    gust = S.periodic_curve(L, r, 1, 7, slope=1.15)
    wob = S.periodic_curve(L, r, 2, 11, slope=0.9)
    out = np.zeros((2, L))
    for ch in range(2):
        g = np.roll(gust, ch * n_of(0.45))                     # right channel lags a little -> motion
        w = np.roll(wob, ch * n_of(1.3))
        base = S.noise_fft(L, r, lambda f: np.exp(-0.5 * (np.log2(f / 520.0) / 1.5) ** 2) / np.sqrt(np.maximum(f, 30)))
        fc = 260 + 720 * g ** 1.3
        body = unit(circ_tv(base, "bp", fc, 0.85)) * (0.32 + 0.68 * g ** 1.5)
        pinkn = S.pink(L, r)
        fw = (480 + 360 * w) * (1.0 + 0.025 * ch)
        howl = unit(circ_tv(pinkn, "bp", fw, 13.0)) * 0.30 * g ** 2.2
        hiss = unit(S.filt_circ(S.filt_circ(S.noise_fft(L, r), "hp", 4200, order=2), "lp", 9000)) * 0.05 * (0.3 + 0.7 * g)
        rumble = unit(S.noise_fft(L, r, lambda f: 1.0 / (1 + (f / 90.0) ** 4))) * 0.18 * (0.5 + 0.5 * g)
        out[ch] = body + howl + hiss + rumble
    out = S.filt_circ(out, "hp", 45, order=2)
    return master_loop(out, -20.0), {"loopSamples": L}


# ----------------------------------------------------------------------------- sea
def _wave(r, strength=1.0):
    """One gentle wave, stereo (2, n): swell -> soft break -> foam fizz -> retreat."""
    dur = 7.5
    n = n_of(dur)
    t = np.arange(n) / SR
    tb = 2.3                                                   # break time
    out = np.zeros((2, n))
    common = r.standard_normal(n)
    for ch in range(2):
        nz = 0.75 * common + 0.66 * r.standard_normal(n)
        # swell: dark rising roar
        sw_env = np.clip(t / tb, 0, 1) ** 2.2 * np.exp(-np.maximum(t - tb, 0) / 0.5)
        sw_fc = 220 + 700 * np.clip(t / tb, 0, 1) ** 1.5
        swell = S.tv_filter(nz, "lp", sw_fc, 0.7, block=64) * sw_env * 0.9
        # break + wash: broadband, bright then darkening
        br_env = np.where(t < tb, 0.0, 1 - np.exp(-np.maximum(t - tb, 0) / 0.12)) * np.exp(-np.maximum(t - tb, 0) / 1.45)
        br_fc = 900 + 4800 * np.exp(-np.maximum(t - tb, 0) / 0.8)
        brk = S.tv_filter(S.hp(nz, 250), "lp", br_fc, 0.6, block=64) * br_env * 1.1
        # foam fizz: dense micro-crackle of bursting bubbles, high band, long decay
        dens = np.where(t < tb + 0.1, 0.0, np.exp(-np.maximum(t - tb - 0.1, 0) / 1.8))
        fz_imp = (r.random(n) < 0.02 * dens) * r.standard_normal(n) * r.uniform(0.3, 1.0, n)
        fizz = S.bp(fz_imp, 5200, 0.7) * 0.8 + S.bp(r.standard_normal(n), 4500, 0.6) * dens * 0.08
        # retreat: soft hiss draining back
        rt_env = np.clip((t - tb - 1.0) / 1.5, 0, 1) * np.exp(-np.maximum(t - tb - 2.5, 0) / 1.4)
        retreat = S.bp(nz, 2600, 0.8) * rt_env * 0.12
        out[ch] = swell + brk + fizz + retreat
    return out * strength


def render_sea(seed: int = 41, dur: float = 24.0, loop_samples: int | None = None):
    r = S.rng(seed)
    L = int(loop_samples) if loop_samples else n_of(dur)
    dur = L / SR
    total = L + n_of(9.0)
    buf = np.zeros((2, total))
    starts = [0.3, 6.2, 12.4, 18.0]
    pans = [-0.35, 0.3, -0.15, 0.4]
    for t0, p, st in zip(starts, pans, [0.9, 1.0, 0.8, 0.95]):
        w = _wave(r, st)
        th = (p + 1) * np.pi / 4
        w[0] *= np.cos(th) * 1.4142
        w[1] *= np.sin(th) * 1.4142
        i = n_of(t0)
        buf[:, i:i + w.shape[1]] += w
    waves = S.fold_loop(buf, L)
    bed = np.zeros((2, L))
    swell = S.periodic_curve(L, r, 2, 8)
    for ch in range(2):
        low = unit(S.noise_fft(L, r, lambda f: 1.0 / (1 + (f / 180.0) ** 2) / np.sqrt(np.maximum(f, 25))))
        far = unit(S.noise_fft(L, r, lambda f: np.exp(-0.5 * (np.log2(f / 900.0) / 1.2) ** 2)))
        bed[ch] = low * 0.05 * (0.6 + 0.4 * swell) + far * 0.025 * (0.5 + 0.5 * swell)
    out = S.filt_circ(waves * 0.3 + bed, "hp", 35, order=2)
    return master_loop(out, -20.0), {"loopSamples": L}


# ----------------------------------------------------------------------------- fire
def _pop(r, size):
    """Wood crackle: 'tick' (0), 'crack' (1) or 'snap' (2) -> mono."""
    if size == 0:
        n = n_of(0.006)
        y = S.bp(r.standard_normal(n), r.uniform(1800, 6500), 1.2) * S.env_exp(n, r.uniform(0.0003, 0.0009), 0.0001)
        return y * r.lognormal(0, 0.5) * 0.35
    n = n_of(0.08 if size == 1 else 0.16)
    y = np.zeros(n)
    k = 2 + int(r.integers(0, 3)) + (2 if size == 2 else 0)
    for _ in range(k):
        i = n_of(r.uniform(0, 0.02 if size == 1 else 0.05))
        m = n_of(0.008)
        if i + m > n:
            continue
        y[i:i + m] += S.bp(r.standard_normal(m), r.uniform(1500, 5500), 1.0) * S.env_exp(m, r.uniform(0.0004, 0.0015), 0.0001) * r.uniform(0.4, 1.0)
    ring = S.modal(r.uniform(900, 2400), n, [(1, 1, 0.03), (1.7, 0.5, 0.02)], r) * 0.25
    body = S.bp(r.standard_normal(n), r.uniform(450, 900), 1.0) * S.env_exp(n, 0.012 if size == 1 else 0.02, 0.0005) * 0.5
    y = y + ring + body
    return y * (0.6 if size == 1 else 1.0)


def render_fire(seed: int = 51, dur: float = 20.0, loop_samples: int | None = None):
    r = S.rng(seed)
    L = int(loop_samples) if loop_samples else n_of(dur)
    dur = L / SR
    slow = S.periodic_curve(L, r, 1, 6)
    flick = S.periodic_curve(L, r, 4, 70, slope=0.6)
    out = np.zeros((2, L))
    for ch in range(2):
        fl = np.roll(flick, ch * n_of(0.07))
        roar = unit(S.noise_fft(L, r, lambda f: 1.0 / np.maximum(f, 40) / (1 + (f / 320.0) ** 2)))
        breath = unit(S.noise_fft(L, r, lambda f: np.exp(-0.5 * (np.log2(f / 1300.0) / 1.0) ** 2)))
        hiss = unit(S.noise_fft(L, r, lambda f: (f > 2500) / (1 + (f / 9000.0) ** 4)))
        out[ch] = (roar * 0.22 * (0.6 + 0.25 * slow + 0.3 * fl)
                   + breath * 0.06 * (0.25 + 0.75 * fl ** 2)
                   + hiss * 0.022 * (0.5 + 0.5 * fl))
    total = L + n_of(1.0)
    buf = np.zeros((2, total))
    t = 0.0
    while True:
        t += r.exponential(1 / 7.5)
        if t >= dur:
            break
        u = r.random()
        size = 2 if u < 0.04 else (1 if u < 0.24 else 0)
        y = _pop(r, size) * (0.55 + 0.45 * slow[min(L - 1, n_of(t))])
        st = S.pan(y, r.uniform(-0.55, 0.55))
        i = n_of(t)
        buf[:, i:i + st.shape[1]] += st
    t = 0.0
    while True:                                                   # faint micro-crackle
        t += r.exponential(1 / 35.0)
        if t >= dur:
            break
        y = _pop(r, 0) * 0.3
        st = S.pan(y, r.uniform(-0.7, 0.7))
        i = n_of(t)
        buf[:, i:i + st.shape[1]] += st
    out = out + S.fold_loop(buf, L) * 1.8
    out = S.filt_circ(out, "hp", 40, order=2)
    return master_loop(out, -21.0), {"loopSamples": L}


RENDER = {"amb_wind": render_wind, "amb_sea": render_sea, "amb_fire": render_fire}


def main(names):
    os.makedirs(CACHE, exist_ok=True)
    for nm in names:
        key = nm if nm.startswith("amb_") else f"amb_{nm}"
        x, meta = RENDER[key]()
        p = os.path.join(CACHE, f"{key}.wav")
        S.write_wav(p, x)
        print(f"{key}: {x.shape[1] / SR:.2f}s peak {S.db(S.peak(x)):.2f} dBFS  LUFS {S.lufs(x):.2f}  -> {p}")


if __name__ == "__main__":
    main(sys.argv[1:] or list(RENDER))
