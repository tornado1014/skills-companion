# Skills Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static skills cheat sheet with a resident cross-platform tray app (Tauri shell + Python brain) that lists the skill/plugin catalog with switchable facets, recommends items from the active Claude Code session's transcript (no AI), activates disabled plugins on click, and reverts session-scoped activations per policy.

**Architecture:** A Python "brain" package owns ALL logic (scan, recommend, activate, revert, ledger/config stores) behind a JSON-out CLI, fully unit-testable with a fake `~/.claude` tree via one env var. A thin Tauri v2 Rust shell provides tray/menu/window/dialog/clipboard/notification/macOS-autotype and calls the brain as a subprocess. A SessionEnd hook only drops a signal file; the resident shell reacts to it.

**Tech Stack:** Python 3.9+ stdlib (pytest dev-only) · Tauri v2 (Rust, no npm — `withGlobalTauri` + static `ui/` dir) · tauri-plugin-clipboard-manager, tauri-plugin-notification · bash hook + osascript (mac autotype).

**Spec:** `docs/superpowers/specs/2026-07-06-skills-companion-design.md` (constraints C1–C8 are binding).

## Global Constraints

- Brain = Python **3.9+ stdlib only**; pytest is a dev dependency only. No pip deps at runtime.
- **No AI/LLM/network** anywhere in the recommendation path (spec §8).
- **Activation applies to plugins only**; personal skills are never state-changed (spec §2).
- Every `~/.claude` path goes through `paths.py` and honors env override **`SKILLS_COMPANION_CLAUDE_HOME`** (tests use a tmp tree).
- `settings.json` writes: **atomic + timestamped backup**, change only intended keys, validate JSON (spec §10).
- State lives in `~/.claude/skills-companion/state/` → `ledger.json`, `config.json`, `session-ended/` (spec §5).
- SessionEnd hook must print **nothing to stdout** and `exit 0` (context-injection safety; spec C4/C6).
- Shell = **Tauri v2, no npm/node**: `withGlobalTauri: true`, `frontendDist: ../ui` static files; identifier `com.earendel.skills-companion`; product name `Skills Companion`.
- Defaults (spec §7–8): `default_policy: "ask"`, `poll_seconds: 20`, live-session threshold `1800`s, transcript last-N `30`, top-K `5`, disabled-plugin boost `1.5`, `notifications_enabled: false`, recommendation `min_matches: 2`.
- User-facing UI strings in **Korean**; code identifiers in English.
- Repo root for all paths below: `~/Desktop/Work_with_Claude_Mac/skills-companion/`. Brain tests run from `brain/`: `python3 -m pytest -q`.
- Commit after every task (messages given per task).

## File Structure

```
skills-companion/
├── brain/
│   ├── skills_companion/
│   │   ├── __init__.py
│   │   ├── paths.py          # env-overridable ~/.claude path helpers
│   │   ├── stores.py         # atomic JSON, Config, Ledger, policy_for
│   │   ├── scanner.py        # catalog from skills/ + plugin cache + settings
│   │   ├── transcripts.py    # newest session, signal extraction, live sessions
│   │   ├── recommender.py    # tokenize (en words + ko bigrams), tf-idf score
│   │   ├── activation.py     # enabledPlugins flip + ledger append
│   │   ├── revert.py         # policy engine, concurrency guard, leak sweep
│   │   ├── installer.py      # settings.json hook add/remove (pure + applied)
│   │   └── cli.py            # JSON-out subcommands (sole shell entry point)
│   └── tests/
│       ├── conftest.py       # fake ~/.claude tree + transcript writer
│       ├── test_paths.py ... test_cli.py, test_installer.py (per module)
├── hooks/session-end-signal.sh
├── shell/
│   ├── src-tauri/ (Cargo.toml, build.rs, tauri.conf.json, icons/, src/main.rs)
│   └── ui/ (index.html, revert.html)
├── installer/launchagent.plist  (template)
└── docs/superpowers/{specs,plans}/
```

---

# Phase 1 — Python Brain (CLI-first, TDD)

### Task 1: Scaffold + paths.py

**Files:**
- Create: `brain/skills_companion/__init__.py` (empty), `brain/skills_companion/paths.py`, `brain/tests/__init__.py` (empty), `brain/tests/test_paths.py`, `.gitignore`

**Interfaces:**
- Produces: `paths.claude_home() -> Path`, `settings_path()`, `skills_dir()`, `plugin_cache_dir()`, `projects_dir()`, `state_dir()` (mkdir -p), `ledger_path()`, `config_path()`, `signals_dir()` (mkdir -p). All return `pathlib.Path`; all derive from `SKILLS_COMPANION_CLAUDE_HOME` env or `~/.claude`.

- [ ] **Step 1: Write the failing test**

`brain/tests/test_paths.py`:
```python
from skills_companion import paths


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    assert paths.claude_home() == tmp_path
    assert paths.settings_path() == tmp_path / "settings.json"
    assert paths.skills_dir() == tmp_path / "skills"
    assert paths.plugin_cache_dir() == tmp_path / "plugins" / "cache"
    assert paths.projects_dir() == tmp_path / "projects"


def test_state_dirs_created(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    assert paths.state_dir().is_dir()
    assert paths.signals_dir().is_dir()
    assert paths.ledger_path().name == "ledger.json"
    assert paths.config_path().name == "config.json"


def test_default_is_home_claude(monkeypatch):
    monkeypatch.delenv("SKILLS_COMPANION_CLAUDE_HOME", raising=False)
    assert str(paths.claude_home()).endswith("/.claude")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/Work_with_Claude_Mac/skills-companion/brain && python3 -m pytest tests/test_paths.py -q`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'skills_companion.paths'`

- [ ] **Step 3: Write minimal implementation**

`.gitignore` (repo root):
```
__pycache__/
.pytest_cache/
shell/src-tauri/target/
shell/src-tauri/gen/
```

`brain/skills_companion/paths.py`:
```python
import os
from pathlib import Path


def claude_home() -> Path:
    return Path(os.environ.get("SKILLS_COMPANION_CLAUDE_HOME", "~/.claude")).expanduser()


def settings_path() -> Path:
    return claude_home() / "settings.json"


def skills_dir() -> Path:
    return claude_home() / "skills"


def plugin_cache_dir() -> Path:
    return claude_home() / "plugins" / "cache"


def projects_dir() -> Path:
    return claude_home() / "projects"


def state_dir() -> Path:
    p = claude_home() / "skills-companion" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path() -> Path:
    return state_dir() / "ledger.json"


def config_path() -> Path:
    return state_dir() / "config.json"


def signals_dir() -> Path:
    p = state_dir() / "session-ended"
    p.mkdir(parents=True, exist_ok=True)
    return p
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_paths.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/Work_with_Claude_Mac/skills-companion
git add .gitignore brain
git commit -m "feat(brain): scaffold package with env-overridable path helpers"
```

---

### Task 2: stores.py — atomic JSON, Config, Ledger

**Files:**
- Create: `brain/skills_companion/stores.py`, `brain/tests/test_stores.py`

**Interfaces:**
- Consumes: `paths.*` from Task 1.
- Produces: `read_json(path, default)`, `atomic_write_json(path, data, backup=False)`,
  `DEFAULT_CONFIG`, `load_config() -> dict`, `save_config(cfg)`, `policy_for(plugin: str, cfg: dict) -> str`,
  `load_ledger() -> dict`, `save_ledger(l)`, `ledger_add(session_id, plugin, cwd="") -> dict`,
  `ledger_remove(session_id, plugin=None) -> dict`.
  Ledger shape: `{session_id: [{"plugin": str, "activated_at": float, "cwd": str}, ...]}`.

- [ ] **Step 1: Write the failing test**

`brain/tests/test_stores.py`:
```python
import json

from skills_companion import paths, stores


def test_read_json_default_on_missing(tmp_path):
    assert stores.read_json(tmp_path / "nope.json", {"a": 1}) == {"a": 1}


def test_atomic_write_creates_backup(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"old": true}', encoding="utf-8")
    stores.atomic_write_json(p, {"new": True}, backup=True)
    assert json.loads(p.read_text(encoding="utf-8")) == {"new": True}
    baks = list(tmp_path.glob("s.json.bak.*"))
    assert len(baks) == 1
    assert json.loads(baks[0].read_text(encoding="utf-8")) == {"old": True}


def test_config_defaults_and_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    cfg = stores.load_config()
    assert cfg["default_policy"] == "ask"
    assert cfg["poll_seconds"] == 20
    assert cfg["notifications_enabled"] is False
    cfg["per_plugin"]["x@m"] = "keep"
    stores.save_config(cfg)
    cfg2 = stores.load_config()
    assert stores.policy_for("x@m", cfg2) == "keep"
    assert stores.policy_for("other@m", cfg2) == "ask"


def test_ledger_add_dedup_and_remove(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(tmp_path))
    stores.ledger_add("S1", "ua@ua", cwd="/w")
    stores.ledger_add("S1", "ua@ua")           # dedup
    stores.ledger_add("S1", "kl@kl")
    led = stores.load_ledger()
    assert [e["plugin"] for e in led["S1"]] == ["ua@ua", "kl@kl"]
    stores.ledger_remove("S1", "ua@ua")
    assert [e["plugin"] for e in stores.load_ledger()["S1"]] == ["kl@kl"]
    stores.ledger_remove("S1", "kl@kl")
    assert "S1" not in stores.load_ledger()    # empty list pruned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_stores.py -q`
