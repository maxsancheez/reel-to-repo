#!/usr/bin/env python3
"""Transcribe a video/audio file on this Mac with Whisper, leaving nothing behind.

Usage: transcribe_local.py <media_file> <out_txt>

Builds a throwaway Python environment and model download (~400 MB, ~5 min)
inside ~/.cache/research-drop, transcribes, then deletes all of it, even on failure.
No API key, nothing sent off this machine except the package/model downloads.
Env: WHISPER_MODEL (default "base"; "small" is more accurate but ~2x the download)
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.expanduser("~/.cache/research-drop")

RUNNER = r'''
import sys, warnings
warnings.filterwarnings("ignore")
from faster_whisper import WhisperModel
model = WhisperModel(sys.argv[3], device="cpu", compute_type="int8")
segments, info = model.transcribe(sys.argv[1], vad_filter=True)
lines = [f"[{int(s.start)//60}:{int(s.start)%60:02d}] {s.text.strip()}" for s in segments]
open(sys.argv[2], "w").write(f"language: {info.language}\n" + "\n".join(lines) + "\n")
'''


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    media, out_txt = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(ROOT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="whisper-", dir=ROOT)
    env = dict(os.environ, HF_HOME=os.path.join(tmp, "hf"), PIP_NO_CACHE_DIR="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", HF_HUB_DISABLE_TELEMETRY="1")
    try:
        venv = os.path.join(tmp, "venv")
        py = os.path.join(venv, "bin", "python")
        subprocess.run([sys.executable, "-m", "venv", venv], check=True)
        subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True, env=env)
        subprocess.run([py, "-m", "pip", "install", "-q", "faster-whisper"], check=True, env=env)
        subprocess.run([py, "-c", RUNNER, media, out_txt, os.environ.get("WHISPER_MODEL", "base")],
                       check=True, env=env, stderr=subprocess.DEVNULL)
        with open(out_txt) as f:
            print(f.read())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
