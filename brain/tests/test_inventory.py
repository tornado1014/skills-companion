from skills_companion import inventory


def test_scan_agents(claude_home):
    ags = inventory.scan_agents()
    assert ags[0]["name"] == "oa-analyzer"
    assert "특허" in ags[0]["desc"]


def test_scan_mcp_user_scope(claude_home):
    mcp = inventory.scan_mcp()
    assert mcp[0]["name"] == "exa" and mcp[0]["scope"] == "user"
    assert mcp[0]["config"]["command"] == "npx"


def test_tool_search_status_default_deferred(claude_home):
    st = inventory.tool_search_status()
    assert st["value"] is None and st["deferred"] is True


def test_discover_projects_from_transcript_cwd(claude_home, write_transcript,
                                               tmp_path):
    proj = tmp_path / "myproj"
    sk = proj / ".claude" / "skills" / "localskill"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text(
        "---\nname: localskill\ndescription: a local skill\n---\n", encoding="utf-8")
    write_transcript("P1", ["work here"], cwd=str(proj))
    projects = inventory.discover_projects()
    mine = [p for p in projects if p["cwd"] == str(proj)]
    assert mine and mine[0]["skills"] == ["localskill"]
    assert mine[0]["has_mcp_json"] is False