Expected: FAIL — `No module named 'skills_companion.stores'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/stores.py`:
```python
import json
import os
import shutil
import tempfile
import time

from . import paths

DEFAULT_CONFIG = {
    "default_policy": "ask",       # ask | auto-revert | keep
    "per_plugin": {},              # plugin_key -> policy
    "notifications_enabled": False,
    "poll_seconds": 20,
}


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_write_json(path, data, backup=False):
    path = str(path)
    if backup and os.path.exists(path):
        ts = time.strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, f"{path}.bak.{ts}")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(read_json(paths.config_path(), {}))
    cfg.setdefault("per_plugin", {})
    return cfg


def save_config(cfg):
    atomic_write_json(paths.config_path(), cfg)


def policy_for(plugin, cfg):
    return cfg.get("per_plugin", {}).get(plugin, cfg.get("default_policy", "ask"))


def load_ledger():
    return read_json(paths.ledger_path(), {})


def save_ledger(ledger):
    atomic_write_json(paths.ledger_path(), ledger)


def ledger_add(session_id, plugin, cwd=""):
    ledger = load_ledger()
    entries = ledger.setdefault(session_id, [])
    if not any(e["plugin"] == plugin for e in entries):
        entries.append({"plugin": plugin, "activated_at": time.time(), "cwd": cwd})
    save_ledger(ledger)
    return ledger


def ledger_remove(session_id, plugin=None):
    ledger = load_ledger()
    if plugin is None:
        ledger.pop(session_id, None)
    elif session_id in ledger:
        ledger[session_id] = [e for e in ledger[session_id] if e["plugin"] != plugin]
        if not ledger[session_id]:
            ledger.pop(session_id)
    save_ledger(ledger)
    return ledger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_stores.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): stores — atomic JSON with backup, config defaults, ledger"
```

---

### Task 3: Shared test fixture (fake ~/.claude tree)

**Files:**
- Create: `brain/tests/conftest.py`

**Interfaces:**
- Produces (for all later tests):
  - fixture `claude_home` → builds tmp `~/.claude` with: 2 personal skills (`patent-en-ko-kipo` silenced, `domain-modeling` loaded), plugin cache for `understand-anything` (skill `understand`) and `korean-law` (command `research`), `settings.json` with `enabledPlugins {"understand-anything@understand-anything": false, "korean-law@korean-law-marketplace": true}` and `skillOverrides {"patent-en-ko-kipo": "user-invocable-only"}`; sets the env var; returns the home `Path`.
  - fixture `write_transcript` → `fn(session_id, texts, mtime=None, tools=None) -> Path` writing a `.jsonl` under `projects/-tmp-work/`.

- [ ] **Step 1: Write the fixture (no dedicated test; consumed by Tasks 4–9)**

`brain/tests/conftest.py`:
```python
import json
import os

import pytest


def _skill(home, folder, name, desc):
    d = home / "skills" / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8"
    )


@pytest.fixture
def claude_home(tmp_path, monkeypatch):
    home = tmp_path / ".claude"
    _skill(home, "patent-en-ko-kipo", "patent-en-ko-kipo",
           "영문 특허 docx를 KIPO 명세서로 번역. Triggers: 특허번역, KIPO 명세서")
    _skill(home, "domain-modeling", "domain-modeling",
           "Build and sharpen the project domain model glossary")
    ua = home / "plugins" / "cache" / "ua-mkt" / "understand-anything" / "2.8.2"
    (ua / "skills" / "understand").mkdir(parents=True)
    (ua / "skills" / "understand" / "SKILL.md").write_text(
        "---\nname: understand\ndescription: Analyze a codebase to produce an "
        "interactive knowledge graph of architecture and components\n---\nbody\n",
        encoding="utf-8")
    kl = home / "plugins" / "cache" / "kl-mkt" / "korean-law" / "4.4.1"
    (kl / "commands").mkdir(parents=True)
    (kl / "commands" / "research.md").write_text(
        "---\nname: research\ndescription: 법령 판례 리서치 legal research\n---\nbody\n",
        encoding="utf-8")
    settings = {
        "enabledPlugins": {
            "understand-anything@understand-anything": False,
            "korean-law@korean-law-marketplace": True,
        },
        "skillOverrides": {"patent-en-ko-kipo": "user-invocable-only"},
    }
    (home / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    (home / "projects" / "-tmp-work").mkdir(parents=True)
    monkeypatch.setenv("SKILLS_COMPANION_CLAUDE_HOME", str(home))
    return home


@pytest.fixture
def write_transcript(claude_home):
    def _write(session_id, texts, mtime=None, tools=None):
        lines = []
        for t in texts:
            lines.append(json.dumps(
                {"type": "user", "sessionId": session_id, "cwd": "/tmp/work",
                 "message": {"role": "user", "content": t}}, ensure_ascii=False))
        for name in tools or []:
            lines.append(json.dumps(
                {"type": "assistant",
                 "message": {"role": "assistant",
                             "content": [{"type": "tool_use", "name": name},
                                         {"type": "text", "text": "ok"}]}},
                ensure_ascii=False))
        f = claude_home / "projects" / "-tmp-work" / f"{session_id}.jsonl"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if mtime is not None:
            os.utime(f, (mtime, mtime))
        return f
    return _write
```

- [ ] **Step 2: Verify collection is clean**

Run: `python3 -m pytest -q`
Expected: `7 passed` (Tasks 1–2 tests still green; conftest imports without error)

- [ ] **Step 3: Commit**

```bash
git add brain/tests/conftest.py
git commit -m "test(brain): shared fake ~/.claude fixture and transcript writer"
```

---

### Task 4: scanner.py — the Catalog

**Files:**
- Create: `brain/skills_companion/scanner.py`, `brain/tests/test_scanner.py`

**Interfaces:**
- Consumes: `paths`, `stores.read_json`, fixture `claude_home`.
- Produces: `scan() -> {"items": [CatalogItem]}` with CatalogItem =
  `{"invoke","name","desc","source" ("personal"|"plugin"),"plugin" (key or None),"category","state" ("loaded"|"silenced"|"enabled"|"disabled"),"invocation" ("auto"|"manual"|"command")}`.
  Also `parse_frontmatter(path) -> (name|None, desc|None)`, `find_plugin_root(pname) -> Path|None`, `categorize(name, desc) -> str`.
  **Disabled plugins ARE scanned** (their items carry `state:"disabled"`) — required by the recommender.

- [ ] **Step 1: Write the failing test**

`brain/tests/test_scanner.py`:
```python
from skills_companion import scanner


def _by_invoke(items):
    return {i["invoke"]: i for i in items}


def test_scan_personal_states(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    kipo = items["/patent-en-ko-kipo"]
    assert kipo["source"] == "personal" and kipo["plugin"] is None
    assert kipo["state"] == "silenced" and kipo["invocation"] == "manual"
    dm = items["/domain-modeling"]
    assert dm["state"] == "loaded" and dm["invocation"] == "auto"


def test_scan_includes_disabled_plugin_items(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    ua = items["/understand-anything:understand"]
    assert ua["source"] == "plugin"
    assert ua["plugin"] == "understand-anything@understand-anything"
    assert ua["state"] == "disabled" and ua["invocation"] == "auto"
    kl = items["/korean-law:research"]
    assert kl["state"] == "enabled" and kl["invocation"] == "command"
    assert kl["plugin"] == "korean-law@korean-law-marketplace"


def test_categorize_korean_keywords(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    assert items["/patent-en-ko-kipo"]["category"] == "특허 · 번역"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scanner.py -q`
Expected: FAIL — `No module named 'skills_companion.scanner'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/scanner.py`:
```python
import re

from . import paths, stores

CATEGORY_RULES = [
    ("특허 · 번역", ["patent", "kipo", "welo", "oa-", "invention", "translat",
                    "gl-postedit", "globallink", "특허", "번역", "명세서"]),
    ("카카오 · 콘텐츠", ["kakao", "카톡", "chat-summary", "briefing", "curate",
                       "needs", "digest", "카카오"]),
    ("소셜 · 스카우팅", ["linkedin", "twitter", "threads", "slack", "scout"]),
    ("노트 · 지식", ["obsidian", "vault", "matjip", "graphify", "daily-bible",
                   "care-group", "볼트", "노트", "묵상"]),
    ("사고 · 프로세스", ["grill", "domain-modeling", "decision", "brainstorm",
                      "plan", "critic", "handoff", "teach", "triage"]),
    ("QA · 자동화", ["browse", "dogfood", "qa", "agent-browser", "electron",
                   "macos", "ssh", "gstack"]),
    ("문서 · 시각화", ["interactive-learning", "pptx", "metrics", "retro", "hwp",
                    "defuddle", "dashboard", "visualiz", "학습"]),
    ("시스템 · 설정", ["skill", "setup", "ship", "review", "launcher", "transplant"]),
]


def parse_frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None, None
    return _scalar(m.group(1), "name"), _scalar(m.group(1), "description")


def _scalar(fm, key):
    mb = re.search(rf"^{key}:\s*[>|]\s*\n((?:[ \t]+.*\n?)+)", fm, re.M)
    if mb:
        return " ".join(x.strip() for x in mb.group(1).splitlines() if x.strip())
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    if not m:
        return None
    val = m.group(1).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        val = val[1:-1]
    return val.strip()


def categorize(name, desc):
    hay = f"{name} {desc}".lower()
    for cat, kws in CATEGORY_RULES:
        if any(kw in hay for kw in kws):
            return cat
    return "기타"


def find_plugin_root(pname):
    cache = paths.plugin_cache_dir()
    if not cache.is_dir():
        return None
    for mk in sorted(cache.iterdir()):
        cand = mk / pname
        if cand.is_dir():
            vers = sorted(v for v in cand.iterdir() if v.is_dir())
            if vers:
                return vers[-1]
    return None


def scan():
    settings = stores.read_json(paths.settings_path(), {})
    overrides = settings.get("skillOverrides", {})
    enabled = settings.get("enabledPlugins", {})
    items = []
    if paths.skills_dir().is_dir():
        for sk in sorted(paths.skills_dir().glob("*/SKILL.md")):
            folder = sk.parent.name
            name, desc = parse_frontmatter(sk)
            name, desc = name or folder, desc or ""
            silenced = overrides.get(name) or overrides.get(folder)
            items.append({
                "invoke": f"/{folder}", "name": name, "desc": desc,
                "source": "personal", "plugin": None,
                "category": categorize(f"{folder} {name}", desc),
                "state": "silenced" if silenced else "loaded",
                "invocation": "manual" if silenced else "auto",
            })
    for key, on in enabled.items():
        pname = key.split("@", 1)[0]
        root = find_plugin_root(pname)
        if root is None:
            continue
        state = "enabled" if on else "disabled"
        for sk in sorted(root.glob("skills/**/SKILL.md")):
            n, ds = parse_frontmatter(sk)
            if not n:
                continue
            items.append({"invoke": f"/{pname}:{n}", "name": n, "desc": ds or "",
                          "source": "plugin", "plugin": key, "category": pname,
                          "state": state, "invocation": "auto"})
        for cmd in sorted(root.glob("commands/**/*.md")):
            n, ds = parse_frontmatter(cmd)
            n = n or cmd.stem
            items.append({"invoke": f"/{pname}:{n}", "name": n,
                          "desc": ds or "(command)", "source": "plugin",
                          "plugin": key, "category": pname,
                          "state": state, "invocation": "command"})
    return {"items": items}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scanner.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): scanner — catalog incl. disabled plugins (port of cheatsheet generator)"
```

