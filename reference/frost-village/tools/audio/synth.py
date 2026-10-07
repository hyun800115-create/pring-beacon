"""Frost Village - tiny procedural audio toolkit (numpy + scipy).

Shared by music.py, ambience.py and sfx.py; it is a library, not a script.
Requirements: python3 with numpy and scipy (``python3 -m pip install numpy scipy pillow``).

Contents
  * units / pitch helpers ............ SR, n_of, midi_hz, note
  * envelopes ........................ env_adsr, env_exp, env_t60, env_pts, fade, periodic_curve
  * oscillators ...................... sine, saw, square (polyBLEP), tri, additive, modal, fm
  * noise ............................ white, noise_fft (periodic, spectrally shaped), pink, brown, band_noise
  * filters .......................... RBJ biquads (lp/hp/bp/peak/shelves), one-poles, dc_block,
                                       time-varying biquad (tv_filter)
  * physical models .................. ks_pluck (Karplus-Strong, period-block vectorised)
  * effects .......................... pan, chorus, echo, reverb (8-line FDN, block-processed)
  * dynamics ......................... compress, limiter (look-ahead, circular option), soft_clip
  * measurement ...................... lufs (ITU-R BS.1770-4 integrated), momentary_max
  * buffers / io ..................... Buf (stereo mix buffer), fold_loop, loop_crossfade,
                                       trim_silence, finish_sfx, write_wav, read_wav
Everything is deterministic: pass an explicit ``np.random.Generator`` (``rng(seed)``).
"""
from __future__ import annotations

import struct

import numpy as np
from scipy import ndimage
from scipy import signal as sps

SR = 44100
TAU = 2.0 * np.pi


# --------------------------------------------------------------------------- units
def n_of(sec: float) -> int:
    return max(0, int(round(sec * SR)))


def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


_NOTE_IDX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note(name) -> int:
    """'C5' -> 72, 'Bb3' -> 58, 'F#4' -> 66 (numbers pass through)."""
    if not isinstance(name, str):
        return name
    name = name.strip()
    base = _NOTE_IDX[name[0].upper()]
    i = 1
    while i < len(name) and name[i] in "#b":
        base += 1 if name[i] == "#" else -1
        i += 1
    return base + 12 * (int(name[i:]) + 1)


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10.0 ** (np.asarray(d, dtype=float) / 20.0)


def peak(x) -> float:
    return float(np.max(np.abs(x))) if np.size(x) else 0.0


# --------------------------------------------------------------------------- envelopes
def env_exp(n: int, tau: float, attack: float = 0.002, curve: float = 1.0) -> np.ndarray:
    """Linear attack then exponential decay (tau = seconds to 1/e)."""
    t = np.arange(n) / SR
    e = np.exp(-t / max(tau, 1e-5))
    na = min(n, n_of(attack))
    if na > 0:
        e[:na] *= np.linspace(0.0, 1.0, na, endpoint=False) ** curve
    return e


def env_t60(n: int, t60: float, attack: float = 0.002) -> np.ndarray:
    return env_exp(n, t60 / 6.9078, attack)


def env_adsr(n: int, a: float, d: float, s: float, r: float, gate: float | None = None) -> np.ndarray:
    """ADSR. ``gate`` = seconds until release starts (default: n - r)."""
    na, nd, nr = n_of(a), n_of(d), n_of(r)
    ng = n_of(gate) if gate is not None else max(0, n - nr)
    e = np.full(n, float(s))
    t = np.arange(n)
    if na > 0:
        m = t < na
        e[m] = (t[m] / na) ** 0.8
    if nd > 0:
        m = (t >= na) & (t < na + nd)
        x = (t[m] - na) / nd
        e[m] = s + (1.0 - s) * np.exp(-4.0 * x) * (1 - x)
    if ng < n:
        lvl = e[min(ng, n - 1)]
        m = t >= ng
        x = (t[m] - ng) / max(nr, 1)
        e[m] = lvl * np.clip(np.exp(-5.0 * x) * (1 - x), 0, 1)
    return e


