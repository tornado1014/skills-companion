from skills_companion import paths


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    assert paths.claude_home() == tmp_path
    assert paths.settings_path() == tmp_path / "settings.json"
    assert paths.skills_dir() == tmp_path / "skills"
    assert paths.plugin_cache_dir() == tmp_path / "plugins" / "cache"
    assert paths.projects_dir() == tmp_path / "projects"


def test_state_dirs_created(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    assert paths.state_dir().is_dir()
    assert paths.signals_dir().is_dir()
    assert paths.ledger_path().name == "ledger.json"
    assert paths.config_path().name == "config.json"


def test_default_is_home_claude(monkeypatch):
    monkeypatch.delenv("SKILLS_COMPANION_CLAUDE_HOME", raising=False)
    assert str(paths.claude_home()).endswith("/.claude")