---

### Task 5: transcripts.py — session signals

**Files:**
- Create: `brain/skills_companion/transcripts.py`, `brain/tests/test_transcripts.py`

**Interfaces:**
- Consumes: `paths`, fixtures.
- Produces:
  - `newest_session() -> {"session_id","path","mtime"} | None` (newest `projects/*/*.jsonl` by mtime),
  - `extract_signals(path, last_n=30, tail_bytes=400_000) -> {"texts":[str], "tools":[str]}` (tolerant tail parse; handles str content and block-list content),
  - `live_sessions(exclude=None, threshold=1800) -> set[str]` (recent mtime AND no end-signal file).

- [ ] **Step 1: Write the failing test**

`brain/tests/test_transcripts.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_transcripts.py -q`
Expected: FAIL — `No module named 'skills_companion.transcripts'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/transcripts.py`:
```python
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
    texts, tools = [], []
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                f.readline()  # drop partial line
            data = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return {"texts": [], "tools": []}
    for line in data.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") not in ("user", "assistant"):
            continue
        content = (d.get("message") or {}).get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    tools.append(b.get("name", ""))
    return {"texts": texts[-last_n:], "tools": tools[-last_n:]}


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_transcripts.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): transcripts — newest session, tail signal extraction, live-session set"
```

---

### Task 6: recommender.py — no-AI matching

**Files:**
- Create: `brain/skills_companion/recommender.py`, `brain/tests/test_recommender.py`

**Interfaces:**
- Consumes: CatalogItem dicts (Task 4), signals dict (Task 5).
- Produces: `tokenize(text) -> list[str]` (lowercase EN words minus stopwords + Korean char bigrams);
  `recommend(items, signals, top_k=5, min_matches=2) -> [ {"item", "score", "kind" ("actionable"|"informational"), "reasons": [str]} ]`
  sorted by score desc; actionable = plugin item with `state=="disabled"` (score ×1.5).

- [ ] **Step 1: Write the failing test**

`brain/tests/test_recommender.py`:
```python
from skills_companion import recommender, scanner


def test_tokenize_english_and_korean_bigrams():
    toks = recommender.tokenize("Analyze the Codebase 특허번역")
    assert "analyze" in toks and "codebase" in toks
    assert "the" not in toks                      # stopword
    assert "특허" in toks and "허번" in toks and "번역" in toks


def test_actionable_recommendation_for_disabled_plugin(claude_home):
    items = scanner.scan()["items"]
    signals = {"texts": ["I need to analyze this codebase architecture",
                         "build a knowledge graph of components"], "tools": []}
    recs = recommender.recommend(items, signals)
    assert recs, "expected at least one recommendation"
    top = recs[0]
    assert top["item"]["invoke"] == "/understand-anything:understand"
    assert top["kind"] == "actionable"
    assert "codebase" in top["reasons"] or "knowledge" in top["reasons"]


def test_korean_match_informational(claude_home):
    items = scanner.scan()["items"]
    signals = {"texts": ["특허번역 명세서 작업을 계속하자"], "tools": []}
    recs = recommender.recommend(items, signals)
    invokes = [r["item"]["invoke"] for r in recs]
    assert "/patent-en-ko-kipo" in invokes
    kipo = next(r for r in recs if r["item"]["invoke"] == "/patent-en-ko-kipo")
    assert kipo["kind"] == "informational"


def test_min_matches_cuts_noise(claude_home):
    items = scanner.scan()["items"]
    recs = recommender.recommend(items, {"texts": ["hello there"], "tools": []})
    assert recs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_recommender.py -q`
Expected: FAIL — `No module named 'skills_companion.recommender'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/recommender.py`:
```python
import math
import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "be", "this", "that", "it", "i", "you", "we",
    "need", "want", "please", "let", "use", "using", "make", "help",
}

BOOST_DISABLED = 1.5


def tokenize(text):
    text = text.lower()
    en = [t for t in re.findall(r"[a-z][a-z0-9_-]{1,}", text) if t not in STOPWORDS]
    bigrams = []
    for chunk in re.findall(r"[가-힣]{2,}", text):
        bigrams.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return en + bigrams


def _corpus(item):
    return set(tokenize(
        f"{item['invoke']} {item['name']} {item['desc']} {item['category']}"))


def recommend(items, signals, top_k=5, min_matches=2):
    query = Counter(tokenize(" ".join(
        signals.get("texts", []) + signals.get("tools", []))))
    if not query:
        return []
    corpora = [_corpus(i) for i in items]
    df = Counter()
    for c in corpora:
        df.update(c)
    n = max(len(items), 1)
    recs = []
    for item, corpus in zip(items, corpora):
        matched = [t for t in query if t in corpus]
        if len(matched) < min_matches:
            continue
        score = sum(query[t] * math.log(1 + n / df[t]) for t in matched)
        score /= math.sqrt(len(corpus) or 1)
        actionable = item["source"] == "plugin" and item["state"] == "disabled"
        if actionable:
            score *= BOOST_DISABLED
        recs.append({
            "item": item,
            "score": round(score, 4),
            "kind": "actionable" if actionable else "informational",
            "reasons": sorted(matched, key=lambda t: -query[t])[:5],
        })
    recs.sort(key=lambda r: -r["score"])
    return recs[:top_k]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_recommender.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): recommender — tf-idf keyword match, ko bigrams, disabled-plugin boost"
```

---

### Task 7: activation.py

**Files:**
- Create: `brain/skills_companion/activation.py`, `brain/tests/test_activation.py`

**Interfaces:**
- Consumes: `paths`, `stores`.
- Produces: `RELOAD = "/reload-plugins"`;
  `activate(plugin_key, session_id=None, cwd="") -> {"ok", "already_enabled"?, "reload_command"?, "error"?}` — flips `enabledPlugins[key]` false→true with backup; ledger-tracks **only** when the app flipped it (spec §10); unknown key → error; already-true → ok/no-op/no ledger.
  `deactivate(plugin_key) -> {"ok", "error"?}` — sets false (idempotent).

- [ ] **Step 1: Write the failing test**

`brain/tests/test_activation.py`:
```python
import json

from skills_companion import activation, paths, stores

UA = "understand-anything@understand-anything"
KL = "korean-law@korean-law-marketplace"


def _settings(home):
    return json.loads((home / "settings.json").read_text(encoding="utf-8"))


def test_activate_flips_and_ledgers(claude_home):
    r = activation.activate(UA, session_id="S1", cwd="/w")
    assert r["ok"] and r["already_enabled"] is False
    assert r["reload_command"] == "/reload-plugins"
    assert _settings(claude_home)["enabledPlugins"][UA] is True
    assert list(claude_home.glob("settings.json.bak.*"))          # backup made
    assert [e["plugin"] for e in stores.load_ledger()["S1"]] == [UA]
    # unrelated keys untouched
    assert _settings(claude_home)["skillOverrides"] == {
        "patent-en-ko-kipo": "user-invocable-only"}


def test_activate_already_enabled_no_ledger(claude_home):
    r = activation.activate(KL, session_id="S1")
    assert r["ok"] and r["already_enabled"] is True
    assert "S1" not in stores.load_ledger()


def test_activate_unknown_plugin(claude_home):
    r = activation.activate("nope@nowhere", session_id="S1")
    assert r["ok"] is False and "unknown" in r["error"]


def test_deactivate(claude_home):
    activation.activate(UA, session_id="S1")
    r = activation.deactivate(UA)
    assert r["ok"]
    assert _settings(claude_home)["enabledPlugins"][UA] is False
    r2 = activation.deactivate(UA)                                # idempotent
    assert r2["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_activation.py -q`
