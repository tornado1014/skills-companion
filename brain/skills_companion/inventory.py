import json
from pathlib import Path

from . import paths, stores
from .scanner import parse_frontmatter


def scan_agents():
    out = []
    d = paths.claude_home() / "agents"
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            name, desc = parse_frontmatter(f)
            out.append({"name": name or f.stem, "desc": desc or "",
                        "path": str(f), "source": "user"})
    return out


def scan_mcp():
    cj = stores.read_json(paths.claude_json_path(), {})
    return [{"name": name, "scope": "user", "config": cfg}
            for name, cfg in (cj.get("mcpServers") or {}).items()]


def discover_projects(max_transcripts=200):
    seen = []
    files = sorted(paths.projects_dir().glob("*/*.jsonl"),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:max_transcripts]
    for f in files:
        cwd = None
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh):
                    if i > 20:
                        break
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if d.get("cwd"):
                        cwd = d["cwd"]
                        break
        except OSError:
            continue
        if not cwd or cwd in seen:
            continue
        seen.append(cwd)
    out = []
    for cwd in seen:
        p = Path(cwd)
        skdir = p / ".claude" / "skills"
        skills = (sorted(x.parent.name for x in skdir.glob("*/SKILL.md"))
                  if skdir.is_dir() else [])
        has_settings = ((p / ".claude" / "settings.json").exists()
                        or (p / ".claude" / "settings.local.json").exists())
        has_mcp = (p / ".mcp.json").exists()
        if skills or has_settings or has_mcp:
            out.append({"cwd": cwd, "skills": skills, "has_mcp_json": has_mcp})
    return out


def tool_search_status():
    s = stores.read_json(paths.settings_path(), {})
    val = (s.get("env") or {}).get("ENABLE_TOOL_SEARCH")
    return {"value": val, "deferred": val in (None, "auto", "true")}
