import copy
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
    "wizard_completed": False,
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
    cfg = copy.deepcopy(DEFAULT_CONFIG)
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


def history_add(cwd, plugin_key):
    hist = read_json(paths.activation_history_path(), {})
    if not cwd:
        return hist
    entry = hist.setdefault(cwd, {}).setdefault(
        plugin_key, {"count": 0, "last_ts": 0.0})
    entry["count"] += 1
    entry["last_ts"] = time.time()
    atomic_write_json(paths.activation_history_path(), hist)
    return hist


def history_for(cwd):
    hist = read_json(paths.activation_history_path(), {})
    return {k: v.get("count", 0) for k, v in hist.get(cwd or "", {}).items()}


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