Expected: FAIL — `No module named 'skills_companion.activation'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/activation.py`:
```python
from . import paths, stores

RELOAD = "/reload-plugins"


def _load_settings():
    return stores.read_json(paths.settings_path(), None)


def activate(plugin_key, session_id=None, cwd=""):
    settings = _load_settings()
    if settings is None:
        return {"ok": False, "error": "settings-not-found"}
    ep = settings.get("enabledPlugins", {})
    if plugin_key not in ep:
        return {"ok": False, "error": f"unknown-plugin: {plugin_key}"}
    if ep[plugin_key]:
        return {"ok": True, "already_enabled": True, "reload_command": RELOAD}
    ep[plugin_key] = True
    stores.atomic_write_json(paths.settings_path(), settings, backup=True)
    if session_id:
        stores.ledger_add(session_id, plugin_key, cwd)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_activation.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): activation — guarded enabledPlugins flip with ledger tracking"
```

---

### Task 8: revert.py — policy engine, guard, sweep

**Files:**
- Create: `brain/skills_companion/revert.py`, `brain/tests/test_revert.py`

**Interfaces:**
- Consumes: `stores` (config/ledger/policy_for), `activation.deactivate`, `transcripts.live_sessions`, `paths.signals_dir()`.
- Produces:
  - `on_session_end(session_id, reason="other") -> {"action" ("none"|"done"|"ask"), "reverted":[], "kept":[], "ask":[]}` — concurrency guard first, then per-plugin policy; deletes the signal file unless `ask` remains; **idempotent** (processed entries leave the ledger).
  - `apply_decisions(session_id, decisions) -> {"reverted":[], "kept":[]}` with decisions `[{"plugin","action" ("revert"|"keep"),"remember": bool}]`; `remember` writes `per_plugin` policy; deletes the signal when the session's ledger is empty.
  - `sweep(idle_threshold=1800) -> {"leaks": [session_id]}` — ledger sessions with no signal file and idle/missing transcript.

- [ ] **Step 1: Write the failing test**

`brain/tests/test_revert.py`:
```python
import json
import time

from skills_companion import activation, paths, revert, stores

UA = "understand-anything@understand-anything"
KL = "korean-law@korean-law-marketplace"


def _enabled(home, key):
    s = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    return s["enabledPlugins"][key]


def _signal(sid):
    p = paths.signals_dir() / f"{sid}.json"
    p.write_text(json.dumps({"reason": "other", "ts": time.time()}), encoding="utf-8")
    return p


def test_default_policy_ask(claude_home):
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    out = revert.on_session_end("S1")
    assert out["action"] == "ask" and out["ask"] == [UA]
    assert sig.exists()                       # kept until decisions applied
    assert _enabled(claude_home, UA) is True  # nothing reverted yet


def test_auto_revert_policy(claude_home):
    cfg = stores.load_config()
    cfg["per_plugin"][UA] = "auto-revert"
    stores.save_config(cfg)
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    out = revert.on_session_end("S1")
    assert out["reverted"] == [UA] and out["action"] == "done"
    assert _enabled(claude_home, UA) is False
    assert "S1" not in stores.load_ledger()
    assert not sig.exists()


def test_keep_policy(claude_home):
    cfg = stores.load_config()
    cfg["per_plugin"][UA] = "keep"
    stores.save_config(cfg)
    activation.activate(UA, session_id="S1")
    _signal("S1")
    out = revert.on_session_end("S1")
    assert out["kept"] == [UA]
    assert _enabled(claude_home, UA) is True
    assert "S1" not in stores.load_ledger()


def test_concurrency_guard(claude_home, write_transcript):
    activation.activate(UA, session_id="S1")
    stores.ledger_add("S2", UA)                       # S2 also holds it
    write_transcript("S2", ["still working"], mtime=time.time())  # S2 live
    _signal("S1")
    out = revert.on_session_end("S1")
    assert out["kept"] == [UA] and out["ask"] == []
    assert _enabled(claude_home, UA) is True          # guarded
    assert "S1" not in stores.load_ledger()
    assert "S2" in stores.load_ledger()


def test_apply_decisions_with_remember(claude_home):
    activation.activate(UA, session_id="S1")
    sig = _signal("S1")
    revert.on_session_end("S1")                       # -> ask
    out = revert.apply_decisions(
        "S1", [{"plugin": UA, "action": "revert", "remember": True}])
    assert out["reverted"] == [UA]
    assert _enabled(claude_home, UA) is False
    assert stores.load_config()["per_plugin"][UA] == "auto-revert"
    assert not sig.exists()


def test_sweep_finds_leaks(claude_home, write_transcript):
    activation.activate(UA, session_id="GONE")
    write_transcript("GONE", ["x"], mtime=time.time() - 9999)
    assert revert.sweep()["leaks"] == ["GONE"]
    _signal("GONE")                                   # signal pending -> not a leak
    assert revert.sweep()["leaks"] == []


def test_no_entries_cleans_signal(claude_home):
    sig = _signal("EMPTY")
    out = revert.on_session_end("EMPTY")
    assert out["action"] == "none"
    assert not sig.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_revert.py -q`
Expected: FAIL — `No module named 'skills_companion.revert'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/revert.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_revert.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): revert engine — policy matrix, concurrency guard, leak sweep"
```

---

### Task 9: cli.py — the shell's single entry point

**Files:**
- Create: `brain/skills_companion/cli.py`, `brain/tests/test_cli.py`

**Interfaces:**
- Consumes: all Phase-1 modules.
- Produces: `main(argv=None) -> int`, prints ONE JSON object to stdout. Subcommands:
  - `scan` → `scanner.scan()`
  - `recommend [--top K]` → `{"session": sid|null, "recommendations": [...]}` (newest session's signals; empty signals → empty recs)
  - `activate --plugin KEY [--session SID]` → activation result (+`"session"` used; defaults to newest)
  - `session-end --session SID [--reason R]` → revert result
  - `apply-decisions --session SID --decisions JSON` → apply result
  - `sweep` → `{"leaks": [...]}` · `pending` → `{"sessions": [{"session_id","reason"}]}`
  - `config-get` → config · `config-set --json J` → merged config
  - (Task 13 adds `install-hooks`/`uninstall-hooks`.)
- Runnable as `python3 -m skills_companion.cli ...` (add `__main__` guard).

- [ ] **Step 1: Write the failing test**

`brain/tests/test_cli.py`:
```python
import json
import time

from skills_companion import cli, paths

UA = "understand-anything@understand-anything"


def _run(capsys, argv):
    assert cli.main(argv) == 0
    return json.loads(capsys.readouterr().out)


def test_scan(claude_home, capsys):
    out = _run(capsys, ["scan"])
    assert any(i["invoke"] == "/domain-modeling" for i in out["items"])


def test_recommend_uses_newest_session(claude_home, write_transcript, capsys):
    write_transcript("S9", ["analyze the codebase architecture knowledge graph"])
    out = _run(capsys, ["recommend", "--top", "3"])
    assert out["session"] == "S9"
    assert out["recommendations"][0]["item"]["invoke"] == \
        "/understand-anything:understand"


def test_activate_session_end_roundtrip(claude_home, write_transcript, capsys):
    write_transcript("S9", ["work"], mtime=time.time() - 99999)  # not live later
    out = _run(capsys, ["activate", "--plugin", UA, "--session", "S9"])
    assert out["ok"] is True
    (paths.signals_dir() / "S9.json").write_text(
        json.dumps({"reason": "other", "ts": time.time()}), encoding="utf-8")
    pend = _run(capsys, ["pending"])
    assert pend["sessions"][0]["session_id"] == "S9"
    end = _run(capsys, ["session-end", "--session", "S9"])
    assert end["action"] == "ask" and end["ask"] == [UA]
    dec = json.dumps([{"plugin": UA, "action": "keep", "remember": True}])
    ap = _run(capsys, ["apply-decisions", "--session", "S9", "--decisions", dec])
    assert ap["kept"] == [UA]
    cfg = _run(capsys, ["config-get"])
    assert cfg["per_plugin"][UA] == "keep"


def test_config_set_merges(claude_home, capsys):
    out = _run(capsys, ["config-set", "--json", '{"default_policy": "keep"}'])
    assert out["default_policy"] == "keep"
    assert out["poll_seconds"] == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -q`
Expected: FAIL — `No module named 'skills_companion.cli'`

- [ ] **Step 3: Write minimal implementation**

`brain/skills_companion/cli.py`:
```python
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
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m pytest -q`
Expected: `33 passed` (all Phase-1 tests: 3+4+3+4+4+4+7+4)

- [ ] **Step 5: Commit**

```bash
git add brain
git commit -m "feat(brain): JSON CLI — scan/recommend/activate/session-end/decisions/sweep/pending/config"
```

---

# Phase 2 — Tauri Shell

### Task 10: Toolchain + Tauri scaffold (builds and shows tray)

**Files:**
- Create: `shell/src-tauri/Cargo.toml`, `shell/src-tauri/build.rs`, `shell/src-tauri/tauri.conf.json`, `shell/src-tauri/src/main.rs` (minimal), `shell/ui/index.html` (placeholder page, replaced in Task 12), `shell/src-tauri/icons/*` (generated)

**Interfaces:**
- Produces: a running tray app skeleton: tray icon, menu (열기/종료), hidden main window that shows on 열기, hides on close. Later tasks extend `main.rs`.

- [ ] **Step 1: Install toolchain (rustc/cargo are NOT installed on this machine)**

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
rustc --version && cargo --version
cargo install tauri-cli --version '^2' --locked
cargo tauri --version
xcode-select -p || xcode-select --install
```
Expected: rustc/cargo/tauri-cli print versions. (tauri-cli compile takes several minutes — run in background.)

- [ ] **Step 2: Write scaffold files**

`shell/src-tauri/Cargo.toml`:
```toml
[package]
name = "skills-companion"
version = "0.1.0"
edition = "2021"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = ["tray-icon"] }
tauri-plugin-clipboard-manager = "2"
tauri-plugin-notification = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

