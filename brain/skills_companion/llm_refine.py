import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time

from . import paths, stores

FIRST_AT = 10        # 최초 트리거 user_msg_count
STEP = 15            # 다음 창까지 추가 메시지 수
MAX_WINDOWS = 2      # 세션당 트리거 창 최대 수
MAX_ATTEMPTS = 2     # 창당 시도(최초 1 + 재시도 1)
TIMEOUT = 30
MAX_RECS = 3


def _cache_path(session_id):
    d = paths.state_dir() / "llm-recs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{session_id}.json"


def _kill_tree(p):
    # Kill the runner and any children it spawned. On POSIX we created a new
    # session (setsid) so we can signal the whole process group; on Windows we
    # created a new process group and fall back to Popen.kill for the tree.
    if os.name == "nt":
        try:
            p.kill()
        except OSError:
            pass
    else:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def default_runner(prompt):
    # Capture via a temp file (not a pipe) and run in a new session/group.
    # `claude` can spawn background children (MCP servers, hooks); if they
    # inherit a stdout *pipe* they hold it open and defeat the timeout, hanging
    # forever. A file avoids that, and the new session/group lets us kill the
    # whole tree on timeout so nothing lingers. `claude` is an npm shim
    # (claude.cmd) on Windows, so resolve it via PATHEXT with shutil.which.
    exe = shutil.which("claude") or "claude"
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with tempfile.TemporaryFile() as out:
        p = subprocess.Popen(
            [exe, "-p", prompt, "--model", "haiku"],
            stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            **kwargs)
        try:
            p.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            _kill_tree(p)
            p.wait()
            raise
        if p.returncode != 0:
            return None
        out.seek(0)
        return out.read().decode("utf-8", "replace")


def _build_prompt(user_texts, local_recs):
    lines = [
        "당신은 Claude Code 스킬 추천기입니다. 아래 최근 대화와 후보 목록을 보고",
        "지금 가장 유용한 항목을 최대 3개 고르세요. 반드시 JSON 배열만 출력:",
        '[{"invoke": "...", "reason": "한국어 한 줄 이유"}]',
        "", "## 최근 사용자 메시지",
    ]
    lines.extend("- " + t[:500] for t in user_texts[-15:])
    lines.append("")
    lines.append("## 후보")
    lines.extend(f"- {r['item']['invoke']} — {(r['item']['desc'] or '')[:100]}"
                 for r in local_recs[:12])
    return "\n".join(lines)


def _parse(out, allowed):
    try:
        m = re.search(r"\[.*\]", out, re.S)
        data = json.loads(m.group(0)) if m else None
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    recs = []
    for d in data[:MAX_RECS]:
        if not isinstance(d, dict):
            continue
        inv, reason = d.get("invoke"), d.get("reason")
        if inv in allowed and isinstance(reason, str):
            recs.append({"invoke": inv, "reason": reason[:80]})
    return recs


def _window(cache, umc):
    if umc < FIRST_AT:
        return 0
    if cache is None:
        return 1
    w = cache.get("window", 1)
    if w < MAX_WINDOWS and umc >= cache.get("msg_count", 0) + STEP:
        return w + 1
    return w


def _merge(llm_recs, local_recs, top_k):
    by_invoke = {r["item"]["invoke"]: r for r in local_recs}
    merged, used = [], set()
    for lr in llm_recs:
        base = by_invoke.get(lr["invoke"])
        if base is None or lr["invoke"] in used:
            continue
        used.add(lr["invoke"])
        merged.append({**base, "reasons": [lr["reason"]], "llm": True})
    for r in local_recs:
        if r["item"]["invoke"] not in used:
            used.add(r["item"]["invoke"])
            merged.append(r)
    return merged[:top_k]


def refine(session_id, user_texts, user_msg_count, local_recs,
           top_k=5, runner=None):
    if not local_recs:
        return []
    runner = runner or default_runner
    cache = stores.read_json(_cache_path(session_id), None)
    win = _window(cache, user_msg_count)
    if win == 0:
        return local_recs[:top_k]
    same_window = cache is not None and cache.get("window") == win
    attempts = cache.get("attempts", 0) if same_window else 0
    need_call = (not same_window) or (
        cache.get("failed") and attempts < MAX_ATTEMPTS)
    if need_call:
        allowed = {r["item"]["invoke"] for r in local_recs}
        out = None
        try:
            out = runner(_build_prompt(user_texts, local_recs))
        except (subprocess.TimeoutExpired, OSError):
            out = None
        recs = _parse(out, allowed) if out is not None else None
        cache = {"ts": time.time(), "msg_count": user_msg_count,
                 "window": win, "recs": recs or [],
                 "failed": recs is None, "attempts": attempts + 1}
        stores.atomic_write_json(_cache_path(session_id), cache)
    return _merge(cache.get("recs") or [], local_recs, top_k)
