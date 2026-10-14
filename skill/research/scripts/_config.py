"""Load ~/.config/research-drop/env into os.environ and put ~/.local/bin on PATH."""
import os
import shlex

CONF = os.path.expanduser("~/.config/research-drop/env")


def load():
    os.environ["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", "")
    if not os.path.isfile(CONF):
        return
    with open(CONF) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = os.path.expandvars(" ".join(shlex.split(val))) if val else ""
            if val:
                os.environ.setdefault(key.strip(), val)
