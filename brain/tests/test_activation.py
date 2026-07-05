import json

from skills_companion import activation, paths, stores

UA = "understand-anything@understand-anything"
KL = "korean-law@korean-law-marketplace"


def _settings(home):
    return json.loads((home / "settings.json").read_text(encoding="utf-8"))


def test_activate_flips_and_ledgers(claude_home):
    r = activation.activate(UA, session_id="S1", cwd="/w")
    assert r["ok"] and r["already_enabled"] is False
    assert r["reload_command"] == "/reload-plugins"
    assert _settings(claude_home)["enabledPlugins"][UA] is True
    assert list(claude_home.glob("settings.json.bak.*"))          # backup made
    assert [e["plugin"] for e in stores.load_ledger()["S1"]] == [UA]
    # unrelated keys untouched
    assert _settings(claude_home)["skillOverrides"] == {
        "patent-en-ko-kipo": "user-invocable-only"}


def test_activate_already_enabled_no_ledger(claude_home):
    r = activation.activate(KL, session_id="S1")
    assert r["ok"] and r["already_enabled"] is True
    assert "S1" not in stores.load_ledger()


def test_activate_already_enabled_by_app_is_ledger_tracked(claude_home):
    activation.activate(UA, session_id="S1", cwd="/w")     # app flips it
    r = activation.activate(UA, session_id="S2")           # already enabled by app
    assert r["ok"] and r["already_enabled"] is True
    assert [e["plugin"] for e in stores.load_ledger()["S2"]] == [UA]


def test_activate_unknown_plugin(claude_home):
    r = activation.activate("nope@nowhere", session_id="S1")
    assert r["ok"] is False and "unknown" in r["error"]


def test_deactivate(claude_home):
    activation.activate(UA, session_id="S1")
    r = activation.deactivate(UA)
    assert r["ok"]
    assert _settings(claude_home)["enabledPlugins"][UA] is False
    r2 = activation.deactivate(UA)                                # idempotent
    assert r2["ok"]
