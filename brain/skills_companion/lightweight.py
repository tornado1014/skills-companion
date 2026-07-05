import json
import shutil
import subprocess
from pathlib import Path

from . import paths, stores

VALID_TOOL_SEARCH = ("auto", "true", "false")


def _settings():
    return stores.read_json(paths.settings_path(), None)


def _write(settings):
    stores.atomic_write_json(paths.settings_path(), settings, backup=True)


def silence_skills(names, mode="user-invocable-only"):
    s = _settings()
    if s is None:
        return {"ok": False, "error": "settings-not-found"}
    so = s.setdefault("skillOverrides", {})
    for n in names:
        so[n] = mode
    _write(s)
    return {"ok": True, "count": len(names)}


def unsilence_skills(names):
    s = _settings()
    if s is None:
        return {"ok": False, "error": "settings-not-found"}
    so = s.get("skillOverrides", {})
    for n in names:
        so.pop(n, None)
    _write(s)
    return {"ok": True}


def set_tool_search(value):
    if value not in VALID_TOOL_SEARCH:
        return {"ok": False, "error": f"invalid-value: {value}"}
    s = _settings()
    if s is None:
        return {"ok": False, "error": "settings-not-found"}
    s.setdefault("env", {})["ENABLE_TOOL_SEARCH"] = value
    _write(s)
    return {"ok": True}


def _archive_dir():
    p = paths.state_dir() / "agents-archived"
    p.mkdir(exist_ok=True)
    return p


def archive_agent(filename):
    src = paths.claude_home() / "agents" / filename
    if not src.is_file():
        return {"ok": False, "error": f"not-found: {filename}"}
    shutil.move(str(src), str(_archive_dir() / filename))
    return {"ok": True}


def restore_agent(filename):
    src = _archive_dir() / filename
    if not src.is_file():
        return {"ok": False, "error": f"not-archived: {filename}"}
    dst = paths.claude_home() / "agents"
    dst.mkdir(exist_ok=True)
    shutil.move(str(src), str(dst / filename))
    return {"ok": True}


def _stash_dir():
    p = paths.state_dir() / "mcp-stash"
    p.mkdir(exist_ok=True)
    return p


def stash_mcp(name, runner=subprocess.run):
    cj = stores.read_json(paths.claude_json_path(), {})
    cfg = (cj.get("mcpServers") or {}).get(name)
    if cfg is None:
        return {"ok": False, "error": f"unknown-server: {name}"}
    stores.atomic_write_json(_stash_dir() / f"{name}.json", cfg)
    r = runner(["claude", "mcp", "remove", name, "-s", "user"],
               capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False,
                "error": f"claude-mcp-remove-failed: {getattr(r, 'stderr', '')}"}
    return {"ok": True}


def restore_mcp(name, runner=subprocess.run):
    f = _stash_dir() / f"{name}.json"
    cfg = stores.read_json(f, None)
    if cfg is None:
        return {"ok": False, "error": f"not-stashed: {name}"}
    r = runner(["claude", "mcp", "add-json", name, json.dumps(cfg), "-s", "user"],
               capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False,
                "error": f"claude-mcp-add-failed: {getattr(r, 'stderr', '')}"}
    f.unlink()
    return {"ok": True}


def migrate_skill(project_dir, name):
    src = Path(project_dir) / ".claude" / "skills" / name
    dst = paths.skills_dir() / name
    if not src.is_dir():
        return {"ok": False, "error": f"not-found: {src}"}
    if dst.exists():
        return {"ok": False, "error": f"name-collision: {name}"}
    paths.skills_dir().mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"ok": True, "moved_to": str(dst)}