def env_pts(points, n: int) -> np.ndarray:
    """Piecewise-linear envelope from [(t_sec, value), ...]."""
    ts = np.array([p[0] for p in points], dtype=float) * SR
    vs = np.array([p[1] for p in points], dtype=float)
    return np.interp(np.arange(n), ts, vs)


def fade(x: np.ndarray, fin: float = 0.002, fout: float = 0.01) -> np.ndarray:
    x = np.array(x, dtype=float, copy=True)
    n = x.shape[-1]
    a, b = min(n_of(fin), n), min(n_of(fout), n)
    if a > 0:
        x[..., :a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b > 0:
        x[..., n - b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return x


def periodic_curve(n: int, r: np.random.Generator, kmin: int = 1, kmax: int = 8, slope: float = 1.0) -> np.ndarray:
    """Smooth random curve, exactly periodic over n samples, normalised to [0, 1] (for loop modulation)."""
    t = np.arange(n) / n
    y = np.zeros(n)
    for k in range(kmin, kmax + 1):
        y += (1.0 / k ** slope) * np.cos(TAU * (k * t + r.random()))
    y -= y.min()
    return y / max(y.max(), 1e-9)


# --------------------------------------------------------------------------- oscillators
def phase(f, n: int, ph0: float = 0.0) -> np.ndarray:
    """Phase in cycles for a constant or per-sample frequency."""
    if np.ndim(f) == 0:
        return ph0 + np.arange(n) * (float(f) / SR)
    f = np.asarray(f, dtype=float)[:n]
    return ph0 + np.concatenate(([0.0], np.cumsum(f[:-1]))) / SR


def sine(f, n: int, ph0: float = 0.0) -> np.ndarray:
    return np.sin(TAU * phase(f, n, ph0))


def _polyblep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    out[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    x = (t[m] - 1.0) / dt[m]
    out[m] = x * x + x + x + 1.0
    return out


def saw(f, n: int, ph0: float = 0.0) -> np.ndarray:
    p = phase(f, n, ph0)
    t = p - np.floor(p)
    if np.ndim(f) == 0:
        dt = np.full(n, float(f) / SR)
    else:
        dt = np.asarray(f, float)[:n] / SR
    dt = np.clip(dt, 1e-6, 0.5)
    return 2.0 * t - 1.0 - _polyblep(t, dt)


def square(f, n: int, pw: float = 0.5, ph0: float = 0.0) -> np.ndarray:
    return 0.5 * (saw(f, n, ph0) - saw(f, n, ph0 + pw))


def additive(f, n: int, partials, fmax: float = 9000.0, ph0: float = 0.0) -> np.ndarray:
    """Additive tone. partials = [(ratio, amp), ...]. Partials above fmax are faded out (anti-alias)."""
    p = phase(f, n, ph0)
    fv = np.asarray(f, dtype=float)
    out = np.zeros(n)
    for ratio, amp in partials:
        fr = fv * ratio
        if np.ndim(fr) == 0:
            if fr >= fmax:
                continue
            out += amp * np.sin(TAU * ratio * p)
        else:
            g = np.clip((fmax - fr[:n]) / (0.1 * fmax), 0.0, 1.0)
            if not g.any():
                continue
            out += amp * g * np.sin(TAU * ratio * p)
    return out


def tri(f, n: int, fmax: float = 9000.0) -> np.ndarray:
    parts = [(k, ((-1) ** ((k - 1) // 2)) / (k * k)) for k in range(1, 40, 2)]
    return additive(f, n, parts, fmax) * (8 / np.pi ** 2)


def modal(f0: float, n: int, modes, r: np.random.Generator | None = None, fmax: float = 9000.0,
          attack: float = 0.0015) -> np.ndarray:
    """Sum of exponentially decaying sinusoids. modes = [(ratio, amp, t60_sec), ...]."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    for ratio, amp, t60 in modes:
        fr = f0 * ratio
        if fr >= fmax:
            continue
        ph = r.uniform(0, 1) if r is not None else 0.0
        out += amp * np.exp(-t * 6.9078 / max(t60, 1e-4)) * np.sin(TAU * (fr * t + ph))
    na = min(n, n_of(attack))
    if na:
        out[:na] *= np.linspace(0, 1, na, endpoint=False)
    return out


def fm(fc, n: int, ratio: float, index, amp=None) -> np.ndarray:
    """Two-operator FM: sin(2pi fc t + index(t) * sin(2pi fc*ratio t))."""
    pc = phase(fc, n)
    pm = phase(np.asarray(fc, dtype=float) * ratio, n)
    idx = np.broadcast_to(np.asarray(index, dtype=float), (n,))
    out = np.sin(TAU * pc + idx * np.sin(TAU * pm))
    return out * amp if amp is not None else out


# --------------------------------------------------------------------------- noise
def white(n: int, r: np.random.Generator) -> np.ndarray:
    return r.standard_normal(n)


def noise_fft(n: int, r: np.random.Generator, shape=None) -> np.ndarray:
    """Periodic (circular) unit-RMS noise of length n with magnitude response shape(freq_hz).
    Built in the frequency domain, so it loops seamlessly at length n."""
    nf = n // 2 + 1
    fr = np.fft.rfftfreq(n, 1.0 / SR)
    mag = np.ones(nf) if shape is None else np.asarray(shape(np.maximum(fr, 1e-3)), dtype=float)
    spec = mag * np.exp(1j * r.uniform(0, TAU, nf)) * r.rayleigh(1.0, nf)
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    s = np.std(x)
    return x / s if s > 0 else x


def pink(n: int, r: np.random.Generator) -> np.ndarray:
    return noise_fft(n, r, lambda f: 1.0 / np.sqrt(np.maximum(f, 20.0)))


def brown(n: int, r: np.random.Generator) -> np.ndarray:
    return noise_fft(n, r, lambda f: 1.0 / np.maximum(f, 20.0))


def band_noise(n: int, r: np.random.Generator, fc: float, octaves: float = 1.0, tilt: float = 0.0) -> np.ndarray:
    """Periodic noise with a log-gaussian band around fc (width in octaves)."""
    return noise_fft(n, r, lambda f: np.exp(-0.5 * (np.log2(f / fc) / (octaves / 2.0)) ** 2) * (f / fc) ** tilt)


# --------------------------------------------------------------------------- filters
def _clampf(f):
    return float(np.clip(f, 5.0, 0.49 * SR))


def bq(kind: str, f: float, q: float = 0.7071, gain_db: float = 0.0):
    """RBJ cookbook biquad -> (b, a). kinds: lp hp bp peak lshelf hshelf notch ap."""
    w0 = TAU * _clampf(f) / SR
    c, s = np.cos(w0), np.sin(w0)
    al = s / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)
    if kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "bp":
        b = [al, 0.0, -al]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "notch":
        b = [1.0, -2 * c, 1.0]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "ap":
        b = [1 - al, -2 * c, 1 + al]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "peak":
        b = [1 + al * A, -2 * c, 1 - al * A]; a = [1 + al / A, -2 * c, 1 - al / A]
    elif kind in ("lshelf", "hshelf"):
        sq = 2 * np.sqrt(A) * al
        if kind == "lshelf":
            b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
            a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
        else:
            b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
            a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    else:
        raise ValueError(kind)
    return np.array(b) / a[0], np.array(a) / a[0]


def filt(x, kind: str, f: float, q: float = 0.7071, gain_db: float = 0.0, order: int = 1):
    """Apply a biquad ``order`` times (along the last axis)."""
    b, a = bq(kind, f, q, gain_db)
    y = np.asarray(x, dtype=float)
    for _ in range(order):
        y = sps.lfilter(b, a, y, axis=-1)
    return y


def filt_circ(x, kind: str, f: float, q: float = 0.7071, gain_db: float = 0.0, order: int = 1):
    """Biquad applied to a LOOP (periodic signal): steady state via a pre-roll of the loop's end."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    pre = min(n, n_of(1.5))
    y = filt(np.concatenate((x[..., n - pre:], x), axis=-1), kind, f, q, gain_db, order)
    return y[..., pre:]


def lp(x, f, q=0.7071, order=1):
    return filt(x, "lp", f, q, order=order)


def hp(x, f, q=0.7071, order=1):
    return filt(x, "hp", f, q, order=order)


def bp(x, f, q=1.0, order=1):
    return filt(x, "bp", f, q, order=order)


def peq(x, f, gain_db, q=1.0):
    return filt(x, "peak", f, q, gain_db)


def shelf_hi(x, f, gain_db, q=0.7071):
    return filt(x, "hshelf", f, q, gain_db)


def shelf_lo(x, f, gain_db, q=0.7071):
    return filt(x, "lshelf", f, q, gain_db)


def onepole_lp(x, f):
    a = np.exp(-TAU * _clampf(f) / SR)
    return sps.lfilter([1 - a], [1, -a], x, axis=-1)


def onepole_hp(x, f):
    return np.asarray(x, float) - onepole_lp(x, f)


def dc_block(x, fc: float = 18.0):
    R = np.exp(-TAU * fc / SR)
    return sps.lfilter([1, -1], [1, -R], x, axis=-1)


def tv_filter(x, kind: str, f, q=0.7071, gain_db: float = 0.0, block: int = 32):
    """Time-varying biquad: coefficients updated every ``block`` samples (f, q may be arrays)."""
    x = np.asarray(x, dtype=float)
    n = x.shape[-1]
    fa = np.broadcast_to(np.asarray(f, dtype=float), (n,))
    qa = np.broadcast_to(np.asarray(q, dtype=float), (n,))
    y = np.empty_like(x)
    zi = np.zeros(x.shape[:-1] + (2,))
    for s in range(0, n, block):
        e = min(n, s + block)
        m = min(n - 1, (s + e) // 2)
        b, a = bq(kind, fa[m], qa[m], gain_db)
        y[..., s:e], zi = sps.lfilter(b, a, x[..., s:e], axis=-1, zi=zi)
    return y


# --------------------------------------------------------------------------- physical models
def ks_pluck(freq: float, dur: float, r: np.random.Generator, t60: float = 2.0, bright: float = 0.6,
             pick: float = 0.18, stretch: float = 0.5, excite: np.ndarray | None = None) -> np.ndarray:
    """Karplus-Strong plucked string (3-tap fractional delay -> accurate tuning), vectorised per period.
    t60: decay of the fundamental; bright: excitation brightness 0..1; pick: pick-position comb;
    stretch: loop-filter weight (0.5 = classic dark, lower = brighter / longer highs)."""
    n = n_of(dur)
    P = SR / freq
    S = float(np.clip(stretch, 0.02, 0.5))
    N = int(np.floor(P - S))
    fr = P - S - N
    h0, h1, h2 = (1 - S) * (1 - fr), (1 - S) * fr + S * (1 - fr), S * fr
    g = 0.001 ** (1.0 / (freq * t60))
    if excite is None:
        ex = r.uniform(-1, 1, N)
        ex = onepole_lp(ex, 300 + 9000 * bright ** 1.5)
        k = int(round(pick * N))
        if k > 0:
            ex = ex - np.concatenate((np.zeros(k), ex[:-k]))
        ex = ex - ex.mean()
        ex /= (np.max(np.abs(ex)) + 1e-9)
    else:
        ex = np.asarray(excite, dtype=float)
    pad = N + 2
    y = np.zeros(pad + n)
    xin = np.zeros(n)
    xin[:min(n, len(ex))] = ex[:n]
    s = pad
    while s < pad + n:
        e = min(s + N, pad + n)
        y[s:e] = xin[s - pad:e - pad] + g * (h0 * y[s - N:e - N] + h1 * y[s - N - 1:e - N - 1]
                                             + h2 * y[s - N - 2:e - N - 2])
        s = e
    out = y[pad:]
    return out - onepole_lp(out, 20.0)


# --------------------------------------------------------------------------- effects
def pan(x, p: float = 0.0):
    """Mono -> stereo (2, n), equal-power (centre = unity on both channels), p in [-1, 1]."""
    th = (np.clip(p, -1, 1) + 1) * np.pi / 4
    x = np.asarray(x, dtype=float)
    return np.stack([x * np.cos(th) * 1.4142, x * np.sin(th) * 1.4142])


def stereo(x):
    x = np.asarray(x, dtype=float)
    return np.stack([x, x]) if x.ndim == 1 else x


def frac_delay_read(x, d, wrap: bool = False):
    """y[n] = x[n - d[n]] with linear interpolation (d in samples, per-sample array)."""
    n = len(x)
    idx = np.arange(n) - d
    if wrap:
        return np.interp(np.mod(idx, n), np.arange(n + 1), np.concatenate((x, x[:1])))
    return np.interp(idx, np.arange(n), x, left=0.0, right=0.0)


def chorus(x, rate: float = 0.35, depth_ms: float = 2.5, base_ms: float = 14.0, mix: float = 0.5,
           voices: int = 2, wrap: bool = False):
    """Stereo chorus -> (2, n). ``wrap`` = treat x as a loop; LFO rates are then snapped so
    they complete whole cycles over the loop (seamless)."""
    xs = stereo(x)
    n = xs.shape[1]
    t = np.arange(n) / SR
    out = np.zeros_like(xs)
    for ch in range(2):
        acc = np.zeros(n)
        for v in range(voices):
            rt = rate * (1 + 0.13 * v + 0.07 * ch)
            if wrap:
                rt = max(1, round(rt * n / SR)) * SR / n
            ph = (v / voices) + ch * 0.25
            d = (base_ms + 3.0 * v + depth_ms * np.sin(TAU * (rt * t + ph))) * SR / 1000.0
            acc += frac_delay_read(xs[ch], d, wrap)
        out[ch] = (1 - mix) * xs[ch] + mix * acc / voices * 1.2
    return out


def echo(x, time: float, fb: float = 0.35, mix: float = 0.3, lp_hz: float = 3500.0, pingpong: bool = True):
    """Feedback delay (block = delay length), returns (2, n) dry + wet."""
    xs = stereo(x)
    n = xs.shape[1]
    D = max(1, n_of(time))
    wet = np.zeros((2, n + D))
    b, a = bq("lp", lp_hz)
    zi = np.zeros((2, 2))
    s = 0
    while s < n:
        e = min(n, s + D)
        prev = wet[:, s:e]
        src = xs[:, s:e] + fb * (prev[::-1] if pingpong else prev)
        src, zi = sps.lfilter(b, a, src, axis=-1, zi=zi)
        wet[:, s + D:e + D] += src
        s = e
    return xs + mix * wet[:, :n]


def _allpass_block(x, D, g):
    y = np.zeros(len(x) + D)
    xp = np.concatenate((np.zeros(D), x))
    n = len(x)
    s = 0
    while s < n:
        e = min(n, s + D)
        y[D + s:D + e] = -g * xp[D + s:D + e] + xp[s:e] + g * y[s:e]
        s = e
    return y[D:]


def reverb(x, rt60: float = 1.8, hf_rt60: float = 0.7, predelay: float = 0.018, size: float = 1.0,
           lo_cut: float = 150.0, hi_cut: float = 6500.0, diffusion: float = 0.6, width: float = 1.0):
    """8-line feedback-delay-network reverb (Householder feedback, Jot one-pole absorption per line,
    Schroeder input diffusers). Block-processed in numpy. Returns the WET signal (2, n), same length
    as the input - zero-pad the input to get the tail."""
    xs = stereo(x)
    n = xs.shape[1]
    xin = hp(lp(xs, hi_cut), lo_cut)
    pd = n_of(predelay)
    if pd:
        xin = np.concatenate((np.zeros((2, pd)), xin[:, :n - pd]), axis=1)
    ap_sets = [(347, 229, 557), (379, 241, 593)]
    for ch in range(2):
        for D in ap_sets[ch]:
            xin[ch] = _allpass_block(xin[ch], int(D * size), diffusion)
    m = (np.array([1153, 1327, 1559, 1693, 1867, 2053, 2251, 2399]) * size).astype(int)
    NL = len(m)
    B = int(min(1024, m.min()))
    Lc = int(2 ** np.ceil(np.log2(m.max() + B + 1)))
    buf = np.zeros((NL, Lc))
    g_dc = 10.0 ** (-3.0 * m / (rt60 * SR))
    g_hf = 10.0 ** (-3.0 * m / (hf_rt60 * SR))
    ratio = g_hf / g_dc
    pole = (1 - ratio) / (1 + ratio)
    zi = np.zeros((NL, 1))
    in_mat = np.zeros((NL, 2))
    sgn = np.array([1, -1, 1, 1, -1, 1, -1, -1], dtype=float)
    in_mat[0::2, 0] = sgn[0::2]
    in_mat[1::2, 1] = sgn[1::2]
    in_mat *= 0.5
    cL = np.array([1, 1, -1, 1, 1, -1, 1, -1], dtype=float) * 0.35
    cR = np.array([1, -1, 1, 1, -1, -1, 1, 1], dtype=float) * 0.35
    cR_eff = cR * width + cL * (1 - width)
    out = np.zeros((2, n))
    ar = np.arange(B)
    rows = np.arange(NL)[:, None]
    for s in range(0, n, B):
        b = min(B, n - s)
        tt = s + ar[:b]
        r = buf[:, tt % Lc]
        damped = np.empty_like(r)
        for i in range(NL):
            damped[i], zi[i] = sps.lfilter([g_dc[i] * (1 - pole[i])], [1.0, -pole[i]], r[i], zi=zi[i])
        out[0, s:s + b] = cL @ damped
        out[1, s:s + b] = cR_eff @ damped
        fbk = damped - (2.0 / NL) * damped.sum(axis=0, keepdims=True)
        w = fbk + in_mat @ xin[:, s:s + b]
        buf[rows, (tt[None, :] + m[:, None]) % Lc] = w
    return out


# --------------------------------------------------------------------------- dynamics
def compress(x, thr_db: float = -18.0, ratio: float = 2.0, tau: float = 0.08, makeup_db: float = 0.0,
             knee_db: float = 6.0, circular: bool = False):
    """Gentle RMS compressor (linked stereo). ``circular`` = treat x as a loop."""
    xs = np.atleast_2d(np.asarray(x, dtype=float))
    n = xs.shape[1]
    if circular:
        y = compress(np.concatenate([xs, xs, xs], axis=1), thr_db, ratio, tau, makeup_db, knee_db, False)
        y = np.atleast_2d(y)[:, n:2 * n]
        return y[0] if np.ndim(x) == 1 else y
    a = np.exp(-1.0 / (tau * SR))
    env = sps.lfilter([1 - a], [1, -a], np.mean(xs ** 2, axis=0))
    lvl = 10 * np.log10(np.maximum(env, 1e-12))
    over = lvl - thr_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    g = undb(-gr + makeup_db)
    a2 = np.exp(-1.0 / (0.03 * SR))
    g = sps.lfilter([1 - a2], [1, -a2], g, zi=[g[0] * a2])[0]
    y = xs * g
    return y[0] if np.ndim(x) == 1 else y


def limiter(x, ceiling_db: float = -1.0, window_ms: float = 8.0, circular: bool = False):
    """Look-ahead brick-wall limiter: per-sample required gain -> centred min filter -> box smoothing
    (never exceeds the requirement). ``circular`` treats the signal as a loop (seamless)."""
    xs = np.atleast_2d(np.asarray(x, dtype=float))
    c = undb(ceiling_db)
    a = np.max(np.abs(xs), axis=0)
    req = np.minimum(1.0, c / np.maximum(a, 1e-12))
    W = max(1, n_of(window_ms / 1000.0))
    mode = "wrap" if circular else "nearest"
    gmin = ndimage.minimum_filter1d(req, size=2 * W + 1, mode=mode)
    g = ndimage.uniform_filter1d(gmin, size=W, mode=mode)
    g = np.minimum(g, req)
    y = np.clip(xs * g, -c, c)
    return y[0] if np.ndim(x) == 1 else y


def soft_clip(x, drive: float = 1.0):
    return np.tanh(drive * np.asarray(x)) / np.tanh(drive)


# --------------------------------------------------------------------------- loudness (BS.1770-4)
def _kweight(x):
    fs = SR
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = np.tan(np.pi * f0 / fs)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = np.tan(np.pi * f0 / fs)
    a0 = 1 + K / Q + K * K
    b2 = [1, -2, 1]
    a2 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    return sps.lfilter(b2, a2, sps.lfilter(b1, a1, x, axis=-1), axis=-1)


def _block_powers(x, dual_mono=True, block=0.4, hop=0.1):
    xs = np.atleast_2d(np.asarray(x, dtype=float))
    z = _kweight(xs) ** 2
    nb, nh = n_of(block), n_of(hop)
    n = z.shape[1]
    if n < nb:
        z = np.concatenate((z, np.zeros((z.shape[0], nb - n))), axis=1)
        n = nb
    cs = np.concatenate((np.zeros((z.shape[0], 1)), np.cumsum(z, axis=1)), axis=1)
    starts = np.arange(0, n - nb + 1, nh)
    pw = ((cs[:, starts + nb] - cs[:, starts]) / nb).sum(axis=0)
    if xs.shape[0] == 1 and dual_mono:
        pw = pw * 2.0
    return pw


def lufs(x, dual_mono: bool = True) -> float:
    """Integrated loudness (gated). Mono is measured as dual-mono (= ffmpeg ebur128 dualmono=true),
    i.e. as heard when a mono file plays on both speakers."""
    pw = _block_powers(x, dual_mono)
    L = -0.691 + 10 * np.log10(np.maximum(pw, 1e-15))
    keep = L > -70
    if not keep.any():
        return -70.0
    rel = -0.691 + 10 * np.log10(pw[keep].mean()) - 10
    keep2 = keep & (L > rel)
    return float(-0.691 + 10 * np.log10(pw[keep2].mean()))


def momentary_max(x, dual_mono: bool = True) -> float:
    pw = _block_powers(x, dual_mono, 0.4, 0.01)
    return float(-0.691 + 10 * np.log10(max(pw.max(), 1e-15)))


# --------------------------------------------------------------------------- buffers & io
class Buf:
    """Growable stereo mix buffer. add(t_sec, mono_or_stereo, gain, pan)."""

    def __init__(self, dur: float = 1.0):
        self.x = np.zeros((2, max(1, n_of(dur))))

    def _ensure(self, n):
        if n > self.x.shape[1]:
            self.x = np.concatenate((self.x, np.zeros((2, n - self.x.shape[1] + SR))), axis=1)

    def add(self, t: float, sig, gain: float = 1.0, p: float = 0.0):
        sig = np.asarray(sig, dtype=float)
        st = pan(sig, p) if sig.ndim == 1 else sig
        i = n_of(t) if t >= 0 else -n_of(-t)
        if i < 0:
            st = st[:, -i:]
            i = 0
        self._ensure(i + st.shape[1])
        self.x[:, i:i + st.shape[1]] += gain * st
        return self

    def get(self, n: int | None = None):
        if n is None:
            return self.x
        self._ensure(n)
        return self.x[:, :n]


def fold_loop(x, L: int):
    """Wrap everything after sample L back onto the start (exact for linear, time-invariant tails)."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    out = x[:, :L].copy()
    s = L
    while s < x.shape[1]:
        e = min(x.shape[1], s + L)
        out[:, :e - s] += x[:, s:e]
        s = e
    return out


def loop_crossfade(x, L: int, xf: int):
    """Seamless loop of length L from a render of >= L + xf samples: material after L is
    equal-power crossfaded over the first xf samples (good for uncorrelated noise beds)."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    out = x[:, :L].copy()
    th = np.linspace(0, np.pi / 2, xf)
    out[:, :xf] = x[:, :xf] * np.sin(th) + x[:, L:L + xf] * np.cos(th)
    return out


def trim_silence(x, thr_db: float = -60.0, pad_ms: float = 2.0):
    xs = np.atleast_2d(np.asarray(x, dtype=float))
    a = np.max(np.abs(xs), axis=0)
    thr = undb(thr_db) * max(a.max(), 1e-12)
    idx = np.nonzero(a > thr)[0]
    if len(idx) == 0:
        return x
    s = max(0, idx[0] - n_of(pad_ms / 1000))
    e = min(xs.shape[1], idx[-1] + n_of(pad_ms / 1000) + 1)
    y = xs[:, s:e]
    return y[0] if np.ndim(x) == 1 else y


def finish_sfx(y, peak_db: float = -1.5, thr_db: float = -56.0, fin: float = 0.001, fout: float = 0.015,
               lowcut: float = 30.0):
    """SFX mastering: high-pass (removes DC/rumble), trim silence, short fades, peak-normalise."""
    y = hp(np.asarray(y, float), lowcut, order=2)
    y = trim_silence(y, thr_db, 1.0)
    dur = y.shape[-1] / SR
    y = fade(y, min(fin, dur / 4), min(fout, dur / 3))
    y = y - np.mean(y, axis=-1, keepdims=True) * fade(np.ones(y.shape[-1]), min(0.004, dur / 4), min(0.004, dur / 4))
    return y / max(peak(y), 1e-12) * undb(peak_db)


def write_wav(path, x):
    """32-bit float WAV (mono if 1-D, else (ch, n))."""
    xs = np.atleast_2d(np.asarray(x, dtype=np.float32))
    ch, n = xs.shape
    data = xs.T.astype("<f4").tobytes()
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 26 + 12 + 8 + len(data)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<IHHIIHHH", 18, 3, ch, SR, SR * ch * 4, ch * 4, 32, 0))
        f.write(b"fact" + struct.pack("<II", 4, n))
        f.write(b"data" + struct.pack("<I", len(data)) + data)


def read_wav(path):
    """Read 16-bit PCM or 32-bit float WAV -> (ch, n) float64."""
    with open(path, "rb") as f:
        raw = f.read()
    pos = 12
    fmt = None
    while pos < len(raw):
        cid, size = raw[pos:pos + 4], struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            _, ch, _, _, _, bits = fmt
            if bits == 32:
                a = np.frombuffer(body, dtype="<f4").astype(float)
            elif bits == 16:
                a = np.frombuffer(body, dtype="<i2").astype(float) / 32768.0
            else:
                raise ValueError("unsupported wav")
            return a.reshape(-1, ch).T
        pos += 8 + size + (size & 1)
    raise ValueError("no data chunk")
