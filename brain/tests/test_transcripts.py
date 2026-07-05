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


def test_live_sessions_threshold_and_signal(write_transcript, claude_home):
    now = time.time()
    write_transcript("LIVE1", ["x"], mtime=now)
    write_transcript("IDLE1", ["x"], mtime=now - 9999)
    write_transcript("ENDED1", ["x"], mtime=now)
    (paths.signals_dir() / "ENDED1.json").write_text("{}", encoding="utf-8")
    live = transcripts.live_sessions()
    assert live == {"LIVE1"}
    assert transcripts.live_sessions(exclude="LIVE1") == set()
