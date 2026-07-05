#!/bin/bash
# SessionEnd hook for Skills Companion: drop a signal file. MUST print nothing
# to stdout (a hook's stdout would be injected into model context) and exit 0.
INPUT="$(cat)"
HOOK_INPUT="$INPUT" /usr/bin/python3 -c '
import json, os, time
try:
    d = json.loads(os.environ.get("HOOK_INPUT") or "{}")
except Exception:
    d = {}
sid = d.get("session_id") or "unknown"
root = os.environ.get("SKILLS_COMPANION_CLAUDE_HOME") or os.path.expanduser("~/.claude")
p = os.path.join(root, "skills-companion", "state", "session-ended")
os.makedirs(p, exist_ok=True)
with open(os.path.join(p, sid + ".json"), "w") as f:
    json.dump({"reason": d.get("reason", "other"), "ts": time.time()}, f)
' >/dev/null 2>&1
exit 0
