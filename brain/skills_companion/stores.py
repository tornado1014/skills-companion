import json
import os
import shutil
import tempfile
import time

from . import paths

DEFAULT_CONFIG = {
    "default_policy": "ask",       # ask | auto-revert | keep
    "per_plugin": {},              # plugin_key -> policy
    "notifications_enabled": False,
    "poll_seconds": 20,
}


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_write_json(path, data, backup=False):
    path = str(path)
    if backup and os.path.exists(path):
        ts = time.strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, f"{path}.bak.{ts}")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(read_json(paths.config_path(), {}))
    cfg.setdefault("per_plugin", {})
    return cfg


def save_config(cfg):
    atomic_write_json(paths.config_path(), cfg)


def policy_for(plugin, cfg):
    return cfg.get("per_plugin", {}).get(plugin, cfg.get("default_policy", "ask"))


def load_ledger():
    return read_json(paths.ledger_path(), {})


def save_ledger(ledger):
    atomic_write_json(paths.ledger_path(), ledger)


def ledger_add(session_id, plugin, cwd=""):
    ledger = load_ledger()
    entries = ledger.setdefault(session_id, [])
    if not any(e["plugin"] == plugin for e in entries):
        entries.append({"plugin": plugin, "activated_at": time.time(), "cwd": cwd})
    save_ledger(ledger)
    return ledger


def ledger_remove(session_id, plugin=None):
    ledger = load_ledger()
    if plugin is None:
        ledger.pop(session_id, None)
    elif session_id in ledger:
        ledger[session_id] = [e for e in ledger[session_id] if e["plugin"] != plugin]
        if not ledger[session_id]:
            ledger.pop(session_id)
    save_ledger(ledger)
    return ledger
