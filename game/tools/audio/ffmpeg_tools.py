"""Frost Village audio - ffmpeg helpers shared by build_audio.py and check_audio.py (library).

encode_ogg / encode_mp3 : 44.1 kHz, bit-exact (deterministic bytes), no metadata;
                          the MP3 keeps its LAME/Xing header (encoder delay + padding info
                          for gapless decoders).
ebur128(path)           : ffmpeg ebur128 -> integrated LUFS, max momentary LUFS, sample peak, true peak.
                          Mono files are measured dual-mono (as heard on two speakers); short
                          files are zero-padded by 0.5 s so the 400 ms momentary window is filled.
decode(path)            : any file -> (channels, n) float64 at 44.1 kHz.
"""
from __future__ import annotations

import re
import subprocess

import numpy as np

SR = 44100
_BITEXACT = ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"]


def _run(args):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error"] + args,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + " ".join(args) + "\n" + p.stderr)
    return p


def encode_ogg(src, dst, channels: int, quality: float = 4.0, gain_db: float = 0.0):
    af = ["-af", f"volume={gain_db:.3f}dB"] if gain_db else []
    _run(["-i", str(src)] + af + _BITEXACT + ["-ac", str(channels), "-ar", str(SR),
                                             "-c:a", "libvorbis", "-q:a", f"{quality:g}", str(dst)])


def encode_mp3(src, dst, channels: int, kbps: int, gain_db: float = 0.0):
    af = ["-af", f"volume={gain_db:.3f}dB"] if gain_db else []
    _run(["-i", str(src)] + af + _BITEXACT + ["-ac", str(channels), "-ar", str(SR),
                                             "-c:a", "libmp3lame", "-b:a", f"{kbps}k",
                                             "-id3v2_version", "0", "-write_xing", "1", str(dst)])


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=channels,sample_rate,codec_name:format=duration", "-of", "default=nw=1",
                        str(path)], capture_output=True, text=True)
    d = dict(line.split("=", 1) for line in p.stdout.split() if "=" in line)
    return {"channels": int(d.get("channels", 0)), "sample_rate": int(d.get("sample_rate", 0)),
            "codec": d.get("codec_name", "?"), "duration": float(d.get("duration", "nan"))}


def ebur128(path, channels: int | None = None):
    """-> dict(I=integrated LUFS, M=max momentary LUFS, peak=sample peak dBFS, tpk=true peak dBFS)."""
    if channels is None:
        channels = probe(path)["channels"]
    flt = "apad=pad_dur=0.5,ebur128=peak=sample+true" + (":dualmono=true" if channels == 1 else "")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-i", str(path), "-af", flt,
                        "-f", "null", "-"], capture_output=True, text=True)
    err = p.stderr
    ms = [float(v) for v in re.findall(r"\bM:\s*(-?[\d.]+|-inf)", err) if v != "-inf"]
    summ = err[err.rfind("Summary:"):]
    I = float(re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", summ).group(1).replace("-inf", "-120"))
    pk = re.findall(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", summ)
    vals = [float(v) if v != "-inf" else -120.0 for v in pk]
    return {"I": I, "M": max(ms) if ms else -120.0, "peak": vals[0] if vals else 0.0,
            "tpk": vals[1] if len(vals) > 1 else 0.0}


def decode(path, channels: int | None = None) -> np.ndarray:
    if channels is None:
        channels = probe(path)["channels"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "f32le", "-ac", str(channels),
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(float).reshape(-1, channels).T


def ogg_tail(path):
    """Last Vorbis packets of an .ogg -> {'discard': end-padding samples the decoder must drop,
    'last_pts': start of the last packet, 'end': last valid sample, 'bounds': packet starts
    (= block boundaries) near the end}. Browsers that ignore the end-trim (Chromium's
    decodeAudioData) return `discard` extra samples, so loops need discard == 0."""
    import json
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_packets", "-show_entries",
                        "packet=pts,duration:packet_side_data", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    pk = json.loads(p.stdout)["packets"]
    last = pk[-1]
    disc = 0
    for sd in last.get("side_data_list", []):
        if sd.get("side_data_type") == "Skip Samples":
            disc = int(sd.get("discard_padding", 0))
    return {"discard": disc, "last_pts": int(last["pts"]), "end": int(last["pts"]) + int(last["duration"]),
            "bounds": [int(q["pts"]) for q in pk[-12:]]}          # block boundaries near the end


def mp3_gapless(path):
    """LAME/Info tag of an .mp3 -> (encoder delay, end padding) in samples, or None.
    A decoder that ignores the tag outputs delay + 529 extra samples before the audio
    (529 = mp3 decoder delay) and the padding after it."""
    with open(path, "rb") as f:
        b = f.read(512)
    for off in (36, 21, 13):                     # MPEG-1 stereo / mono, MPEG-2 mono
        if b[off:off + 4] in (b"Info", b"Xing"):
            flags = int.from_bytes(b[off + 4:off + 8], "big")
            p = off + 8 + (4 if flags & 1 else 0) + (4 if flags & 2 else 0) + (100 if flags & 4 else 0) + \
                (4 if flags & 8 else 0)
            v = int.from_bytes(b[p + 21:p + 24], "big")
            return v >> 12, v & 4095
    return None
