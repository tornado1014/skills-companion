import json
import os
import subprocess
from pathlib import Path

from skills_companion import installer, paths, stores

HOOK = "/repo/hooks/session-end-signal.sh"


def test_add_hook_idempotent():
    s = {}
    installer.add_session_end_hook(s, HOOK)
    installer.add_session_end_hook(s, HOOK)
    assert len(s["hooks"]["SessionEnd"]) == 1
    assert s["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"bash {HOOK}"


def test_remove_cheatsheet_hook_only():
    s = {"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "korean-law-key-sync.py"}]},
        {"matcher": "startup",
         "hooks": [{"type": "command",
                    "command": "bash /Users/x/.claude/skills-cheatsheet/open.sh"}]},
    ]}}
    installer.remove_cheatsheet_hook(s)
    entries = s["hooks"]["SessionStart"]
    assert len(entries) == 1
    assert "korean-law" in entries[0]["hooks"][0]["command"]


def test_install_hooks_applies_with_backup(claude_home):
    r = installer.install_hooks(HOOK)
    assert r["ok"]
    s = stores.read_json(paths.settings_path(), {})
    assert s["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"bash {HOOK}"
    assert list(claude_home.glob("settings.json.bak.*"))
    r2 = installer.uninstall_hooks(HOOK)
    assert r2["ok"]
    s2 = stores.read_json(paths.settings_path(), {})
    assert s2["hooks"]["SessionEnd"] == []


def test_hook_script_writes_signal(claude_home):
    script = Path(__file__).resolve().parents[2] / "hooks" / "session-end-signal.sh"
    payload = json.dumps({"session_id": "HOOKSESS", "reason": "prompt_input_exit",
                          "hook_event_name": "SessionEnd"})
    env = dict(os.environ, SKILLS_COMPANION_CLAUDE_HOME=str(claude_home))
    p = subprocess.run(["bash", str(script)], input=payload, text=True,
                       capture_output=True, env=env)
    assert p.returncode == 0
    assert p.stdout == ""                                  # zero stdout!
    sig = claude_home / "skills-companion" / "state" / "session-ended" / "HOOKSESS.json"
    assert sig.exists()
    assert json.loads(sig.read_text())["reason"] == "prompt_input_exit"
