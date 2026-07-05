from . import paths, stores


def _cmd(script_path):
    return f"bash {script_path}"


def add_session_end_hook(settings, script_path):
    hooks = settings.setdefault("hooks", {})
    entries = hooks.setdefault("SessionEnd", [])
    cmd = _cmd(script_path)
    exists = any(cmd == h.get("command") for e in entries
                 for h in e.get("hooks", []))
    if not exists:
        entries.append({"hooks": [{"type": "command", "command": cmd}]})
    return settings


def remove_session_end_hook(settings, script_path):
    entries = settings.get("hooks", {}).get("SessionEnd")
    if entries is not None:
        cmd = _cmd(script_path)
        settings["hooks"]["SessionEnd"] = [
            e for e in entries
            if not any(cmd == h.get("command") for h in e.get("hooks", []))]
    return settings


def remove_cheatsheet_hook(settings):
    entries = settings.get("hooks", {}).get("SessionStart")
    if entries is not None:
        settings["hooks"]["SessionStart"] = [
            e for e in entries
            if not any("skills-cheatsheet/open.sh" in h.get("command", "")
                       for h in e.get("hooks", []))]
    return settings


def _apply(mutate):
    settings = stores.read_json(paths.settings_path(), None)
    if settings is None:
        return {"ok": False, "error": "settings-not-found"}
    mutate(settings)
    stores.atomic_write_json(paths.settings_path(), settings, backup=True)
    return {"ok": True}


def install_hooks(script_path):
    return _apply(lambda s: remove_cheatsheet_hook(
        add_session_end_hook(s, script_path)))


def uninstall_hooks(script_path):
    return _apply(lambda s: remove_session_end_hook(s, script_path))
