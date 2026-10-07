"""Frost Village - render a 30 s 'gameplay soundscape' demo from the delivered assets (preview only).

Decodes assets/audio/*.ogg exactly as the game plays them, applies the manifest base volume x the
call-site volume / playback rate used in src/ (e.g. footsteps x0.32, rising pickup pitch, pad-fill
ticks speeding up, station sfx x0.45), over the village music and ambience. Lets a designer hear
the mix in one file and prints a loudness timeline (music bed vs sfx layer).

Run:  python3 tools/audio/demo_mix.py     -> docs/previews/audio_mix_demo.ogg (+ .mp3)
Deterministic. Needs numpy + scipy + ffmpeg. Not part of the game payload.
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
PREV = os.path.join(ROOT, "docs", "previews")
DUR = 30.0


def main():
    with open(os.path.join(AUD, "manifest.json")) as f:
        man = json.load(f)
    audio, groups = man["audio"], man["audioGroups"]
    cache = {}

    def get(key):
        if key not in cache:
            ch = 1 if audio[key]["kind"] == "sfx" else 2
            cache[key] = F.decode(os.path.join(AUD, f"{key}.ogg"), ch)
        return cache[key]

    r = np.random.default_rng(7)
    n = S.n_of(DUR)
    bed = np.zeros((2, n))
    fx = np.zeros((2, n))
    variant = {}

    def sfx(t, key, vol=1.0, rate=1.0, pan=0.0):
        if key in groups:
            opts = groups[key]
            i = int(r.integers(len(opts)))
            if len(opts) > 1 and i == variant.get(key):
                i = (i + 1) % len(opts)
            variant[key] = i
            key = opts[i]
        x = get(key)[0]
        if rate != 1.0:                                  # playback-rate change = resample (pitch + speed)
            m = int(len(x) / rate)
            x = np.interp(np.arange(m) * rate, np.arange(len(x)), x)
        g = audio[key]["volume"] * vol
        st = S.pan(x, pan)                               # centre = mono on both speakers at unity (WebAudio up-mix)
        i = S.n_of(t)
        e = min(n, i + st.shape[1])
        fx[:, i:e] += g * st[:, :e - i]

    def loop(key, vol, t0=0.0, t1=DUR, fade=1.2):
        x = get(key)
        reps = int(np.ceil(n / x.shape[1])) + 1
        y = np.tile(x, reps)[:, :n]
        env = np.clip((np.arange(n) / S.SR - t0) / fade, 0, 1) * np.clip((t1 - np.arange(n) / S.SR) / fade, 0, 1)
        bed[:] += audio[key]["volume"] * vol * y * env

    loop("bgm_village", 1.0, 0.0, DUR + 5)
    loop("amb_wind", 0.6)
    loop("amb_sea", 0.8, 0.0, 12.0)
    loop("amb_fire", 0.7, 19.0, DUR + 5)

    def walk(t0, t1):
        t = t0
        while t < t1:
            sfx(t, "sfx_step_snow", 0.32, 0.9 + 0.2 * r.random(), r.uniform(-0.1, 0.1))
            t += 0.31
    walk(0.4, 2.8)
    got = 0
    for k in range(4):                                   # chop a tree, logs pop onto the stack
        t = 3.0 + k * 0.57
        sfx(t, "sfx_chop", 1.0, 1.0, -0.15)
        sfx(t + 0.28, "sfx_pickup", 0.6, 1 + got * 0.08)
        got += 1
    sfx(5.6, "sfx_splash", 0.5, 1.0, 0.4)                # fisherman worker nearby
    sfx(6.0, "sfx_reel", 0.3, 1.0, 0.4)
    walk(5.6, 7.6)
    for k in range(5):                                   # unload into the station
        sfx(7.8 + k * 0.12, "sfx_drop", 0.35, 1.1 + 0.2 * r.random())
    sfx(8.2, "sfx_sizzle", 0.45, 1.0, 0.2)
    sfx(9.0, "sfx_sizzle", 0.45, 1.0, 0.2)
    sfx(9.3, "sfx_drop", 0.35, 1.2)
    sfx(10.0, "sfx_customer_happy", 0.7, 1.0, -0.2)       # customer served
    for k in range(4):
        sfx(10.25 + k * 0.08, "sfx_coin", 0.4, 0.95 + 0.2 * r.random(), -0.2)
    sfx(11.2, "sfx_coins_many", 0.9)                      # collect the cash pile
    walk(11.6, 13.0)
    t, paid = 13.2, 0.0
    while t < 14.8:                                      # pay into an unlock pad
        sfx(t, "sfx_pad_fill", 0.5, 0.85 + 0.7 * paid)
        paid = min(1.0, paid + 0.07 / 1.6)
        t += 0.07
    sfx(14.85, "sfx_unlock", 1.0)
    walk(16.8, 18.0)
    for k in range(3):                                   # mine
        sfx(18.2 + k * 0.57, "sfx_mine", 1.0, 1.0, 0.1)
        sfx(18.5 + k * 0.57, "sfx_pickup", 0.6, 1 + (got + k) * 0.08)
    sfx(20.2, "sfx_smelt", 0.45, 1.0, -0.3)
    for k in range(2):
        sfx(21.0 + k * 0.7, "sfx_harvest", 1.0, 1.0, 0.2)
    sfx(22.0, "sfx_oven", 0.45, 1.0, 0.3)
    sfx(22.6, "sfx_saw", 0.45, 1.0, -0.4)
    sfx(23.4, "sfx_bow", 0.6, 1.0, 0.3)
    sfx(23.75, "sfx_hit_animal", 0.8, 1.0, 0.35)
    sfx(24.0, "sfx_animal_deer", 0.6, 1.0, 0.35)
    sfx(24.9, "sfx_animal_boar", 0.35, 1.0, -0.4)
    sfx(25.6, "sfx_hire", 1.0)
    sfx(27.3, "sfx_click", 1.0)
    sfx(27.5, "sfx_whoosh", 1.0)
    sfx(27.9, "sfx_levelup", 1.0)
    sfx(29.3, "sfx_error", 0.4)

    mix = bed + fx
    pk = S.peak(mix)
    if pk > S.undb(-1.0):
        mix = S.limiter(mix, -1.0, 5.0)
    os.makedirs(PREV, exist_ok=True)
    wav = os.path.join(HERE, "_cache", "audio_mix_demo.wav")
    S.write_wav(wav, mix)
    F.encode_ogg(wav, os.path.join(PREV, "audio_mix_demo.ogg"), 2, 4)
    F.encode_mp3(wav, os.path.join(PREV, "audio_mix_demo.mp3"), 2, 128)
    print(f"music+ambience bed: {S.lufs(bed):.1f} LUFS   sfx layer: {S.lufs(fx):.1f} LUFS   "
          f"mix: {S.lufs(mix):.1f} LUFS, peak {S.db(pk):.1f} dBFS")
    print("timeline (1 s windows, momentary LUFS)   bed | sfx")
    for s in range(int(DUR)):
        a, b = S.n_of(s), S.n_of(s + 1)
        print(f"  {s:2d}s  {S.momentary_max(bed[:, a:b]):6.1f} | {S.momentary_max(fx[:, a:b]) if np.any(fx[:, a:b]) else -99:6.1f}")
    print("wrote docs/previews/audio_mix_demo.ogg / .mp3")


if __name__ == "__main__":
    main()
