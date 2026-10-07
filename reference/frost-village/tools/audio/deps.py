"""Frost Village audio tools - dependency check (imported first by every entry script).

The synthesis code needs numpy + scipy (+ Pillow for preview images) and the ffmpeg CLI.
If scipy is missing from the running interpreter but the build venv exists at
/tmp/fv_audio_venv (created with `python3 -m venv --system-site-packages /tmp/fv_audio_venv`
and `pip install scipy`), the script transparently re-runs itself with that interpreter.
On another PC simply:  python3 -m pip install numpy scipy pillow   (and install ffmpeg).
"""
from __future__ import annotations

import os
import shutil
import sys

VENV_PY = "/tmp/fv_audio_venv/bin/python"


def ensure() -> None:
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
    except ImportError:
        if os.path.exists(VENV_PY) and os.path.abspath(sys.prefix) != "/tmp/fv_audio_venv":
            os.execv(VENV_PY, [VENV_PY] + sys.argv)
        sys.exit("Frost Village audio tools need numpy + scipy + pillow:\n"
                 "    python3 -m pip install numpy scipy pillow")
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH (needs libvorbis + libmp3lame).")
