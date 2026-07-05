from skills_companion import lightweight, paths, stores


def test_silence_and_unsilence(claude_home):
    r = lightweight.silence_skills(["domain-modeling"])
    assert r["ok"] and r["count"] == 1
    s = stores.read_json(paths.settings_path(), {})
    assert s["skillOverrides"]["domain-modeling"] == "user-invocable-only"
    lightweight.unsilence_skills(["domain-modeling", "patent-en-ko-kipo"])
    s = stores.read_json(paths.settings_path(), {})
    assert "domain-modeling" not in s["skillOverrides"]
    assert "patent-en-ko-kipo" not in s["skillOverrides"]
    assert list(claude_home.glob("settings.json.bak.*"))


def test_set_tool_search_validates(claude_home):
    assert lightweight.set_tool_search("auto")["ok"]
    s = stores.read_json(paths.settings_path(), {})
    assert s["env"]["ENABLE_TOOL_SEARCH"] == "auto"
    assert lightweight.set_tool_search("banana")["ok"] is False


def test_archive_and_restore_agent(claude_home):
    assert lightweight.archive_agent("oa-analyzer.md")["ok"]
    assert not (claude_home / "agents" / "oa-analyzer.md").exists()
    assert (paths.state_dir() / "agents-archived" / "oa-analyzer.md").exists()
    assert lightweight.restore_agent("oa-analyzer.md")["ok"]
    assert (claude_home / "agents" / "oa-analyzer.md").exists()
    assert lightweight.archive_agent("nope.md")["ok"] is False


def test_stash_and_restore_mcp_via_cli(claude_home):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class R:
            returncode = 0
            stderr = ""
        return R()

    r = lightweight.stash_mcp("exa", runner=fake_run)
    assert r["ok"]
    assert calls[0][:4] == ["claude", "mcp", "remove", "exa"]
    stash = paths.state_dir() / "mcp-stash" / "exa.json"
    assert stash.exists()
    r2 = lightweight.restore_mcp("exa", runner=fake_run)
    assert r2["ok"] and not stash.exists()
    assert calls[1][:4] == ["claude", "mcp", "add-json", "exa"]
    assert lightweight.stash_mcp("ghost", runner=fake_run)["ok"] is False


def test_migrate_skill_and_collision(claude_home, tmp_path):
    proj = tmp_path / "p2"
    src = proj / ".claude" / "skills" / "movee"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(
        "---\nname: movee\ndescription: d\n---\n", encoding="utf-8")
    r = lightweight.migrate_skill(str(proj), "movee")
    assert r["ok"]
    assert (claude_home / "skills" / "movee" / "SKILL.md").exists()
    assert not src.exists()
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("x", encoding="utf-8")
    r2 = lightweight.migrate_skill(str(proj), "movee")
    assert r2["ok"] is False and "collision" in r2["error"]
