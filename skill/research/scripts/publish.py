#!/usr/bin/env python3
"""Publish a finished entry as its own GitHub repo, matching the user's other projects.

Usage: publish.py <entry_dir> <repo-name>

Creates github.com/<user>/<repo-name> (or updates it if this agent made it before),
with the entry's meta.json summary as the description and its tags as topics.
The local copy lives in RESEARCH_PROJECTS_DIR (default ~/Desktop/github projects).
Env: RESEARCH_REPO_VISIBILITY (public|private, default public)
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _config  # noqa: E402

_config.load()

PROJECTS_DIR = os.path.expanduser(os.environ.get("RESEARCH_PROJECTS_DIR", "~/Desktop/github projects"))
VISIBILITY = os.environ.get("RESEARCH_REPO_VISIBILITY", "public")
MARKER = ".research-agent"  # marks repos this agent created, so re-runs update instead of clobbering
SKIP = shutil.ignore_patterns("_spark", "meta.json", ".env", "*.key", "__pycache__", ".DS_Store", "node_modules", ".venv")
GITIGNORE = ".venv/\n__pycache__/\n.DS_Store\n.research-agent\n"


def sh(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check).stdout.strip()


def repo_exists(full_name):
    return subprocess.run(["gh", "repo", "view", full_name], capture_output=True).returncode == 0


def pick_name(user, name):
    """Reuse a repo this agent made; never overwrite one the user made by hand."""
    for candidate in [name] + [f"{name}-{i}" for i in range(2, 20)]:
        local = os.path.join(PROJECTS_DIR, candidate)
        ours = os.path.isfile(os.path.join(local, MARKER))
        if ours or (not repo_exists(f"{user}/{candidate}") and not os.path.exists(local)):
            return candidate, ours
    sys.exit(f"could not find a free repo name for {name}")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, wanted = os.path.abspath(sys.argv[1]), sys.argv[2]
    with open(os.path.join(src, "meta.json")) as f:
        meta = json.load(f)

    user = sh("gh", "api", "user", "--jq", ".login")
    name, updating = pick_name(user, wanted)
    local = os.path.join(PROJECTS_DIR, name)

    if updating:
        sh("git", "pull", "--rebase", "--quiet", cwd=local, check=False)
        for item in os.listdir(local):
            if item not in (".git", MARKER):
                path = os.path.join(local, item)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    else:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        os.makedirs(local)
        sh("git", "init", "-q", "-b", "main", cwd=local)
        with open(os.path.join(local, MARKER), "w") as f:
            f.write("Created by the /research Claude Code skill.\n")

    shutil.copytree(src, local, ignore=SKIP, dirs_exist_ok=True)
    if not os.path.exists(os.path.join(local, ".gitignore")):
        with open(os.path.join(local, ".gitignore"), "w") as f:
            f.write(GITIGNORE)

    sh("git", "add", "-A", cwd=local)
    msg = f"{'Update' if updating else 'Add'} research: {meta.get('title', name)}"
    sh("git", "commit", "-q", "-m", f"{msg}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", cwd=local)

    description = meta.get("summary", "")[:350]
    if updating:
        sh("git", "push", "-q", cwd=local)
        sh("gh", "repo", "edit", f"{user}/{name}", "--description", description)
    else:
        sh("gh", "repo", "create", name, f"--{VISIBILITY}", "--description", description,
           "--source", local, "--remote", "origin", "--push")
    topics = [t.lower().replace(" ", "-")[:50] for t in meta.get("tags", [])][:20]
    if topics:
        sh("gh", "repo", "edit", f"{user}/{name}", *[a for t in topics for a in ("--add-topic", t)], check=False)

    print(f"https://github.com/{user}/{name}")


if __name__ == "__main__":
    main()
