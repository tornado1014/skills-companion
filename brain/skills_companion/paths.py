import os
from pathlib import Path


def claude_home() -> Path:
    return Path(os.environ.get("SKILLS_COMPANION_CLAUDE_HOME", "~/.claude")).expanduser()


def settings_path() -> Path:
    return claude_home() / "settings.json"


def skills_dir() -> Path:
    return claude_home() / "skills"


def plugin_cache_dir() -> Path:
    return claude_home() / "plugins" / "cache"


def projects_dir() -> Path:
    return claude_home() / "projects"


def state_dir() -> Path:
    p = claude_home() / "skills-companion" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path() -> Path:
    return state_dir() / "ledger.json"


def config_path() -> Path:
    return state_dir() / "config.json"


def signals_dir() -> Path:
    p = state_dir() / "session-ended"
    p.mkdir(parents=True, exist_ok=True)
    return p


def claude_json_path() -> Path:
    return claude_home().parent / ".claude.json"
