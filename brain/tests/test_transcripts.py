import json
import time

from skills_companion import paths, transcripts


def test_newest_session(write_transcript):
    now = time.time()
    write_transcript("OLD1", ["old work"], mtime=now - 500)
    write_transcript("NEW1", ["new work"], mtime=now)
    s = transcripts.newest_session()
    assert s["session_id"] == "NEW1"


def test_extract_signals_texts_and_tools(write_transcript):
    f = write_transcript("S1", ["특허번역 도면 작업", "KIPO 명세서 검수"],
                         tools=["Bash", "Read"])
    sig = transcripts.extract_signals(f)
    assert "특허번역 도면 작업" in sig["texts"]
    assert sig["tools"] == ["Bash", "Read"]


def test_extract_signals_skips_garbage_lines(write_transcript, claude_home):
    f = write_transcript("S2", ["hello"])
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("NOT-JSON\n")
        fh.write(json.dumps({"type": "summary"}) + "\n")
    sig = transcripts.extract_signals(f)
    assert sig["texts"] == ["hello"]


def test_extract_signals_v2_fields(write_transcript):
    f = write_transcript("SV2", ["첫 질문", "둘째 질문 합니다"],
                         tools=["Bash"], cwd="/tmp/proj")
    sig = transcripts.extract_signals(f)
    assert sig["cwd"] == "/tmp/proj"
    assert sig["user_texts"] == ["첫 질문", "둘째 질문 합니다"]
    assert sig["user_msg_count"] == 2
    assert "첫 질문" in sig["texts"] and sig["tools"] == ["Bash"]   # 기존 키 유지


def test_extract_signals_v2_tool_result_turn_not_counted(write_transcript, claude_home):
    f = write_transcript("SV3", ["질문 하나"], cwd="/tmp/proj")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "cwd": "/tmp/proj", "message": {
            "role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}) + "\n")
    sig = transcripts.extract_signals(f)
    assert sig["user_msg_count"] == 1
    assert sig["user_texts"] == ["질문 하나"]


def test_extract_signals_v2_defaults_on_missing_file(claude_home):
    sig = transcripts.extract_signals("/nonexistent/x.jsonl")
    assert sig == {"texts": [], "tools": [], "cwd": "",
                   "user_texts": [], "user_msg_count": 0}


def test_live_sessions_threshold_and_signal(write_transcript, claude_home):
    now = time.time()
    write_transcript("LIVE1", ["x"], mtime=now)
    write_transcript("IDLE1", ["x"], mtime=now - 9999)
    write_transcript("ENDED1", ["x"], mtime=now)
    (paths.signals_dir() / "ENDED1.json").write_text("{}", encoding="utf-8")
    live = transcripts.live_sessions()
    assert live == {"LIVE1"}
    assert transcripts.live_sessions(exclude="LIVE1") == set()
