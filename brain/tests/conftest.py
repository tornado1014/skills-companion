import json
import os

import pytest


def _skill(home, folder, name, desc):
    d = home / "skills" / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8"
    )


@pytest.fixture
def claude_home(tmp_path, monkeypatch):
    home = tmp_path / ".claude"
    _skill(home, "patent-en-ko-kipo", "patent-en-ko-kipo",
           "영문 특허 docx를 KIPO 명세서로 번역. Triggers: 특허번역, KIPO 명세서")
    _skill(home, "domain-modeling", "domain-modeling",
           "Build and sharpen the project domain model glossary")
    ua = home / "plugins" / "cache" / "ua-mkt" / "understand-anything" / "2.8.2"
    (ua / "skills" / "understand").mkdir(parents=True)
    (ua / "skills" / "understand" / "SKILL.md").write_text(
        "---\nname: understand\ndescription: Analyze a codebase to produce an "
        "interactive knowledge graph of architecture and components\n---\nbody\n",
        encoding="utf-8")
    kl = home / "plugins" / "cache" / "kl-mkt" / "korean-law" / "4.4.1"
    (kl / "commands").mkdir(parents=True)
    (kl / "commands" / "research.md").write_text(
        "---\nname: research\ndescription: 법령 판례 리서치 legal research\n---\nbody\n",
        encoding="utf-8")
    settings = {
        "enabledPlugins": {
            "understand-anything@understand-anything": False,
            "korean-law@korean-law-marketplace": True,
        },
        "skillOverrides": {"patent-en-ko-kipo": "user-invocable-only"},
    }
    (home / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    (home / "projects" / "-tmp-work").mkdir(parents=True)
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(home))
    return home


@pytest.fixture
def write_transcript(claude_home):
    def _write(session_id, texts, mtime=None, tools=None):
        lines = []
        for t in texts:
            lines.append(json.dumps(
                {"type": "user", "sessionId": session_id, "cwd": "/tmp/work",
                 "message": {"role": "user", "content": t}}, ensure_ascii=False))
        for name in tools or []:
            lines.append(json.dumps(
                {"type": "assistant",
                 "message": {"role": "assistant",
                             "content": [{"type": "tool_use", "name": name},
                                         {"type": "text", "text": "ok"}]}},
                ensure_ascii=False))
        f = claude_home / "projects" / "-tmp-work" / f"{session_id}.jsonl"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if mtime is not None:
            os.utime(f, (mtime, mtime))
        return f
    return _write
