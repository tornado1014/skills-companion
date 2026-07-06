import json
import os
import time

from . import paths


def newest_session():
    best = None
    for f in paths.projects_dir().glob("*/*.jsonl"):
        try:
            m = f.stat().st_mtime
        except OSError:
            continue
        if best is None or m > best[1]:
            best = (f, m)
    if best is None:
        return None
    return {"session_id": best[0].stem, "path": str(best[0]), "mtime": best[1]}


def extract_signals(path, last_n=30, tail_bytes=400_000):
    empty = {"texts": [], "tools": [], "cwd": "",
             "user_texts": [], "user_msg_count": 0}
    texts, tools, user_texts = [], [], []
    cwd, user_msg_count = "", 0
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                f.readline()  # drop partial line
            data = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return empty
    for line in data.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("cwd"):
            cwd = d["cwd"]
        if d.get("type") not in ("user", "assistant"):
            continue
        content = (d.get("message") or {}).get("content")
        turn_texts = []
        if isinstance(content, str):
            turn_texts.append(content)
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    turn_texts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    tools.append(b.get("name", ""))
        texts.extend(turn_texts)
        if d.get("type") == "user" and any(t.strip() for t in turn_texts):
            user_msg_count += 1
            user_texts.extend(t for t in turn_texts if t.strip())
    return {"texts": texts[-last_n:], "tools": tools[-last_n:], "cwd": cwd,
            "user_texts": user_texts[-last_n:], "user_msg_count": user_msg_count}


def live_sessions(exclude=None, threshold=1800):
    now = time.time()
    live = set()
    for f in paths.projects_dir().glob("*/*.jsonl"):
        sid = f.stem
        if sid == exclude:
            continue
        try:
            if now - f.stat().st_mtime > threshold:
                continue
        except OSError:
            continue
        if (paths.signals_dir() / f"{sid}.json").exists():
            continue
        live.add(sid)
    return live
