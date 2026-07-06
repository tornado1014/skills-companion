from . import paths, stores

RELOAD = "/reload-plugins"


def _load_settings():
    return stores.read_json(paths.settings_path(), None)


def _app_enabled(plugin_key):
    ledger = stores.load_ledger()
    return any(e["plugin"] == plugin_key for es in ledger.values() for e in es)


def activate(plugin_key, session_id=None, cwd=""):
    settings = _load_settings()
    if settings is None:
        return {"ok": False, "error": "settings-not-found"}
    ep = settings.get("enabledPlugins", {})
    if plugin_key not in ep:
        return {"ok": False, "error": f"unknown-plugin: {plugin_key}"}
    if ep[plugin_key]:
        if session_id and _app_enabled(plugin_key):
            stores.ledger_add(session_id, plugin_key, cwd)
            stores.history_add(cwd, plugin_key)
        return {"ok": True, "already_enabled": True, "reload_command": RELOAD}
    ep[plugin_key] = True
    stores.atomic_write_json(paths.settings_path(), settings, backup=True)
    if session_id:
        stores.ledger_add(session_id, plugin_key, cwd)
    stores.history_add(cwd, plugin_key)
    return {"ok": True, "already_enabled": False, "reload_command": RELOAD}


def deactivate(plugin_key):
    settings = _load_settings()
    if settings is None:
        return {"ok": False, "error": "settings-not-found"}
    ep = settings.get("enabledPlugins", {})
    if plugin_key not in ep:
        return {"ok": False, "error": f"unknown-plugin: {plugin_key}"}
    if ep[plugin_key]:
        ep[plugin_key] = False
        stores.atomic_write_json(paths.settings_path(), settings, backup=True)
    return {"ok": True}
