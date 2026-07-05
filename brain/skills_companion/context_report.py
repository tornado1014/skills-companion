from pathlib import Path

from . import inventory, paths, scanner, stores, transcripts


def _tok(text):
    return len(text) // 4 if text else 0


def report():
    items = scanner.scan()["items"]
    skills_t = sum(_tok(i["desc"]) for i in items
                   if i["source"] == "personal" and i["state"] == "loaded")
    plugin_t = sum(_tok(i["desc"]) for i in items
                   if i["source"] == "plugin" and i["state"] == "enabled")
    agents = inventory.scan_agents()
    agents_t = sum(_tok(a["desc"]) + 40 for a in agents)
    mcp = inventory.scan_mcp()
    ts = inventory.tool_search_status()
    per_server = 250 if ts["deferred"] else 1500
    cm = paths.claude_home() / "CLAUDE.md"
    cm_t = _tok(cm.read_text(encoding="utf-8", errors="ignore")) if cm.is_file() else 0
    mem_t = 0
    sess = transcripts.newest_session()
    if sess:
        mem = Path(sess["path"]).parent / "memory" / "MEMORY.md"
        if mem.is_file():
            text = mem.read_text(encoding="utf-8", errors="ignore")
            mem_t = _tok("\n".join(text.splitlines()[:200])[:25_000])
    s = stores.read_json(paths.settings_path(), {})
    hooks = [h.get("command", "")
             for e in s.get("hooks", {}).get("SessionStart", [])
             for h in e.get("hooks", [])]
    rows = [
        {"key": "personal_skills", "label": "개인 스킬 설명(로딩중)",
         "tokens": skills_t, "controllable": True,
         "advice": "마법사에서 '수동(/)'으로 전환"},
        {"key": "plugins", "label": "플러그인 스킬/명령 설명",
         "tokens": plugin_t, "controllable": True,
         "advice": "안 쓰는 플러그인 비활성화"},
        {"key": "agents", "label": f"사용자 에이전트 {len(agents)}개",
         "tokens": agents_t, "controllable": True,
         "advice": "보관(archive) 가능 — 복원 지원"},
        {"key": "mcp",
         "label": f"MCP 서버 {len(mcp)}개 (지연로딩 {'ON' if ts['deferred'] else 'OFF'})",
         "tokens": len(mcp) * per_server, "controllable": True,
         "advice": "지연로딩 켜기 + 미사용 서버 보관"},
        {"key": "claude_md", "label": "~/.claude/CLAUDE.md", "tokens": cm_t,
         "controllable": False,
         "advice": "직접 다듬기 · .claude/rules/ 분할 (앱이 수정하지 않음)"},
        {"key": "memory_md", "label": "자동 메모리 MEMORY.md(로딩분)",
         "tokens": mem_t, "controllable": False,
         "advice": "Claude가 관리 — 앱이 수정하지 않음"},
        {"key": "hooks", "label": f"SessionStart 훅 {len(hooks)}개",
         "tokens": None, "controllable": False,
         "advice": "stdout 출력 훅은 컨텍스트 주입 — 점검 권장", "detail": hooks},
    ]
    return {"rows": rows,
            "total_estimate": sum(r["tokens"] or 0 for r in rows),
            "tool_search": ts}