`shell/src-tauri/build.rs`:
```rust
fn main() {
    tauri_build::build()
}
```

`shell/src-tauri/tauri.conf.json`:
```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Skills Companion",
  "version": "0.1.0",
  "identifier": "com.earendel.skills-companion",
  "build": { "frontendDist": "../ui" },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      { "label": "main", "title": "Skills Companion",
        "width": 980, "height": 720, "visible": false }
    ]
  },
  "bundle": { "active": true, "targets": ["app"],
              "icon": ["icons/32x32.png", "icons/128x128.png",
                       "icons/icon.icns", "icons/icon.png"] }
}
```

`shell/ui/index.html` (placeholder; real UI in Task 12):
```html
<!doctype html><meta charset="utf-8"><title>Skills Companion</title>
<body style="font-family:sans-serif"><h1>Skills Companion (loading…)</h1></body>
```

`shell/src-tauri/src/main.rs` (skeleton):
```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager,
};

fn open_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            let open_i = MenuItem::with_id(app, "open", "Skills Companion 열기",
                                           true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&open_i, &sep, &quit_i])?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, e| match e.id().as_ref() {
                    "open" => open_main(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(|w, e| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = e {
                let _ = w.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Skills Companion");
}
```

- [ ] **Step 3: Generate icons (stdlib-only PNG, then tauri icon)**

```bash
cd ~/Desktop/Work_with_Claude_Mac/skills-companion
python3 - <<'PY'
import struct, zlib
def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + \
        struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
W = H = 512
raw = b"".join(b"\x00" + bytes((37, 99, 235, 255)) * W for _ in range(H))
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
open("icon-src.png", "wb").write(png)
PY
cd shell/src-tauri && cargo tauri icon ../../icon-src.png
ls icons/ | head
```
Expected: `icons/` contains `icon.icns`, `icon.png`, `32x32.png`, `128x128.png`, …

- [ ] **Step 4: Build and smoke-test**

Run (background, first build takes minutes): `cd shell/src-tauri && cargo build 2>&1 | tail -20`
Expected: `Finished` with no errors. **If the compiler reports Tauri v2 API drift** (e.g. `show_menu_on_left_click` renamed), fix per compiler suggestion — the tray/menu/window API surface is the only expected drift area.
Then: `cargo tauri dev` briefly → menu-bar icon appears; 열기 shows the placeholder window; closing the window hides it (app stays in tray); 종료 quits. Ctrl+C to stop dev.

- [ ] **Step 5: Commit**

```bash
git add shell icon-src.png
git commit -m "feat(shell): Tauri v2 scaffold — tray skeleton, hidden main window, icons"
```

---

### Task 11: Rust commands + poll loop (brain bridge, signals→revert window, dynamic tray)

**Files:**
- Modify: `shell/src-tauri/src/main.rs` (replace whole file with the version below)

**Interfaces:**
- Consumes: brain CLI (Task 9) via `python3 -m skills_companion.cli`.
- Produces JS-invokable commands: `brain(args: string[]) -> JSON`, `copy_text(text)`, `notify(title, body)`, `autotype_reload() -> bool`. Poll loop every `poll_seconds`: processes `pending` + `sweep` sessions through `session-end` (opens `revert.html?session=SID` window when `action=="ask"`), refreshes tray menu with top-3 recommendations (`rec:0..2` menu ids), sends opt-in notifications for new actionable recs.

- [ ] **Step 1: Replace `main.rs`**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashSet;
use std::process::Command;
use std::sync::Mutex;
use std::time::Duration;

use serde_json::Value;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, WebviewUrl, WebviewWindowBuilder,
};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_notification::NotificationExt;

struct RecState(Mutex<Vec<Value>>);

fn brain_dir() -> String {
    let home = std::env::var("HOME").unwrap_or_default();
    format!("{home}/Desktop/Work_with_Claude_Mac/skills-companion/brain")
}

fn run_brain(args: &[&str]) -> Result<Value, String> {
    let out = Command::new("python3")
        .args(["-m", "skills_companion.cli"])
        .args(args)
        .env("PYTHONPATH", brain_dir())
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).into_owned());
    }
    serde_json::from_slice(&out.stdout).map_err(|e| e.to_string())
}

#[tauri::command]
fn brain(args: Vec<String>) -> Result<Value, String> {
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    run_brain(&refs)
}

#[tauri::command]
fn copy_text(app: AppHandle, text: String) -> Result<(), String> {
    app.clipboard().write_text(text).map_err(|e| e.to_string())
}

#[tauri::command]
fn notify(app: AppHandle, title: String, body: String) {
    let _ = app.notification().builder().title(title).body(body).show();
}

#[tauri::command]
fn autotype_reload() -> bool {
    #[cfg(target_os = "macos")]
    {
        let script = r#"tell application "System Events"
  set frontApp to name of first application process whose frontmost is true
  if frontApp is in {"Terminal", "iTerm2", "WezTerm", "Alacritty", "kitty", "Ghostty"} then
    keystroke "/reload-plugins"
    key code 36
    return "typed"
  end if
end tell
return "skipped""#;
        if let Ok(o) = Command::new("osascript").arg("-e").arg(script).output() {
            return String::from_utf8_lossy(&o.stdout).trim() == "typed";
        }
    }
    false
}

fn open_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

fn open_revert(app: &AppHandle, session: &str) {
    let label = format!("revert-{}", &session[..session.len().min(8)]);
    if app.get_webview_window(&label).is_some() {
        return;
    }
    let url = format!("revert.html?session={session}");
    let _ = WebviewWindowBuilder::new(app, &label, WebviewUrl::App(url.into()))
        .title("세션 정리 — Skills Companion")
        .inner_size(480.0, 460.0)
        .build();
}

fn activate_flow(app: &AppHandle, plugin: &str, invoke_label: &str) {
    match run_brain(&["activate", "--plugin", plugin]) {
        Ok(_) => {
            let _ = app.clipboard().write_text("/reload-plugins".to_string());
            let typed = autotype_reload();
            let body = if typed {
                format!("{invoke_label} 활성화 — /reload-plugins 자동 입력됨")
            } else {
                format!("{invoke_label} 활성화 — /reload-plugins 를 세션에 붙여넣으세요 (복사됨)")
            };
            let _ = app.notification().builder()
                .title("플러그인 활성화됨").body(body).show();
        }
        Err(e) => {
            let _ = app.notification().builder()
                .title("활성화 실패").body(e).show();
        }
    }
}

fn handle_rec_click(app: &AppHandle, idx: usize) {
    let recs = app.state::<RecState>().0.lock().unwrap().clone();
    let Some(r) = recs.get(idx) else { return };
    let invoke = r["item"]["invoke"].as_str().unwrap_or("").to_string();
    if r["kind"] == "actionable" {
        if let Some(plugin) = r["item"]["plugin"].as_str() {
            activate_flow(app, plugin, &invoke);
        }
    } else {
        let _ = app.clipboard().write_text(invoke.clone());
        let _ = app.notification().builder()
            .title("복사됨").body(format!("{invoke} — 세션에 붙여넣으세요")).show();
    }
}

fn rebuild_tray(app: &AppHandle, recs: &[Value]) {
    *app.state::<RecState>().0.lock().unwrap() = recs.to_vec();
    let mut rec_items: Vec<MenuItem<tauri::Wry>> = vec![];
    for (i, r) in recs.iter().take(3).enumerate() {
        let mark = if r["kind"] == "actionable" { "⚡" } else { "💡" };
        let label = format!("{mark} {}", r["item"]["invoke"].as_str().unwrap_or("?"));
        if let Ok(mi) = MenuItem::with_id(app, format!("rec:{i}"), label, true,
                                          None::<&str>) {
            rec_items.push(mi);
        }
    }
    let open_i = MenuItem::with_id(app, "open", "Skills Companion 열기", true,
                                   None::<&str>).unwrap();
    let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>).unwrap();
    let sep = PredefinedMenuItem::separator(app).unwrap();
    let mut refs: Vec<&dyn tauri::menu::IsMenuItem<tauri::Wry>> = vec![];
    for mi in &rec_items {
        refs.push(mi);
    }
    refs.push(&sep);
    refs.push(&open_i);
    refs.push(&quit_i);
    if let Ok(menu) = Menu::with_items(app, &refs) {
        if let Some(tray) = app.tray_by_id("main") {
            let _ = tray.set_menu(Some(menu));
        }
    }
}

