#!/usr/bin/env python3
"""Pull everything useful out of a short-video URL so Claude can "watch" it.

Usage: fetch_reel.py <url> <out_dir>   -> prints a JSON summary to stdout

Writes to <out_dir>:
  video.mp4            the reel (<=720p)
  frames/f_###.jpg     evenly spaced stills, 720px wide (for zooming in)
  sheet_#.jpg          contact sheets of 6 frames each (look at these first)
  captions.txt         platform captions/auto-subs if the site has them

Uses your Chrome login by default (YTDLP_COOKIES_BROWSER=none to disable).
Needs yt-dlp and ffmpeg on PATH (installed by setup.sh). Nothing here needs an API key.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

_config.load()

MIN_FRAMES, MAX_FRAMES = 8, 24
META_KEYS = ("title", "uploader", "channel", "description", "duration", "upload_date",
             "view_count", "like_count", "comment_count", "webpage_url", "tags")


def ytdlp(args, timeout=300):
    """Run yt-dlp with the user's Chrome cookies, falling back to logged-out."""
    base = ["yt-dlp", "--no-warnings", "--no-playlist", "--no-cache-dir"]
    if shutil.which("ffmpeg"):
        base += ["--ffmpeg-location", shutil.which("ffmpeg")]
    browser = os.environ.get("YTDLP_COOKIES_BROWSER", "chrome")
    attempts = [["--cookies-from-browser", browser]] if browser and browser != "none" else []
    attempts.append([])
    err = None
    for extra in attempts:
        try:
            return subprocess.run(base + extra + args, capture_output=True, text=True,
                                  check=True, timeout=timeout).stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            err = e
    raise err


def vtt_to_text(path):
    lines, seen = [], set()
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = re.sub(r"<[^>]+>", "", line).strip()
            if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")) or line.isdigit():
                continue
            if line not in seen:  # auto-subs repeat each line as it scrolls
                seen.add(line)
                lines.append(line)
    return " ".join(lines)


def probe_duration(video):
    """Instagram often omits duration; read it from the file header instead."""
    out = subprocess.run(["ffmpeg", "-i", video], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    url, out = sys.argv[1], os.path.abspath(sys.argv[2])
    os.makedirs(out, exist_ok=True)
    result = {"url": url, "errors": []}

    # 1. Metadata, caption, and top comments (comments are slow on some sites, so try twice)
    meta = None
    for extra in (["--get-comments", "--extractor-args", "youtube:max_comments=40,all,0"], []):
        try:
            meta = json.loads(ytdlp(["-J"] + extra + [url], timeout=120))
            break
        except Exception as e:
            result["errors"].append(f"metadata{' (with comments)' if extra else ''}: {str(getattr(e, 'stderr', e))[-300:]}")
    if meta is None:
        print(json.dumps(result, indent=2))
        return
    result.update({k: meta.get(k) for k in META_KEYS})
    comments = sorted(meta.get("comments") or [], key=lambda c: c.get("like_count") or 0, reverse=True)
    result["top_comments"] = [{"text": c.get("text", "")[:400], "likes": c.get("like_count")} for c in comments[:25]]

    # 2. Video, then platform captions separately so a caption failure can't block the video
    try:
        ytdlp(["-S", "res:720,ext:mp4", "--merge-output-format", "mp4",
               "-o", os.path.join(out, "video.%(ext)s"), url])
    except Exception as e:
        result["errors"].append(f"download: {str(getattr(e, 'stderr', e))[-300:]}")
    try:
        ytdlp(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en,en-orig,en-US,en-GB",
               "--sub-format", "vtt", "-o", os.path.join(out, "video.%(ext)s"), url], timeout=60)
    except Exception:
        pass  # many reels have no captions; the local transcriber covers that

    subs = sorted(glob.glob(os.path.join(out, "video*.vtt")))
    if subs:
        text = vtt_to_text(subs[0])
        with open(os.path.join(out, "captions.txt"), "w") as f:
            f.write(text)
        result["captions_file"] = os.path.join(out, "captions.txt")
        result["captions_preview"] = text[:600]

    videos = [p for p in glob.glob(os.path.join(out, "video.*")) if not p.endswith(".vtt")]
    if not videos:
        print(json.dumps(result, indent=2))
        return
    video = videos[0]
    result["video"] = video

    # 3. Frames + contact sheets
    if shutil.which("ffmpeg"):
        frames_dir = os.path.join(out, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        duration = float(meta.get("duration") or probe_duration(video) or 30)
        n = max(MIN_FRAMES, min(MAX_FRAMES, int(duration / 2)))
        fps = n / max(duration, 1)
        ff = ["ffmpeg", "-v", "error", "-y"]
        try:
            subprocess.run(ff + ["-i", video, "-vf", f"fps={fps:.4f},scale=720:-2", "-q:v", "3",
                                 os.path.join(frames_dir, "f_%03d.jpg")], check=True, timeout=180)
            subprocess.run(ff + ["-i", os.path.join(frames_dir, "f_%03d.jpg"),
                                 "-vf", "scale=360:-2,tile=3x2:padding=4:color=white", "-q:v", "3",
                                 os.path.join(out, "sheet_%d.jpg")], check=True, timeout=180)
        except Exception as e:
            result["errors"].append(f"frames: {e}")
        result["frames"] = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
        result["sheets"] = sorted(glob.glob(os.path.join(out, "sheet_*.jpg")))
        result["seconds_per_frame"] = round(1 / fps, 1)
    else:
        result["errors"].append("ffmpeg not installed: no frames (run setup.sh)")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
