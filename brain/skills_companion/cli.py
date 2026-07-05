import argparse
import json

from . import activation, paths, recommender, revert, scanner, stores, transcripts


def _cmd_recommend(args):
    sess = transcripts.newest_session()
    signals = (transcripts.extract_signals(sess["path"])
               if sess else {"texts": [], "tools": []})
    items = scanner.scan()["items"]
    recs = recommender.recommend(items, signals, top_k=args.top)
    return {"session": sess["session_id"] if sess else None,
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
        out = activation.activate(args.plugin, session_id=sid)
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
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
