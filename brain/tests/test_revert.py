import json
import time

from skills_companion import activation, paths, revert, stores

UA = "understand-anything@understand-anything"
KL = "korean-law@korean-law-marketplace"


def _enabled(home, key):
    s = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    return s["enabledPlugins"][key]


def _signal(sid):
    p = paths.signals_dir() / f"{sid}.json"
    p.write_text(json.dumps({"reason": "other", "ts": time.time()}), encoding="utf-8")
    return p


def test_default_policy_ask(claude_home):
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    out = revert.on_session_end("S1")
    assert out["action"] == "ask" and out["ask"] == [UA]
    assert sig.exists()                       # kept until decisions applied
    assert _enabled(claude_home, UA) is True  # nothing reverted yet


def test_auto_revert_policy(claude_home):
    cfg = stores.load_config()
    cfg["per_plugin"][UA] = "auto-revert"
    stores.save_config(cfg)
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    out = revert.on_session_end("S1")
    assert out["reverted"] == [UA] and out["action"] == "done"
    assert _enabled(claude_home, UA) is False
    assert "S1" not in stores.load_ledger()
    assert not sig.exists()


def test_keep_policy(claude_home):
    cfg = stores.load_config()
    cfg["per_plugin"][UA] = "keep"
    stores.save_config(cfg)
    activation.activate(UA, session_id="S1")
    _signal("S1")
    out = revert.on_session_end("S1")
    assert out["kept"] == [UA]
    assert _enabled(claude_home, UA) is True
    assert "S1" not in stores.load_ledger()


def test_concurrency_guard(claude_home, write_transcript):
    activation.activate(UA, session_id="S1")
    stores.ledger_add("S2", UA)                       # S2 also holds it
    write_transcript("S2", ["still working"], mtime=time.time())  # S2 live
    _signal("S1")
    out = revert.on_session_end("S1")
    assert out["kept"] == [UA] and out["ask"] == []
    assert _enabled(claude_home, UA) is True          # guarded
    assert "S1" not in stores.load_ledger()
    assert "S2" in stores.load_ledger()


def test_apply_decisions_concurrency_guard(claude_home, write_transcript):
    activation.activate(UA, session_id="S1")
    activation.activate(UA, session_id="S2")          # already-enabled, ledger-tracked
    write_transcript("S2", ["still working"], mtime=time.time())  # S2 live
    sig = _signal("S1")
    out = revert.apply_decisions(
        "S1", [{"plugin": UA, "action": "revert", "remember": False}])
    assert out["kept"] == [UA] and out["reverted"] == []
    assert _enabled(claude_home, UA) is True          # guarded, not reverted
    assert "S1" not in stores.load_ledger()
    assert UA in {e["plugin"] for e in stores.load_ledger()["S2"]}
    assert not sig.exists()


def test_apply_decisions_with_remember(claude_home):
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    revert.on_session_end("S1")                       # -> ask
    out = revert.apply_decisions(
        "S1", [{"plugin": UA, "action": "revert", "remember": True}])
    assert out["reverted"] == [UA]
    assert _enabled(claude_home, UA) is False
    assert stores.load_config()["per_plugin"][UA] == "auto-revert"
    assert not sig.exists()


def test_sweep_finds_leaks(claude_home, write_transcript):
    activation.activate(UA, session_id="GONE")
    write_transcript("GONE", ["x"], mtime=time.time() - 9999)
    assert revert.sweep()["leaks"] == ["GONE"]
    _signal("GONE")                                   # signal pending -> not a leak
    assert revert.sweep()["leaks"] == []


def test_no_entries_cleans_signal(claude_home):
    sig = _signal("EMPTY")
    out = revert.on_session_end("EMPTY")
    assert out["action"] == "none"
    assert not sig.exists()
