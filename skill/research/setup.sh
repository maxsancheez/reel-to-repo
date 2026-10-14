#!/bin/zsh
# One-time setup for /research: installs gh, yt-dlp and ffmpeg (~130 MB total) to ~/.local/bin, logs into GitHub,
# and writes a config file (~/.config/research-drop/env).
set -e
BIN="$HOME/.local/bin"; mkdir -p "$BIN"
ARCH=$(uname -m); [ "$ARCH" = "x86_64" ] && ARCH=amd64

if ! command -v gh >/dev/null && [ ! -x "$BIN/gh" ]; then
  echo "Installing GitHub CLI..."
  URL=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest \
    | python3 -c "import json,sys; print(next(a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if 'macOS_$ARCH' in a['name'] and a['name'].endswith('.zip')))")
  TMP=$(mktemp -d); curl -fsSL "$URL" -o "$TMP/gh.zip"; unzip -q "$TMP/gh.zip" -d "$TMP"
  cp "$TMP"/gh_*/bin/gh "$BIN/gh"; rm -rf "$TMP"
fi

if ! command -v yt-dlp >/dev/null && [ ! -x "$BIN/yt-dlp" ]; then
  echo "Installing yt-dlp..."
  curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos -o "$BIN/yt-dlp"
  chmod +x "$BIN/yt-dlp"
fi

if ! command -v ffmpeg >/dev/null && [ ! -x "$BIN/ffmpeg" ]; then
  echo "Installing ffmpeg (for pulling frames out of reels)..."
  TMP=$(mktemp -d); python3 -m venv "$TMP/v"
  "$TMP/v/bin/pip" install -q --no-cache-dir --upgrade pip
  "$TMP/v/bin/pip" install -q --no-cache-dir imageio-ffmpeg
  cp "$("$TMP/v/bin/python" -c 'import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())')" "$BIN/ffmpeg"
  chmod +x "$BIN/ffmpeg"; rm -rf "$TMP"
fi

grep -q '.local/bin' ~/.zshrc 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
export PATH="$BIN:$PATH"

gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git

CONF="$HOME/.config/research-drop/env"
if [ ! -f "$CONF" ]; then
  mkdir -p "$(dirname "$CONF")"
  cat > "$CONF" <<'EOF'
export RESEARCH_PROJECTS_DIR="$HOME/Desktop/github projects"
export RESEARCH_REPO_VISIBILITY="public"
# Reels are fetched with your Chrome login. Set to "none" to turn that off.
export YTDLP_COOKIES_BROWSER="chrome"
# Local voice transcription: on by default, installs temporarily per run and deletes itself.
# Set to "off" to skip it (runs ~5 min faster). WHISPER_MODEL=small is more accurate.
export LOCAL_TRANSCRIBE="on"
export WHISPER_MODEL="base"
EOF
  chmod 600 "$CONF"
fi

echo
echo "Done. Paste a link into Claude Code with /research to try it."
echo "(The first reel triggers a macOS prompt for Chrome Safe Storage: click Always Allow.)"