fn poll_once(app: &AppHandle, notified: &mut HashSet<String>) {
    // 1) explicit end signals, then leaks — both funnel into session-end
    let mut sids: Vec<String> = vec![];
    if let Ok(v) = run_brain(&["pending"]) {
        if let Some(arr) = v["sessions"].as_array() {
            sids.extend(arr.iter()
                .filter_map(|x| x["session_id"].as_str().map(String::from)));
        }
    }
    if let Ok(v) = run_brain(&["sweep"]) {
        if let Some(arr) = v["leaks"].as_array() {
            sids.extend(arr.iter().filter_map(|x| x.as_str().map(String::from)));
        }
    }
    for sid in sids {
        if let Ok(r) = run_brain(&["session-end", "--session", &sid]) {
            if r["action"] == "ask" {
                open_revert(app, &sid);
            }
        }
    }
    // 2) recommendations -> tray + opt-in notification
    let notifications_on = run_brain(&["config-get"])
        .map(|c| c["notifications_enabled"] == true)
        .unwrap_or(false);
    if let Ok(v) = run_brain(&["recommend", "--top", "3"]) {
        let recs = v["recommendations"].as_array().cloned().unwrap_or_default();
        rebuild_tray(app, &recs);
        if notifications_on {
            for r in &recs {
                if r["kind"] != "actionable" {
                    continue;
                }
                let key = r["item"]["plugin"].as_str().unwrap_or("").to_string();
                if !key.is_empty() && notified.insert(key.clone()) {
                    let _ = app.notification().builder()
                        .title("추천 플러그인")
                        .body(format!("{key} — 트레이에서 활성화할 수 있어요"))
                        .show();
                }
            }
        }
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_notification::init())
        .manage(RecState(Mutex::new(vec![])))
        .invoke_handler(tauri::generate_handler![
            brain, copy_text, notify, autotype_reload
        ])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            let open_i = MenuItem::with_id(app, "open", "Skills Companion 열기",
                                           true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&open_i, &sep, &quit_i])?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, e| {
                    let id = e.id().as_ref().to_string();
                    match id.as_str() {
                        "open" => open_main(app),
                        "quit" => app.exit(0),
                        _ => {
                            if let Some(i) = id.strip_prefix("rec:") {
                                if let Ok(idx) = i.parse::<usize>() {
                                    handle_rec_click(app, idx);
                                }
                            }
                        }
                    }
                })
                .build(app)?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut notified: HashSet<String> = HashSet::new();
                loop {
                    poll_once(&handle, &mut notified);
                    let secs = run_brain(&["config-get"])
                        .ok()
                        .and_then(|c| c["poll_seconds"].as_u64())
                        .unwrap_or(20);
                    std::thread::sleep(Duration::from_secs(secs));
                }
            });
            Ok(())
        })
        .on_window_event(|w, e| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = e {
                let _ = w.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Skills Companion");
}
```

- [ ] **Step 2: Build**

Run: `cd shell/src-tauri && cargo build 2>&1 | tail -20`
Expected: `Finished`. Fix any v2 API drift per compiler messages (menu/tray builder methods are the drift-prone area; the logic above is the contract).

- [ ] **Step 3: Manual verify with real data**

Run `cargo tauri dev`, then:
1. Tray menu shows up to 3 recommendation lines (this machine has real transcripts).
2. Create a fake signal: `python3 -c "import json,os,time; p=os.path.expanduser('~/.claude/skills-companion/state/session-ended'); os.makedirs(p,exist_ok=True); json.dump({'reason':'other','ts':time.time()}, open(p+'/testsess.json','w'))"` → within one poll the signal disappears (`action:"none"`, no ledger) — confirms the signal pipeline.
3. Quit dev.

- [ ] **Step 4: Commit**

```bash
git add shell
git commit -m "feat(shell): brain bridge, activation flow, dynamic tray recs, signal poll loop"
```

---

### Task 12: Main window UI — faceted catalog + recommendations + settings

**Files:**
- Modify: `shell/ui/index.html` (replace placeholder with full UI)

**Interfaces:**
- Consumes: `window.__TAURI__.core.invoke("brain", {args:[...]})`, `invoke("copy_text",{text})`, `invoke("autotype_reload")`, `invoke("notify",{title,body})`.
- Produces: single-page UI — group-by selector (카테고리/출처/상태/호출), state filters, search box, item cards with per-state action buttons (실행 명령 복사 / 활성화), 추천 rail (top-5 with reasons), 설정 section (default policy select, per-plugin policy table, notifications checkbox → `config-set`).

- [ ] **Step 1: Write the UI**

`shell/ui/index.html`:
```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Skills Companion</title>
<style>
:root{--bg:#f7f7f8;--fg:#1a1a1a;--card:#fff;--line:#e5e5e7;--muted:#6b7280;--accent:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e6e6e8;--card:#181b21;--line:#2a2e37;--muted:#9aa1ad;--accent:#5b9dff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:16px}
header{position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}
select,input[type=search]{padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
input[type=search]{flex:1;min-width:180px}
.rail{background:var(--card);border:1px solid var(--accent);border-radius:10px;padding:10px 12px;margin:12px 0}
.rail h3{margin:0 0 6px;font-size:13px;color:var(--accent)}
.rec{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:4px 0}
.rec .why{color:var(--muted);font-size:11.5px}
h2.grp{margin:18px 0 6px;font-size:13.5px;color:var(--muted);border-left:3px solid var(--accent);padding-left:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 11px}
.chead{display:flex;justify-content:space-between;gap:8px;align-items:center}
code.inv{color:var(--accent);font:12.5px ui-monospace,Menlo,monospace;font-weight:600;word-break:break-all}
.badge{font-size:10px;font-weight:700;color:#fff;border-radius:5px;padding:2px 6px;white-space:nowrap}
.desc{color:var(--muted);font-size:12px;margin-top:4px}
button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:7px;padding:4px 9px;cursor:pointer;font-size:12px}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
#settings{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:16px 0}
#settings table{width:100%;border-collapse:collapse;font-size:12.5px}
#settings td{padding:4px 6px;border-top:1px solid var(--line)}
.hidden{display:none!important}
</style></head><body><div class="wrap">
<header>
  <b>🗂️ Skills Companion</b>
  <div class="controls">
    <label>그룹: <select id="groupBy">
      <option value="category">카테고리</option><option value="source">출처</option>
      <option value="state">상태</option><option value="invocation">호출</option>
    </select></label>
    <label><input type="checkbox" id="fDisabled"> 비활성 플러그인만</label>
    <input id="q" type="search" placeholder="검색: 이름·설명·명령어">
    <button id="refresh">↻</button>
  </div>
</header>
<div class="rail"><h3>💡 이 세션 추천</h3><div id="recs">로딩…</div></div>
<div id="list">로딩…</div>
<div id="settings">
  <b>⚙️ 설정</b>
  <div style="margin:8px 0">
    기본 되돌림 정책:
    <select id="defPolicy">
      <option value="ask">물어보기 (ask)</option>
      <option value="auto-revert">자동 되돌림</option>
      <option value="keep">유지</option>
    </select>
    <label style="margin-left:12px"><input type="checkbox" id="notifs"> 추천 알림 켜기</label>
  </div>
  <table id="perPlugin"></table>
</div>
</div>
<script>
const inv = (cmd, args) => window.__TAURI__.core.invoke(cmd, args);
const brain = (...args) => inv("brain", { args });
const BADGE = { loaded:["로딩중","#d97706"], silenced:["수동 /","#2563eb"],
                enabled:["활성","#16a34a"], disabled:["비활성","#dc2626"] };
const GLBL = { source:{personal:"개인",plugin:"플러그인"},
               state:{loaded:"로딩중",silenced:"수동",enabled:"활성 플러그인",disabled:"비활성 플러그인"},
               invocation:{auto:"자동",manual:"수동",command:"명령"} };
let items = [], config = {};

async function activatePlugin(pluginKey, invoke) {
  const r = await brain("activate", "--plugin", pluginKey);
  if (!r.ok) { await inv("notify",{title:"활성화 실패",body:r.error||""}); return; }
  await inv("copy_text", { text: "/reload-plugins" });
  const typed = await inv("autotype_reload");
  await inv("notify", { title: "플러그인 활성화됨",
    body: typed ? invoke+" — /reload-plugins 자동 입력됨"
                : invoke+" — /reload-plugins 붙여넣으세요 (복사됨)" });
  load();
}
async function copyInvoke(invoke) {
  await inv("copy_text", { text: invoke });
  await inv("notify", { title: "복사됨", body: invoke + " — 세션에 붙여넣으세요" });
}

function card(i) {
  const [bl, bc] = BADGE[i.state] || ["?", "#888"];
  const act = (i.source === "plugin" && i.state === "disabled")
    ? `<button class="primary" data-act="on" data-plugin="${i.plugin}" data-invoke="${i.invoke}">활성화</button>`
    : `<button data-act="copy" data-invoke="${i.invoke}">복사</button>`;
  return `<div class="card" data-text="${(i.invoke+" "+i.name+" "+i.desc).toLowerCase()
           .replace(/"/g,"&quot;")}" data-state="${i.state}" data-source="${i.source}">
    <div class="chead"><code class="inv">${i.invoke}</code>
      <span><span class="badge" style="background:${bc}">${bl}</span> ${act}</span></div>
    <div class="desc">${(i.desc||"").slice(0,220)}</div></div>`;
}

function render() {
  const g = document.getElementById("groupBy").value;
  const q = document.getElementById("q").value.trim().toLowerCase();
  const onlyDis = document.getElementById("fDisabled").checked;
  const groups = {};
  for (const i of items) {
    if (onlyDis && !(i.source === "plugin" && i.state === "disabled")) continue;
    if (q && !(i.invoke+" "+i.name+" "+i.desc).toLowerCase().includes(q)) continue;
    const key = (GLBL[g] && GLBL[g][i[g]]) || i[g] || "기타";
    (groups[key] = groups[key] || []).push(i);
  }
  document.getElementById("list").innerHTML = Object.keys(groups).sort().map(k =>
    `<h2 class="grp">${k} <small>${groups[k].length}</small></h2>
     <div class="grid">${groups[k].map(card).join("")}</div>`).join("") || "결과 없음";
}

async function loadRecs() {
  const r = await brain("recommend", "--top", "5");
  const el = document.getElementById("recs");
  if (!r.recommendations.length) { el.textContent = "현재 세션과 매칭되는 추천 없음"; return; }
  el.innerHTML = r.recommendations.map(x => {
    const i = x.item;
    const btn = x.kind === "actionable"
      ? `<button class="primary" data-act="on" data-plugin="${i.plugin}" data-invoke="${i.invoke}">활성화</button>`
      : `<button data-act="copy" data-invoke="${i.invoke}">복사</button>`;
    return `<div class="rec"><span><code class="inv">${i.invoke}</code>
      <span class="why">← ${x.reasons.join(", ")}</span></span>${btn}</div>`;
  }).join("");
}

async function loadSettings() {
  config = await brain("config-get");
  document.getElementById("defPolicy").value = config.default_policy;
  document.getElementById("notifs").checked = !!config.notifications_enabled;
  const rows = Object.entries(config.per_plugin || {});
  document.getElementById("perPlugin").innerHTML = rows.length
    ? "<tr><td><b>플러그인별 정책</b></td><td></td><td></td></tr>" + rows.map(([p, pol]) =>
      `<tr><td><code>${p}</code></td><td>${pol}</td>
       <td><button data-act="unset" data-plugin="${p}">해제</button></td></tr>`).join("")
    : "";
}
async function saveConfig(patch) {
  config = await brain("config-set", "--json", JSON.stringify(patch));
  loadSettings();
}

async function load() { items = (await brain("scan")).items; render(); loadRecs(); loadSettings(); }

document.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.act === "on") activatePlugin(b.dataset.plugin, b.dataset.invoke);
  else if (b.dataset.act === "copy") copyInvoke(b.dataset.invoke);
  else if (b.dataset.act === "unset") {
    const pp = { ...config.per_plugin }; delete pp[b.dataset.plugin];
    saveConfig({ per_plugin: pp });
  } else if (b.id === "refresh") load();
});
document.getElementById("groupBy").addEventListener("change", render);
document.getElementById("fDisabled").addEventListener("change", render);
document.getElementById("q").addEventListener("input", render);
document.getElementById("defPolicy").addEventListener("change",
  e => saveConfig({ default_policy: e.target.value }));
