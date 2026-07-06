import argparse
import json
import sys

from . import (activation, context_report, inventory, lightweight, llm_refine,
               paths, recommender, revert, scanner, stores, transcripts)


def _cmd_recommend(args):
    sess = transcripts.newest_session()
    signals = (transcripts.extract_signals(sess["path"]) if sess
               else {"texts": [], "tools": [], "cwd": "",
                     "user_texts": [], "user_msg_count": 0})
    items = scanner.scan()["items"]
    cwd = signals.get("cwd", "")
    local = recommender.recommend(
        items, signals, top_k=max(args.top, 12),
        history=stores.history_for(cwd),
        project_tokens=recommender.project_tokens(cwd))
    if sess:
        recs = llm_refine.refine(
            sess["session_id"], signals.get("user_texts", []),
            signals.get("user_msg_count", 0), local, top_k=args.top)
    else:
        recs = local[:args.top]
    return {"session": sess["session_id"] if sess else None,
            "session_title": transcripts.session_title(sess["path"]) if sess
            else None,
            "recommendations": recs}


def _cmd_pending(_args):
    out = []
    for f in sorted(paths.signals_dir().glob("*.json")):
        d = stores.read_json(f, {})
        out.append({"session_id": f.stem, "reason": d.get("reason", "other")})
    return {"sessions": out}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="skills-companion-brain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    p = sub.add_parser("recommend")
    p.add_argument("--top", type=int, default=5)
    p = sub.add_parser("activate")
    p.add_argument("--plugin", required=True)
    p.add_argument("--session")
    p = sub.add_parser("session-end")
    p.add_argument("--session", required=True)
    p.add_argument("--reason", default="other")
    p = sub.add_parser("apply-decisions")
    p.add_argument("--session", required=True)
    p.add_argument("--decisions", required=True)
    sub.add_parser("sweep")
    sub.add_parser("pending")
    sub.add_parser("config-get")
    p = sub.add_parser("config-set")
    p.add_argument("--json", required=True)
    sub.add_parser("inventory")
    sub.add_parser("context-report")
    p = sub.add_parser("lightweight")
    p.add_argument("--json", required=True)
    p = sub.add_parser("archive-agent")
    p.add_argument("--file", required=True)
    p = sub.add_parser("restore-agent")
    p.add_argument("--file", required=True)
    p = sub.add_parser("stash-mcp")
    p.add_argument("--name", required=True)
    p = sub.add_parser("restore-mcp")
    p.add_argument("--name", required=True)
    p = sub.add_parser("migrate-skill")
    p.add_argument("--project", required=True)
    p.add_argument("--name", required=True)
    p = sub.add_parser("disable-plugin")
    p.add_argument("--plugin", required=True)
    p = sub.add_parser("install-hooks")
    p.add_argument("--script", required=True)
    p = sub.add_parser("uninstall-hooks")
    p.add_argument("--script", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        out = scanner.scan()
    elif args.cmd == "recommend":
        out = _cmd_recommend(args)
    elif args.cmd == "activate":
        sid = args.session
        if not sid:
            sess = transcripts.newest_session()
            sid = sess["session_id"] if sess else None
        cwd = ""
        if sid:
            tp = transcripts.session_path(sid)
            if tp:
                cwd = transcripts.extract_signals(tp).get("cwd", "")
        out = activation.activate(args.plugin, session_id=sid, cwd=cwd)
        out["session"] = sid
    elif args.cmd == "session-end":
        out = revert.on_session_end(args.session, reason=args.reason)
    elif args.cmd == "apply-decisions":
        out = revert.apply_decisions(args.session, json.loads(args.decisions))
    elif args.cmd == "sweep":
        out = revert.sweep()
    elif args.cmd == "pending":
        out = _cmd_pending(args)
    elif args.cmd == "config-get":
        out = stores.load_config()
    elif args.cmd == "config-set":
        cfg = stores.load_config()
        cfg.update(json.loads(getattr(args, "json")))
        stores.save_config(cfg)
        out = cfg
    elif args.cmd == "inventory":
        out = {"agents": inventory.scan_agents(), "mcp": inventory.scan_mcp(),
               "projects": inventory.discover_projects(),
               "tool_search": inventory.tool_search_status()}
    elif args.cmd == "context-report":
        out = context_report.report()
    elif args.cmd == "lightweight":
        spec = json.loads(getattr(args, "json"))
        results = {}
        if spec.get("silence"):
            results["silence"] = lightweight.silence_skills(spec["silence"])
        if spec.get("unsilence"):
            results["unsilence"] = lightweight.unsilence_skills(spec["unsilence"])
        if spec.get("tool_search"):
            results["tool_search"] = lightweight.set_tool_search(spec["tool_search"])
        out = {"ok": all(r.get("ok") for r in results.values()) if results else True,
               "results": results}
    elif args.cmd == "archive-agent":
        out = lightweight.archive_agent(args.file)
    elif args.cmd == "restore-agent":
        out = lightweight.restore_agent(args.file)
    elif args.cmd == "stash-mcp":
        out = lightweight.stash_mcp(args.name)
    elif args.cmd == "restore-mcp":
        out = lightweight.restore_mcp(args.name)
    elif args.cmd == "migrate-skill":
        out = lightweight.migrate_skill(args.project, args.name)
    elif args.cmd == "disable-plugin":
        out = activation.deactivate(args.plugin)
    elif args.cmd == "install-hooks":
        from . import installer
        out = installer.install_hooks(args.script)
    elif args.cmd == "uninstall-hooks":
        from . import installer
        out = installer.uninstall_hooks(args.script)
    # Emit UTF-8 explicitly. On Windows, stdout defaults to the locale codepage
    # (e.g. cp949), which crashes on non-ASCII (— / Korean) and would corrupt
    # the bytes the Tauri shell parses as UTF-8. Writing to the byte buffer is
    # platform-independent and matches what the shell expects.
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
