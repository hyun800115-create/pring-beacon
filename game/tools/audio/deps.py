"""Frost Village audio tools - dependency check (imported first by every entry script).

The synthesis code needs numpy + scipy (+ Pillow for preview images) and the ffmpeg CLI.
If scipy is missing from the running interpreter but the build venv exists at
<저장소>/.cache/venv (CLAUDE.md 의 환경 설정 참고
and `pip install scipy`), the script transparently re-runs itself with that interpreter.
On another PC simply:  python3 -m pip install numpy scipy pillow   (and install ffmpeg).
"""
from __future__ import annotations

import os
import shutil
import sys

# 저장소/.cache 에 있는 가상환경과 ffmpeg 를 쓴다 (윈도우: Scripts/python.exe, 리눅스: bin/python).
REPO_CACHE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".cache"))
VENV_DIR = os.path.join(REPO_CACHE, "venv")
VENV_PY = os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "python")
_BIN = os.path.join(REPO_CACHE, "bin")
if os.path.isdir(_BIN) and _BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")


def ensure() -> None:
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
    except ImportError:
        if os.path.exists(VENV_PY) and os.path.normcase(os.path.abspath(sys.prefix)) != os.path.normcase(VENV_DIR):
            import subprocess; sys.exit(subprocess.call([VENV_PY] + sys.argv))  # 윈도우는 execv 가 불안정
        sys.exit("Frost Village audio tools need numpy + scipy + pillow:\n"
                 "    python3 -m pip install numpy scipy pillow")
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH (needs libvorbis + libmp3lame).")
