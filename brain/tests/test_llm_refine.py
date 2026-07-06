import json
import subprocess

from skills_companion import llm_refine, paths, stores


def _rec(invoke, state="disabled"):
    return {"item": {"invoke": invoke, "name": invoke, "desc": "d",
                     "category": "c", "source": "plugin", "state": state,
                     "plugin": invoke},
            "score": 1.0,
            "kind": "actionable" if state == "disabled" else "informational",
            "reasons": ["대화: x"]}


LOCAL = [_rec("/a"), _rec("/b"), _rec("/c", state="enabled")]


def test_no_call_below_threshold(claude_home):
    calls = []
    out = llm_refine.refine("S", ["t"], 9, LOCAL,
                            runner=lambda p: calls.append(p) or "[]")
    assert out == LOCAL[:5] and calls == []


def test_llm_recs_pinned_top_with_model_reason(claude_home):
    runner = lambda p: json.dumps([{"invoke": "/c", "reason": "지금 문맥에 딱"}])
    out = llm_refine.refine("S", ["t"] * 10, 10, LOCAL, runner=runner)
    assert [r["item"]["invoke"] for r in out] == ["/c", "/a", "/b"]
    assert out[0]["reasons"] == ["지금 문맥에 딱"]
    assert out[0]["kind"] == "informational"          # kind는 기존 규칙 유지


def test_unknown_invoke_dropped(claude_home):
    runner = lambda p: json.dumps([{"invoke": "/zz", "reason": "x"}])
    out = llm_refine.refine("S1", ["t"], 10, LOCAL, runner=runner)
    assert [r["item"]["invoke"] for r in out] == ["/a", "/b", "/c"]


def test_bad_json_fails_soft_and_marks_cache(claude_home):
    out = llm_refine.refine("S2", ["t"], 10, LOCAL, runner=lambda p: "not json")
    assert [r["item"]["invoke"] for r in out] == ["/a", "/b", "/c"]
    cache = stores.read_json(paths.state_dir() / "llm-recs" / "S2.json", {})
    assert cache["failed"] is True


def test_timeout_fails_soft(claude_home):
    def boom(p):
        raise subprocess.TimeoutExpired("claude", 30)
    out = llm_refine.refine("S3", ["t"], 10, LOCAL, runner=boom)
    assert [r["item"]["invoke"] for r in out] == ["/a", "/b", "/c"]


def test_failed_retries_once_then_stops(claude_home):
    calls = []
    def bad(p):
        calls.append(1)
        raise subprocess.TimeoutExpired("claude", 30)
    for _ in range(3):
        llm_refine.refine("S4", ["t"], 10, LOCAL, runner=bad)
    assert len(calls) == 2


def test_two_windows_max(claude_home):
    calls = []
    def good(p):
        calls.append(1)
        return json.dumps([{"invoke": "/a", "reason": "r"}])
    llm_refine.refine("S5", ["t"], 10, LOCAL, runner=good)   # 창1
    llm_refine.refine("S5", ["t"], 20, LOCAL, runner=good)   # +10<15 → 캐시 재사용
    assert len(calls) == 1
    llm_refine.refine("S5", ["t"], 25, LOCAL, runner=good)   # +15 → 창2
    assert len(calls) == 2
    llm_refine.refine("S5", ["t"], 99, LOCAL, runner=good)   # 창 2개 초과 금지
    assert len(calls) == 2


def test_reason_truncated_to_80(claude_home):
    runner = lambda p: json.dumps([{"invoke": "/a", "reason": "가" * 200}])
    out = llm_refine.refine("S6", ["t"], 10, LOCAL, runner=runner)
    assert len(out[0]["reasons"][0]) == 80


def test_empty_candidates_never_calls(claude_home):
    calls = []
    out = llm_refine.refine("S7", ["t"], 50, [],
                            runner=lambda p: calls.append(p) or "[]")
    assert out == [] and calls == []
