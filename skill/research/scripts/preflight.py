#!/usr/bin/env python3
"""Check that /research can run. Prints one status line per dependency; exits 1 if blocked."""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

_config.load()

gh_ok = shutil.which("gh") and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0
print("github:     " + ("ok" if gh_ok else "MISSING - run ~/.claude/skills/research/setup.sh"))
print("yt-dlp:     " + ("ok" if shutil.which("yt-dlp") else "missing - reels will fall back to page text"))
print("ffmpeg:     " + ("ok" if shutil.which("ffmpeg") else "missing - no frames from reels"))
print("transcribe: " + ("off" if os.environ.get("LOCAL_TRANSCRIBE") == "off" else "on (local, temporary)"))
sys.exit(0 if gh_ok else 1)
