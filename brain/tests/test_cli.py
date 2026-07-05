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
