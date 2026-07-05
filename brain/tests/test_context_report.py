from skills_companion import context_report


def test_report_has_all_rows_and_total(claude_home):
    rep = context_report.report()
    keys = {r["key"] for r in rep["rows"]}
    assert {"personal_skills", "plugins", "agents", "mcp",
            "claude_md", "memory_md", "hooks"} <= keys
    assert rep["total_estimate"] > 0
    assert rep["tool_search"]["deferred"] is True


def test_report_counts_only_loaded_skills(claude_home):
    rep = context_report.report()
    row = next(r for r in rep["rows"] if r["key"] == "personal_skills")
    assert row["tokens"] > 0            # domain-modeling is loaded
    assert row["controllable"] is True
    mcp = next(r for r in rep["rows"] if r["key"] == "mcp")
    assert mcp["tokens"] == 250         # 1 server × deferred heuristic
