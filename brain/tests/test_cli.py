import json
import time

from skills_companion import cli, paths

UA = "understand-anything@understand-anything"


def _run(capsys, argv):
    assert cli.main(argv) == 0
    return json.loads(capsys.readouterr().out)


def test_scan(claude_home, capsys):
    out = _run(capsys, ["scan"])
    assert any(i["invoke"] == "/domain-modeling" for i in out["items"])


def test_recommend_uses_newest_session(claude_home, write_transcript, capsys):
    write_transcript("S9", ["analyze the codebase architecture knowledge graph"])
    out = _run(capsys, ["recommend", "--top", "3"])
    assert out["session"] == "S9"
    assert out["recommendations"][0]["item"]["invoke"] == \
        "/understand-anything:understand"


def test_activate_session_end_roundtrip(claude_home, write_transcript, capsys):
    write_transcript("S9", ["work"], mtime=time.time() - 99999)  # not live later
    out = _run(capsys, ["activate", "--plugin", UA, "--session", "S9"])
    assert out["ok"] is True
    (paths.signals_dir() / "S9.json").write_text(
        json.dumps({"reason": "other", "ts": time.time()}), encoding="utf-8")
    pend = _run(capsys, ["pending"])
    assert pend["sessions"][0]["session_id"] == "S9"
    end = _run(capsys, ["session-end", "--session", "S9"])
    assert end["action"] == "ask" and end["ask"] == [UA]
    dec = json.dumps([{"plugin": UA, "action": "keep", "remember": True}])
    ap = _run(capsys, ["apply-decisions", "--session", "S9", "--decisions", dec])
    assert ap["kept"] == [UA]
    cfg = _run(capsys, ["config-get"])
    assert cfg["per_plugin"][UA] == "keep"


def test_config_set_merges(claude_home, capsys):
    out = _run(capsys, ["config-set", "--json", '{"default_policy": "keep"}'])
    assert out["default_policy"] == "keep"
    assert out["poll_seconds"] == 20


def test_cli_inventory_and_report(claude_home, capsys):
    inv = _run(capsys, ["inventory"])
    assert inv["agents"][0]["name"] == "oa-analyzer"
    assert inv["mcp"][0]["name"] == "exa"
    assert inv["tool_search"]["deferred"] is True
    rep = _run(capsys, ["context-report"])
    assert rep["total_estimate"] > 0


def test_cli_lightweight_bundle(claude_home, capsys):
    out = _run(capsys, ["lightweight", "--json",
                        '{"silence": ["domain-modeling"], "tool_search": "auto"}'])
    assert out["ok"] is True
    from skills_companion import paths, stores
    s = stores.read_json(paths.settings_path(), {})
    assert s["skillOverrides"]["domain-modeling"] == "user-invocable-only"
    assert s["env"]["ENABLE_TOOL_SEARCH"] == "auto"


def test_cli_wizard_flag_default(claude_home, capsys):
    cfg = _run(capsys, ["config-get"])
    assert cfg["wizard_completed"] is False


def test_cli_activate_records_history_with_cwd(claude_home, write_transcript, capsys):
    from skills_companion import stores
    write_transcript("S9", ["work"], cwd="/tmp/work")
    _run(capsys, ["activate", "--plugin", UA, "--session", "S9"])
    assert stores.history_for("/tmp/work") == {UA: 1}


def test_recommend_blends_history_for_cwd(claude_home, write_transcript, capsys):
    write_transcript("SH", ["시작"], cwd="/tmp/work")   # umc=1 → 프로젝트/이력 가중 우세
    _run(capsys, ["activate", "--plugin", UA, "--session", "SH"])
    out = _run(capsys, ["recommend", "--top", "3"])
    top = out["recommendations"][0]
    assert top["item"]["invoke"] == "/understand-anything:understand"
    assert any("1회 사용" in r for r in top["reasons"])


def test_cli_disable_plugin(claude_home, capsys):
    out = _run(capsys, ["disable-plugin", "--plugin",
                        "korean-law@korean-law-marketplace"])
    assert out["ok"] is True
