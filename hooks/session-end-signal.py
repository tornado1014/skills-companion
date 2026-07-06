#!/usr/bin/env python3
"""SessionEnd hook for Skills Companion: drop a signal file the resident shell
polls. Cross-platform (used directly on Windows via `py`, and works on macOS/
Linux too). MUST print nothing to stdout (a hook's stdout is injected into the
model context) and exit 0 no matter what."""
import json
import os
import sys
import time


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    sid = d.get("session_id") or "unknown"
    root = os.environ.get("SKILLS_COMPANION_CLAUDE_HOME") or os.path.expanduser("~/.claude")
    p = os.path.join(root, "skills-companion", "state", "session-ended")
    os.makedirs(p, exist_ok=True)
    tmp = os.path.join(p, sid + ".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"reason": d.get("reason", "other"), "ts": time.time()}, f)
    os.replace(tmp, os.path.join(p, sid + ".json"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
