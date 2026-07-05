import time

from . import activation, paths, stores, transcripts


def _signal_path(session_id):
    return paths.signals_dir() / f"{session_id}.json"


def on_session_end(session_id, reason="other"):
    ledger = stores.load_ledger()
    entries = ledger.get(session_id, [])
    if not entries:
        _signal_path(session_id).unlink(missing_ok=True)
        return {"action": "none", "reverted": [], "kept": [], "ask": []}
    cfg = stores.load_config()
    live = transcripts.live_sessions(exclude=session_id)
    held = set()
    for sid, es in ledger.items():
        if sid in live:
            held |= {e["plugin"] for e in es}
    out = {"action": "done", "reverted": [], "kept": [], "ask": []}
    for e in list(entries):
        p = e["plugin"]
        if p in held:
            stores.ledger_remove(session_id, p)
            out["kept"].append(p)
            continue
        pol = stores.policy_for(p, cfg)
        if pol == "auto-revert":
            activation.deactivate(p)
            stores.ledger_remove(session_id, p)
            out["reverted"].append(p)
        elif pol == "keep":
            stores.ledger_remove(session_id, p)
            out["kept"].append(p)
        else:
            out["ask"].append(p)
    if out["ask"]:
        out["action"] = "ask"
    else:
        _signal_path(session_id).unlink(missing_ok=True)
    return out


def apply_decisions(session_id, decisions):
    cfg = stores.load_config()
    out = {"reverted": [], "kept": []}
    for d in decisions:
        p = d["plugin"]
        if d.get("action") == "revert":
            activation.deactivate(p)
            out["reverted"].append(p)
        else:
            out["kept"].append(p)
        stores.ledger_remove(session_id, p)
        if d.get("remember"):
            cfg["per_plugin"][p] = (
                "auto-revert" if d.get("action") == "revert" else "keep")
    stores.save_config(cfg)
    if session_id not in stores.load_ledger():
        _signal_path(session_id).unlink(missing_ok=True)
    return out


def sweep(idle_threshold=1800):
    ledger = stores.load_ledger()
    now = time.time()
    leaks = []
    for sid in ledger:
        if _signal_path(sid).exists():
            continue
        tf = next(iter(paths.projects_dir().glob(f"*/{sid}.jsonl")), None)
        try:
            idle = tf is None or now - tf.stat().st_mtime > idle_threshold
        except OSError:
            idle = True
        if idle:
            leaks.append(sid)
    return {"leaks": leaks}
