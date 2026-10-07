"""Frost Village - audio preview images (waveform thumbnails + spectrograms) with Pillow.

Library used by build_audio.py / check_audio.py; can also be run directly to make a
spectrogram of any wav/ogg/mp3:  python3 tools/audio/preview.py in.ogg out.png
"""
from __future__ import annotations

import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SR = 44100
BG = (24, 30, 44)
FG = (120, 200, 255)
FG2 = (255, 196, 92)
GRID = (52, 62, 82)
TXT = (230, 236, 245)


def font(size=12):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def decode(path) -> np.ndarray:
    """Decode any audio file with ffmpeg -> (ch, n) float at 44.1 kHz."""
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                           "stream=channels", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    ch = int(info.stdout.strip() or 1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", str(ch), "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(float).reshape(-1, ch).T


def waveform(x, w=360, h=64, color=FG, loop_marks=False) -> Image.Image:
    xs = np.atleast_2d(x)
    m = xs.mean(axis=0) if xs.shape[0] > 1 else xs[0]
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.line([(0, h // 2), (w, h // 2)], fill=GRID)
    for lvl in (0.5, 0.891):  # -6 dB, -1 dB
        for s in (-1, 1):
            y = h / 2 - s * lvl * (h / 2 - 1)
            d.line([(0, y), (w, y)], fill=GRID if lvl < 0.8 else (90, 60, 60))
    n = len(m)
    edges = np.linspace(0, n, w + 1).astype(int)
    for i in range(w):
        seg = xs[:, edges[i]:max(edges[i] + 1, edges[i + 1])]
        if seg.size == 0:
            continue
        lo, hi = seg.min(), seg.max()
        rms = np.sqrt(np.mean(seg ** 2))
        d.line([(i, h / 2 - hi * (h / 2 - 1)), (i, h / 2 - lo * (h / 2 - 1))], fill=tuple(int(c * 0.55) for c in color))
        d.line([(i, h / 2 - rms * (h / 2 - 1)), (i, h / 2 + rms * (h / 2 - 1))], fill=color)
    if loop_marks:
        d.line([(0, 0), (0, h)], fill=FG2)
        d.line([(w - 1, 0), (w - 1, h)], fill=FG2)
    return img


def spectrogram(x, w=900, h=260, fmax=12000.0, nfft=2048, db_range=80.0) -> Image.Image:
    xs = np.atleast_2d(x)
    m = xs.mean(axis=0)
    hop = max(1, (len(m) - nfft) // w) if len(m) > nfft else 1
    win = np.hanning(nfft)
    frames = []
    for i in range(w):
        s = i * hop
        seg = m[s:s + nfft]
        if len(seg) < nfft:
            seg = np.pad(seg, (0, nfft - len(seg)))
        frames.append(np.abs(np.fft.rfft(seg * win)))
    S = np.array(frames).T
    fr = np.fft.rfftfreq(nfft, 1 / SR)
    keep = fr <= fmax
    S = 20 * np.log10(S[keep] + 1e-9)
    S -= S.max()
    S = np.clip((S + db_range) / db_range, 0, 1)
    # log-ish frequency axis
    fk = fr[keep]
    ys = np.geomspace(40, fmax, h)[::-1]
    rows = np.array([S[np.argmin(np.abs(fk - y))] for y in ys])
    r = np.clip(rows * 1.4 - 0.2, 0, 1)
    g = np.clip(rows * 1.6 - 0.6, 0, 1)
    b = np.clip(0.25 + rows * 0.9 - g * 0.6, 0, 1)
    rgb = (np.stack([r * 255, g * 255, b * 200 + 30], axis=-1)).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB")
    d = ImageDraw.Draw(img)
    f = font(10)
    for fh in (100, 1000, 4000, 8000):
        y = int(np.argmin(np.abs(ys - fh)))
        d.line([(0, y), (12, y)], fill=TXT)
        d.text((14, y - 6), f"{fh if fh < 1000 else str(fh // 1000) + 'k'}", fill=TXT, font=f)
    return img


if __name__ == "__main__":
    a = decode(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else "spec.png"
    im = Image.new("RGB", (900, 340), BG)
    im.paste(spectrogram(a), (0, 0))
    im.paste(waveform(a, 900, 80), (0, 260))
    im.save(out)
    print("wrote", out)