document.getElementById("notifs").addEventListener("change",
  e => saveConfig({ notifications_enabled: e.target.checked }));
load();
</script></body></html>
```

- [ ] **Step 2: Manual verify**

`cargo tauri dev` → 열기 →
1. 카탈로그가 그룹·검색·"비활성 플러그인만" 필터로 동작.
2. 추천 rail에 현재 실세션 기반 항목 + reasons 표시.
3. 비활성 플러그인 카드의 [활성화] → 알림 뜨고 `~/.claude/settings.json`에서 해당 키만 true로 바뀜 + `.bak.*` 생성 확인 → **되돌리기**: `python3 -m skills_companion.cli apply-decisions --session <표시된 세션> --decisions '[{"plugin":"<키>","action":"revert"}]'` (PYTHONPATH=brain) 로 원복.
4. 설정 변경이 `config-get`에 반영.

- [ ] **Step 3: Commit**

```bash
git add shell/ui/index.html
git commit -m "feat(ui): faceted catalog, recommendation rail, activation flow, settings"
```

---

### Task 13: Revert dialog window

**Files:**
- Create: `shell/ui/revert.html`

**Interfaces:**
- Consumes: URL `?session=SID`; `brain("session-end","--session",SID)` (idempotent — returns remaining `ask` items), `brain("apply-decisions","--session",SID,"--decisions",JSON)`.
- Produces: per-plugin choice UI (되돌림/유지 + "이 플러그인은 항상 이렇게" remember checkbox), 일괄 버튼, closes window on completion.

- [ ] **Step 1: Write the dialog**

`shell/ui/revert.html`:
```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>세션 정리</title>
<style>
body{margin:0;padding:16px;background:#f7f7f8;color:#1a1a1a;
font:14px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",sans-serif}
@media(prefers-color-scheme:dark){body{background:#0f1115;color:#e6e6e8}}
.item{border:1px solid #8884;border-radius:9px;padding:9px 11px;margin:8px 0}
code{font:12.5px ui-monospace,Menlo,monospace;color:#2563eb;font-weight:600}
label{margin-right:10px}
.remember{font-size:12px;opacity:.8;display:block;margin-top:4px}
.actions{margin-top:14px;display:flex;gap:8px;justify-content:flex-end}
button{border:1px solid #8884;background:transparent;color:inherit;border-radius:8px;
padding:7px 14px;cursor:pointer}
button.primary{background:#2563eb;border-color:#2563eb;color:#fff}
</style></head><body>
<h3>세션이 끝났어요 — 이 세션에서 켠 플러그인을 어떻게 할까요?</h3>
<div id="items">로딩…</div>
<div class="actions">
  <button id="keepAll">모두 유지</button>
  <button id="revertAll" class="primary">모두 되돌림</button>
  <button id="apply">선택 적용</button>
</div>
<script>
const inv = (cmd, args) => window.__TAURI__.core.invoke(cmd, args);
const brain = (...args) => inv("brain", { args });
const sid = new URLSearchParams(location.search).get("session");
let plugins = [];

async function load() {
  const r = await brain("session-end", "--session", sid);
  plugins = r.ask || [];
  if (!plugins.length) { window.close(); return; }
  document.getElementById("items").innerHTML = plugins.map((p, i) => `
    <div class="item"><code>${p}</code><br>
      <label><input type="radio" name="a${i}" value="revert" checked> 되돌림(끄기)</label>
      <label><input type="radio" name="a${i}" value="keep"> 유지</label>
      <label class="remember"><input type="checkbox" id="rem${i}">
        이 플러그인은 앞으로 항상 이렇게 (기억)</label>
    </div>`).join("");
}
async function apply(force) {
  const decisions = plugins.map((p, i) => ({
    plugin: p,
    action: force || document.querySelector(`input[name=a${i}]:checked`).value,
    remember: document.getElementById(`rem${i}`).checked,
  }));
  await brain("apply-decisions", "--session", sid,
              "--decisions", JSON.stringify(decisions));
  window.close();
}
document.getElementById("apply").onclick = () => apply(null);
document.getElementById("revertAll").onclick = () => apply("revert");
document.getElementById("keepAll").onclick = () => apply("keep");
load();
</script></body></html>
```

- [ ] **Step 2: Manual verify (end-to-end ask flow)**

With `cargo tauri dev` running:
```bash
export PYTHONPATH=~/Desktop/Work_with_Claude_Mac/skills-companion/brain
python3 -m skills_companion.cli activate --plugin understand-anything@understand-anything --session FAKE_E2E
python3 - <<'PY'
import json, os, time
p = os.path.expanduser("~/.claude/skills-companion/state/session-ended")
os.makedirs(p, exist_ok=True)
json.dump({"reason": "other", "ts": time.time()}, open(p + "/FAKE_E2E.json", "w"))
PY
```
Expected: within one poll (≤20s) the revert dialog opens listing the plugin. Choose 되돌림 + 기억 → settings key back to `false`, `config.json` `per_plugin` gains `auto-revert`, signal file gone, dialog closes.

- [ ] **Step 3: Commit**

```bash
git add shell/ui/revert.html
git commit -m "feat(ui): session-end revert dialog with per-plugin remember"
```

---

# Phase 3 — Hooks & Migration

### Task 14: Hook script + installer (tested)

**Files:**
- Create: `hooks/session-end-signal.sh`, `brain/skills_companion/installer.py`, `brain/tests/test_installer.py`
- Modify: `brain/skills_companion/cli.py` (add `install-hooks` / `uninstall-hooks`)

**Interfaces:**
- Consumes: `paths`, `stores`.
- Produces:
  - `installer.add_session_end_hook(settings: dict, script_path: str) -> dict` (idempotent append of `{"hooks":[{"type":"command","command":"bash <script_path>"}]}` to `hooks.SessionEnd`),
  - `installer.remove_cheatsheet_hook(settings: dict) -> dict` (drops SessionStart entries whose command contains `skills-cheatsheet/open.sh`),
  - `installer.remove_session_end_hook(settings: dict, script_path: str) -> dict`,
  - `installer.install_hooks(script_path) / uninstall_hooks(script_path)` → applied to real settings with backup,
  - CLI: `install-hooks --script PATH`, `uninstall-hooks --script PATH`.
  - Hook script: reads hook JSON from stdin, writes `state/session-ended/<sid>.json`, **zero stdout**, `exit 0`.

- [ ] **Step 1: Write the failing test**

`brain/tests/test_installer.py`:
```python
import json
import os
import subprocess
from pathlib import Path

from skills_companion import installer, paths, stores

HOOK = "/repo/hooks/session-end-signal.sh"


def test_add_hook_idempotent():
    s = {}
    installer.add_session_end_hook(s, HOOK)
    installer.add_session_end_hook(s, HOOK)
    assert len(s["hooks"]["SessionEnd"]) == 1
    assert s["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"bash {HOOK}"


def test_remove_cheatsheet_hook_only():
    s = {"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "korean-law-key-sync.py"}]},
        {"matcher": "startup",
         "hooks": [{"type": "command",
                    "command": "bash /Users/x/.claude/skills-cheatsheet/open.sh"}]},
    ]}}
    installer.remove_cheatsheet_hook(s)
    entries = s["hooks"]["SessionStart"]
    assert len(entries) == 1
    assert "korean-law" in entries[0]["hooks"][0]["command"]


def test_install_hooks_applies_with_backup(claude_home):
    r = installer.install_hooks(HOOK)
    assert r["ok"]
    s = stores.read_json(paths.settings_path(), {})
    assert s["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == f"bash {HOOK}"
    assert list(claude_home.glob("settings.json.bak.*"))
    r2 = installer.uninstall_hooks(HOOK)
    assert r2["ok"]
    s2 = stores.read_json(paths.settings_path(), {})
    assert s2["hooks"]["SessionEnd"] == []


def test_hook_script_writes_signal(claude_home):
    script = Path(__file__).resolve().parents[2] / "hooks" / "session-end-signal.sh"
    payload = json.dumps({"session_id": "HOOKSESS", "reason": "prompt_input_exit",
                          "hook_event_name": "SessionEnd"})
    env = dict(os.environ, SKILLS_COMPANION_CLAUDE_HOME=str(claude_home))
    p = subprocess.run(["bash", str(script)], input=payload, text=True,
                       capture_output=True, env=env)
    assert p.returncode == 0
    assert p.stdout == ""                                  # zero stdout!
    sig = claude_home / "skills-companion" / "state" / "session-ended" / "HOOKSESS.json"
    assert sig.exists()
    assert json.loads(sig.read_text())["reason"] == "prompt_input_exit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_installer.py -q`
Expected: FAIL — `No module named 'skills_companion.installer'`

- [ ] **Step 3: Write implementations**

`hooks/session-end-signal.sh`:
```bash
#!/bin/bash
# SessionEnd hook for Skills Companion: drop a signal file. MUST print nothing
# to stdout (a hook's stdout would be injected into model context) and exit 0.
INPUT="$(cat)"
HOOK_INPUT="$INPUT" /usr/bin/python3 -c '
import json, os, time
try:
    d = json.loads(os.environ.get("HOOK_INPUT") or "{}")
except Exception:
    d = {}
sid = d.get("session_id") or "unknown"
root = os.environ.get("SKILLS_COMPANION_CLAUDE_HOME") or os.path.expanduser("~/.claude")
p = os.path.join(root, "skills-companion", "state", "session-ended")
os.makedirs(p, exist_ok=True)
with open(os.path.join(p, sid + ".json"), "w") as f:
    json.dump({"reason": d.get("reason", "other"), "ts": time.time()}, f)
' >/dev/null 2>&1
exit 0
```
Then: `chmod +x hooks/session-end-signal.sh`

`brain/skills_companion/installer.py`:
```python
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
```

Add to `cli.py` — in the subparser block:
```python
    p = sub.add_parser("install-hooks")
    p.add_argument("--script", required=True)
    p = sub.add_parser("uninstall-hooks")
    p.add_argument("--script", required=True)
```
and in the dispatch chain:
```python
    elif args.cmd == "install-hooks":
        from . import installer
        out = installer.install_hooks(args.script)
    elif args.cmd == "uninstall-hooks":
        from . import installer
        out = installer.uninstall_hooks(args.script)
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m pytest -q`
Expected: `37 passed` (Phase-1 33 + installer 4)

- [ ] **Step 5: Commit**

```bash
git add brain hooks
git commit -m "feat(hooks): SessionEnd signal script + idempotent settings installer"
```

---

### Task 15: Migration, LaunchAgent, smoke test

**Files:**
- Create: `installer/com.earendel.skills-companion.plist`
- Modify: `~/.claude/skills/myskills/SKILL.md` (repoint), `~/.claude/settings.json` (via installer CLI), archive `~/.claude/skills-cheatsheet.html`

**Interfaces:**
- Consumes: Task 14 CLI; built app bundle from `cargo tauri build`.
- Produces: installed resident app; old cheat-sheet system retired (backed up, reversible).

- [ ] **Step 1: Release build + install app**

```bash
cd ~/Desktop/Work_with_Claude_Mac/skills-companion/shell/src-tauri
cargo tauri build 2>&1 | tail -5
cp -R "target/release/bundle/macos/Skills Companion.app" /Applications/
open -a "Skills Companion" && sleep 3 && pgrep -f skills-companion
```
Expected: build succeeds; tray icon appears; pgrep prints a pid.

- [ ] **Step 2: Install hooks (adds SessionEnd signal, removes HTML-open hook)**

```bash
export PYTHONPATH=~/Desktop/Work_with_Claude_Mac/skills-companion/brain
python3 -m skills_companion.cli install-hooks \
  --script ~/Desktop/Work_with_Claude_Mac/skills-companion/hooks/session-end-signal.sh
python3 - <<'PY'
import json, os
s = json.load(open(os.path.expanduser("~/.claude/settings.json")))
assert any("session-end-signal.sh" in h["command"]
           for e in s["hooks"]["SessionEnd"] for h in e["hooks"])
assert not any("skills-cheatsheet" in h.get("command", "")
               for e in s["hooks"].get("SessionStart", []) for h in e.get("hooks", []))
print("hooks OK")
PY
```
Expected: `{"ok": true}` then `hooks OK`.

- [ ] **Step 3: Repoint /myskills + archive static cheat sheet**

Replace `~/.claude/skills/myskills/SKILL.md` content with:
```markdown
---
name: myskills
description: Open the Skills Companion app window (tray app with the full skills/plugin catalog, recommendations, and plugin activation). Use when the user types /myskills or asks what skills/commands are available.
---

# /myskills

Open the Skills Companion window:

```bash
open -a "Skills Companion"
```

Do not print the catalog into the conversation — the reference lives in the app.
Confirm in one short line that the app was opened.
```

Archive the old HTML (reversible):
```bash
mkdir -p ~/.claude/backups
mv ~/.claude/skills-cheatsheet.html ~/.claude/backups/skills-cheatsheet.html.retired-$(date +%Y%m%d) 2>/dev/null
ls ~/.claude/backups | grep cheatsheet
```
(Leave `~/.claude/skills-cheatsheet/` scripts in place — harmless, and `open.sh` is no longer referenced by any hook.)

- [ ] **Step 4: LaunchAgent (auto-start at login)**

`installer/com.earendel.skills-companion.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.earendel.skills-companion</string>
  <key>ProgramArguments</key>
  <array><string>/Applications/Skills Companion.app/Contents/MacOS/skills-companion</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict></plist>
```
```bash
cp installer/com.earendel.skills-companion.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.earendel.skills-companion.plist
launchctl list | grep skills-companion
```
Expected: job listed.

- [ ] **Step 5: End-to-end smoke test (real session)**

1. Open a terminal, start `claude` in any directory, chat one line mentioning e.g. "코드베이스 아키텍처 분석" → within ~20s tray shows `⚡ /understand-anything:understand`.
2. Click it → notification; `enabledPlugins` flipped true; `/reload-plugins` on clipboard (or auto-typed if terminal frontmost).
3. `/exit` the session → signal file appears → revert dialog opens → choose 되돌림 → key back to false.
4. `kill -9` test: repeat activation in a new session, then close the terminal window (no /exit) → within poll+1800s idle the leak sweep raises the dialog. For the smoke test, temporarily lower the threshold: `python3 -m skills_companion.cli config-set --json '{"poll_seconds": 10}'` and verify sweep logic with a fake old-mtime transcript instead (as in Task 8's test) if waiting is impractical.
5. `/myskills` in a Claude session → app window focuses.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/Work_with_Claude_Mac/skills-companion
git add installer
git commit -m "feat(install): LaunchAgent, /myskills repoint, cheatsheet retirement"
```

---

## Self-Review Notes (performed)

- **Spec coverage:** §5 architecture→T10–11; §6 components 1–8→T4,T6,T5/T11,T7,T8,T12–13,T14,T2; §8 engine→T6; §9 flows→T7/T11 (activate), T8/T13 (end/ask), T8/T11 (sweep); §10 edge cases→tests in T7 (unknown/already-enabled/unrelated keys), T8 (guard/idempotent/no-entries); §12 migration→T15; §13 packaging→T15. Windows packaging, agents, un-silencing: out of scope per spec §4.
- **Type consistency:** ledger/config/CatalogItem/Recommendation shapes identical across T2/T4/T6/T9/T12; plugin key format `name@marketplace` everywhere; CLI verbs match shell callers (T11–13 call only verbs defined in T9/T14).
- **Known drift risk (explicit):** Tauri v2 Rust API names in T10–11 may need compiler-guided renames; the JSON contracts with the brain are the stable interface.
