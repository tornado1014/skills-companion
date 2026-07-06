import json

from skills_companion import paths, stores


def test_read_json_default_on_missing(tmp_path):
    assert stores.read_json(tmp_path / "nope.json", {"a": 1}) == {"a": 1}


def test_atomic_write_creates_backup(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"old": true}', encoding="utf-8")
    stores.atomic_write_json(p, {"new": True}, backup=True)
    assert json.loads(p.read_text(encoding="utf-8")) == {"new": True}
    baks = list(tmp_path.glob("s.json.bak.*"))
    assert len(baks) == 1
    assert json.loads(baks[0].read_text(encoding="utf-8")) == {"old": True}


def test_config_defaults_and_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    cfg = stores.load_config()
    assert cfg["default_policy"] == "ask"
    assert cfg["poll_seconds"] == 20
    assert cfg["notifications_enabled"] is False
    cfg["per_plugin"]["x@m"] = "keep"
    stores.save_config(cfg)
    cfg2 = stores.load_config()
    assert stores.policy_for("x@m", cfg2) == "keep"
    assert stores.policy_for("other@m", cfg2) == "ask"


def test_ledger_add_dedup_and_remove(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    stores.ledger_add("S1", "ua@ua", cwd="/w")
    stores.ledger_add("S1", "ua@ua")           # dedup
    stores.ledger_add("S1", "kl@kl")
    led = stores.load_ledger()
    assert [e["plugin"] for e in led["S1"]] == ["ua@ua", "kl@kl"]
    stores.ledger_remove("S1", "ua@ua")
    assert [e["plugin"] for e in stores.load_ledger()["S1"]] == ["kl@kl"]
    stores.ledger_remove("S1", "kl@kl")
    assert "S1" not in stores.load_ledger()    # empty list pruned


def test_history_add_and_for(claude_home):
    UA = "understand-anything@understand-anything"
    stores.history_add("/w", UA)
    stores.history_add("/w", UA)
    stores.history_add("/other", UA)
    assert stores.history_for("/w") == {UA: 2}
    assert stores.history_for("/none") == {}
    raw = stores.read_json(paths.activation_history_path(), {})
    assert raw["/w"][UA]["count"] == 2 and raw["/w"][UA]["last_ts"] > 0


def test_history_add_empty_cwd_is_noop(claude_home):
    stores.history_add("", "x@y")
    assert stores.read_json(paths.activation_history_path(), {}) == {}
