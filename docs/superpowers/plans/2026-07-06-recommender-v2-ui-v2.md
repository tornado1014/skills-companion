# 추천 로직 v2 + 카탈로그 UI v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 추천 근거를 인간 가독 문자열로 바꾸는 하이브리드 추천 로직 v2(조사 스트립 토큰화·프로젝트 신호·활성화 이력·연속 블렌딩·haiku 리파인)와, 사이드바+히어로 구조의 모던 프로덕티비티 스타일 카탈로그 UI v2를 구현하고 실환경에 재배포한다.

**Architecture:** brain(Python stdlib)은 신호 수집 → 토큰화 → 로컬 블렌딩 스코어 → (조건부) LLM 리파인 병합의 파이프라인이며 recommend 출력 스키마(`reasons: list[str]`)는 하위호환. shell은 `index.html` 단일 파일 UI를 사이드바+검색+히어로+리스트 행 구조로 재작성하고 `revert.html`/`wizard.html`은 스타일 토큰만 교체. `main.rs`·tauri.conf.json·CSP·창 크기는 무변경.

**Tech Stack:** Python 3 (stdlib only, pytest), Tauri 2 (Rust shell 무변경), vanilla HTML/CSS/JS (외부 리소스 0).

**스펙:** `docs/superpowers/specs/2026-07-06-recommender-v2-ui-v2-design.md` (승인 완료)
**승인 목업:** `.superpowers/brainstorm/2649-1783305889/content/catalog-combined.html`(구조), `visual-style.html`의 스타일 B(모던 프로덕티비티)

## Global Constraints

- **C9/C12 절대 규칙**: `~/.claude.json`(직접) · `installed_plugins.json` · `CLAUDE.md` · `MEMORY.md` · `korean-law-key-sync.py` 훅은 **절대 쓰지 않는다**. `~/.claude/settings.json` 쓰기는 앱 CLI(atomic + 백업) 경유만. 서브에이전트에게도 전파.
- brain은 **stdlib 전용** (외부 의존성 도입 금지).
- UI는 **외부 리소스 0** (CSP — 폰트·스크립트·이미지 전부 로컬/시스템).
- `main.rs`·트레이 메뉴·brain CLI 스키마·tauri.conf.json·창 크기(980×720) 무변경.
- recommend 출력 스키마 하위호환: `reasons`는 계속 `list[str]` (내용만 인간 가독 문자열로).
- 테스트: `cd brain && python3 -m pytest -q` — 기존 55개 회귀 금지. **의도적 수정이 허용된 기존 테스트는 아래 "허용된 기존 테스트 수정" 절의 1건뿐.**
- Rust 빌드 전 `source "$HOME/.cargo/env"`. `cargo tauri build`/`dev`는 **run_in_background**.
- **cwd 함정**: cwd가 있는 셸에서 파일을 만들면 OMC 훅이 그 cwd에 `.omc/`를 만든다. `shell/src-tauri/capabilities/` 안에 `.omc`가 생기면 빌드가 깨진다 — 파일 생성은 항상 절대경로로, 작업 후 `ls shell/src-tauri/capabilities/` 확인.
- `newest_session()` 오귀속 한계는 스펙 1.2가 수용 — 고치려 들지 말 것.

## 허용된 기존 테스트 수정 (스펙이 의도적으로 바꾼 동작)

스펙 1.5/1.7이 `reasons`를 "매칭 토큰 나열"에서 "인간 가독 문자열"로 바꾸므로, 아래 **1건만** 수정한다. 그 외 기존 테스트는 한 글자도 바꾸지 않는다.

- `brain/tests/test_recommender.py::test_actionable_recommendation_for_disabled_plugin`의 마지막 줄:
  - 기존: `assert "codebase" in top["reasons"] or "knowledge" in top["reasons"]`
  - 수정: `assert any(("codebase" in r) or ("knowledge" in r) for r in top["reasons"])`

## File Structure

| 파일 | 역할 |
|---|---|
| `brain/skills_companion/transcripts.py` (수정) | 신호 수집: cwd·user_texts·user_msg_count 추가, `session_path()` 헬퍼 |
| `brain/skills_companion/recommender.py` (수정) | `tokenize_ex()`(조사 스트립·bigram 불용어·visible 집합), `project_tokens()`(프로젝트 코퍼스), `recommend()` 블렌딩 v2 |
| `brain/skills_companion/stores.py` (수정) | `history_add()`/`history_for()` — `state/activation-history.json` |
| `brain/skills_companion/paths.py` (수정) | `activation_history_path()` |
| `brain/skills_companion/activation.py` (수정) | activate 성공 시 이력 기록 |
| `brain/skills_companion/llm_refine.py` (신규) | haiku 리파인: 트리거·캐시·검증·병합·폴백 |
| `brain/skills_companion/cli.py` (수정) | `_cmd_recommend` v2 배선, activate 분기의 cwd 연결 |
| `brain/tests/test_llm_refine.py` (신규) | mock runner 테스트 |
| `brain/tests/test_{transcripts,recommender,stores,activation,cli}.py` (수정) | 신규 동작 테스트 추가 |
| `shell/ui/index.html` (재작성) | 사이드바+검색(⌘K)+히어로+리스트 행, 스타일 토큰 v2 |
| `shell/ui/revert.html`, `shell/ui/wizard.html` (수정) | `<style>` 블록만 토큰 교체, 로직 무변경 |

**모든 pytest 실행은 `cd /Users/earendel/Desktop/Work_with_Claude_Mac/skills-companion/brain && python3 -m pytest -q [경로]` 형태로 실행한다** (이하 "Run:"에는 pytest 인자만 표기).

---

### Task 1: `extract_signals` v2 — cwd·user_texts·user_msg_count

**Files:**
- Modify: `brain/skills_companion/transcripts.py:22-51` (`extract_signals`)
- Test: `brain/tests/test_transcripts.py`

**Interfaces:**
- Consumes: 없음 (기존 transcript JSONL 형식)
- Produces: `extract_signals(path, last_n=30, tail_bytes=400_000) -> dict` — 키 `texts: list[str]`, `tools: list[str]`, `cwd: str`, `user_texts: list[str]`, `user_msg_count: int`. 오류 시에도 5키 전부 포함한 기본값 반환. Task 5·6·7이 새 키를 소비.

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_transcripts.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_transcripts.py -v`
Expected: 신규 3개 FAIL (KeyError `'cwd'` 등), 기존 4개 PASS

- [ ] **Step 3: 구현** — `transcripts.py`의 `extract_signals` 전체를 다음으로 교체:

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_transcripts.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/transcripts.py brain/tests/test_transcripts.py
git commit -m "feat(brain): extract_signals v2 - cwd, user_texts, user_msg_count"
```

---

### Task 2: `tokenize_ex` — 조사 스트립·bigram 불용어·visible 집합

**Files:**
- Modify: `brain/skills_companion/recommender.py:14-20` (`tokenize`)
- Test: `brain/tests/test_recommender.py`

**Interfaces:**
- Produces: `tokenize_ex(text) -> {"tokens": list[str], "visible": set[str]}`. `tokens`에는 영어 토큰 + 한글 온전 토큰(조사 스트립 후 어간, **2회 계상=2배 가중**) + 불용어 제외 bigram. `visible`에는 영어 토큰과 온전 토큰만 (bigram 절대 불포함) — reasons 노출 후보. `tokenize(text) -> list[str]`는 `tokenize_ex(text)["tokens"]` 래퍼로 하위호환 유지. Task 4·5가 `tokenize_ex`를 소비.

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_recommender.py` 끝에 추가:

```python
def test_tokenize_ex_strips_josa_and_weights_full_tokens():
    tx = recommender.tokenize_ex("보정서를 검토합니다")
    assert tx["tokens"].count("보정서") == 2      # 조사 스트립 + 2배 가중
    assert "보정서" in tx["visible"]
    assert "니다" not in tx["tokens"]             # bigram 불용어
    assert "합니" not in tx["tokens"]


def test_tokenize_ex_whole_word_without_josa_is_full_token():
    tx = recommender.tokenize_ex("특허번역")
    assert tx["tokens"].count("특허번역") == 2
    assert "특허" in tx["tokens"]                 # bigram은 점수용으로 유지
    assert "특허번역" in tx["visible"]
    assert "허번" not in tx["visible"]            # bigram은 visible 불포함


def test_tokenize_backcompat_returns_flat_list():
    toks = recommender.tokenize("Analyze 특허번역")
    assert "analyze" in toks and "특허" in toks and "특허번역" in toks
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_recommender.py -v`
Expected: 신규 3개 FAIL (`AttributeError: ... tokenize_ex`), 기존 4개 PASS

- [ ] **Step 3: 구현** — `recommender.py`의 `tokenize`를 다음으로 교체 (STOPWORDS 아래):

```python
# 한글 어절 끝 조사 — 긴 것 먼저 매칭
_JOSA = sorted([
    "에서부터", "으로부터", "으로서", "으로써", "에게서", "까지", "부터",
    "처럼", "보다", "에서", "에게", "한테", "으로", "이나", "이라",
    "라도", "마저", "조차", "은", "는", "이", "가", "을", "를",
    "에", "의", "도", "만", "와", "과", "로",
], key=len, reverse=True)

# 어미·기능어 bigram 차단 세트 (스펙 1.4 초기 목록, 구현 중 확장 가능)
BIGRAM_STOP = {
    "니다", "습니", "세요", "하세", "어요", "예요", "해줘", "해서", "하는",
    "있는", "없는", "그리", "리고", "하지", "지만", "에서", "으로", "한다",
    "했다", "합니", "입니", "것을", "것이", "그것", "저것",
}


def _strip_josa(word):
    for j in _JOSA:
        if word.endswith(j) and len(word) - len(j) >= 2:
            return word[: -len(j)]
    return word


def tokenize_ex(text):
    text = text.lower()
    en = [t for t in re.findall(r"[a-z][a-z0-9_-]{1,}", text) if t not in STOPWORDS]
    tokens = list(en)
    visible = set(en)
    for chunk in re.findall(r"[가-힣]{2,}", text):
        stem = _strip_josa(chunk)
        if len(stem) >= 2:
            tokens.extend((stem, stem))          # 온전 토큰 2배 가중
            visible.add(stem)
        tokens.extend(b for b in (chunk[i:i + 2] for i in range(len(chunk) - 1))
                      if b not in BIGRAM_STOP)
    return {"tokens": tokens, "visible": visible}


def tokenize(text):
    return tokenize_ex(text)["tokens"]
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_recommender.py -v`
Expected: 전부 PASS (기존 `test_tokenize_english_and_korean_bigrams` 포함 — 특허/허번/번역은 불용어가 아니므로 유지됨)

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/recommender.py brain/tests/test_recommender.py
git commit -m "feat(brain): tokenize v2 - josa strip, full-token weighting, bigram stoplist"
```

---

### Task 3: 활성화 이력 스토어 + activate 연결

**Files:**
- Modify: `brain/skills_companion/paths.py` (함수 1개 추가)
- Modify: `brain/skills_companion/stores.py` (함수 2개 추가)
- Modify: `brain/skills_companion/activation.py:15-30` (`activate`)
- Modify: `brain/skills_companion/transcripts.py` (`session_path` 추가)
- Modify: `brain/skills_companion/cli.py:73-79` (activate 분기)
- Test: `brain/tests/test_stores.py`, `brain/tests/test_activation.py`, `brain/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1의 `extract_signals`(cwd 추출)
- Produces:
  - `paths.activation_history_path() -> Path` = `state_dir()/"activation-history.json"`
  - `stores.history_add(cwd: str, plugin_key: str) -> dict` — `{cwd: {plugin_key: {"count": int, "last_ts": float}}}` 누적 (cwd가 빈 문자열이면 no-op으로 현재 이력 반환)
  - `stores.history_for(cwd: str) -> dict[str, int]` — plugin_key → count (Task 5·7 소비)
  - `transcripts.session_path(session_id: str) -> str | None`
  - `activation.activate(...)`: 성공적으로 활성이 반영되고 `cwd`가 비어있지 않으면 `history_add` 호출

- [ ] **Step 1: 실패하는 테스트 작성**

`brain/tests/test_stores.py` 끝에 추가 (파일 상단에 `UA = "understand-anything@understand-anything"`가 없으면 함께 추가):

```python
def test_history_add_and_for(claude_home):
    UA = "understand-anything@understand-anything"
    stores.history_add("/w", UA)
    stores.history_add("/w", UA)
    stores.history_add("/other", UA)
    assert stores.history_for("/w") == {UA: 2}
    assert stores.history_for("/none") == {}
    raw = stores.read_json(paths.activation_history_path(), {})
    assert raw["/w"][UA]["count"] == 2 and raw["/w"][UA]["last_ts"] > 0


def test_history_add_empty_cwd_is_noop(claude_home):
    stores.history_add("", "x@y")
    assert stores.read_json(paths.activation_history_path(), {}) == {}
```

(주의: `test_stores.py`가 `paths`를 import하지 않으면 import 줄에 추가.)

`brain/tests/test_activation.py` 끝에 추가:

```python
def test_activate_records_history(claude_home):
    activation.activate(UA, session_id="S1", cwd="/w")
    assert stores.history_for("/w") == {UA: 1}
    # 앱이 켠 플러그인을 다른 세션이 또 쓰면 그 cwd에도 누적
    activation.activate(UA, session_id="S2", cwd="/w2")
    assert stores.history_for("/w2") == {UA: 1}


def test_activate_without_cwd_records_nothing(claude_home):
    activation.activate(UA, session_id="S1")
    assert stores.read_json(paths.activation_history_path(), {}) == {}
```

`brain/tests/test_cli.py` 끝에 추가:

```python
def test_cli_activate_records_history_with_cwd(claude_home, write_transcript, capsys):
    from skills_companion import stores
    write_transcript("S9", ["work"], cwd="/tmp/work")
    _run(capsys, ["activate", "--plugin", UA, "--session", "S9"])
    assert stores.history_for("/tmp/work") == {UA: 1}
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_stores.py tests/test_activation.py tests/test_cli.py -v`
Expected: 신규 5개 FAIL (`AttributeError: ... history_add` 등), 기존 전부 PASS

- [ ] **Step 3: 구현**

`paths.py` 끝에 추가:

```python
def activation_history_path() -> Path:
    return state_dir() / "activation-history.json"
```

`stores.py` 끝에 추가:

```python
def history_add(cwd, plugin_key):
    hist = read_json(paths.activation_history_path(), {})
    if not cwd:
        return hist
    entry = hist.setdefault(cwd, {}).setdefault(
        plugin_key, {"count": 0, "last_ts": 0.0})
    entry["count"] += 1
    entry["last_ts"] = time.time()
    atomic_write_json(paths.activation_history_path(), hist)
    return hist


def history_for(cwd):
    hist = read_json(paths.activation_history_path(), {})
    return {k: v.get("count", 0) for k, v in hist.get(cwd or "", {}).items()}
```

`activation.py`의 `activate`를 다음으로 교체:

```python
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
```

`transcripts.py` 끝에 추가:

```python
def session_path(session_id):
    for f in paths.projects_dir().glob(f"*/{session_id}.jsonl"):
        return str(f)
    return None
```

`cli.py`의 activate 분기(현행 73-79행)를 다음으로 교체:

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_stores.py tests/test_activation.py tests/test_cli.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/paths.py brain/skills_companion/stores.py \
  brain/skills_companion/activation.py brain/skills_companion/transcripts.py \
  brain/skills_companion/cli.py brain/tests/test_stores.py \
  brain/tests/test_activation.py brain/tests/test_cli.py
git commit -m "feat(brain): activation history store keyed by cwd"
```

---

### Task 4: 프로젝트 코퍼스 — `project_tokens`

**Files:**
- Modify: `brain/skills_companion/recommender.py` (함수 추가, `import json, os` 추가)
- Test: `brain/tests/test_recommender.py`

**Interfaces:**
- Consumes: Task 2 `tokenize_ex`
- Produces: `project_tokens(cwd: str, head_bytes=4096) -> {"tokens": list[str], "visible": set[str]}` — cwd의 `CLAUDE.md`/`README.md`/`pyproject.toml` 앞 4KB 원문, `package.json`의 name/description/dependencies 키 이름, `Cargo.toml`의 name/description 줄을 합쳐 `tokenize_ex`한 결과. cwd가 빈 문자열이거나 파일이 없으면 빈 결과. 캐시 없음. Task 5·7 소비.

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_recommender.py` 끝에 추가 (파일 상단에 `import json` 추가):

```python
def test_project_tokens_reads_known_files(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("특허 보정서 자동화 프로젝트", encoding="utf-8")
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "pdf-merge", "description": "merge pdf files",
        "dependencies": {"pdf-lib": "1.0"}}), encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text(
        'name = "tauri-shell"\nversion = "1"\n', encoding="utf-8")
    tx = recommender.project_tokens(str(tmp_path))
    assert "보정서" in tx["visible"]
    assert "pdf-merge" in tx["tokens"]
    assert "pdf-lib" in tx["tokens"]
    assert "tauri-shell" in tx["tokens"]


def test_project_tokens_empty_or_missing_cwd():
    assert recommender.project_tokens("") == {"tokens": [], "visible": set()}
    assert recommender.project_tokens("/nonexistent-xyz-123")["tokens"] == []
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_recommender.py -v`
Expected: 신규 2개 FAIL (`AttributeError: ... project_tokens`)

- [ ] **Step 3: 구현** — `recommender.py` 상단 import에 `json`, `os` 추가 후 `tokenize` 아래에 추가:

```python
_PROJECT_TEXT_FILES = ("CLAUDE.md", "README.md", "pyproject.toml")


def project_tokens(cwd, head_bytes=4096):
    if not cwd:
        return {"tokens": [], "visible": set()}
    parts = []
    for name in _PROJECT_TEXT_FILES:
        try:
            with open(os.path.join(cwd, name), encoding="utf-8",
                      errors="ignore") as f:
                parts.append(f.read(head_bytes))
        except OSError:
            continue
    try:
        with open(os.path.join(cwd, "package.json"), encoding="utf-8",
                  errors="ignore") as f:
            pkg = json.loads(f.read(head_bytes))
        parts.append(str(pkg.get("name", "")))
        parts.append(str(pkg.get("description", "")))
        parts.extend((pkg.get("dependencies") or {}).keys())
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    try:
        with open(os.path.join(cwd, "Cargo.toml"), encoding="utf-8",
                  errors="ignore") as f:
            for line in f.read(head_bytes).splitlines():
                if line.strip().startswith(("name", "description")):
                    parts.append(line)
    except OSError:
        pass
    return tokenize_ex(" ".join(p for p in parts if p))
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_recommender.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/recommender.py brain/tests/test_recommender.py
git commit -m "feat(brain): project corpus tokens from cwd files"
```

---

### Task 5: `recommend` 연속 블렌딩 + 인간 가독 reasons

**Files:**
- Modify: `brain/skills_companion/recommender.py:23-55` (`_corpus`, `recommend`)
- Test: `brain/tests/test_recommender.py` (신규 추가 + 허용된 1건 수정)

**Interfaces:**
- Consumes: Task 2 `tokenize_ex`, Task 3 `history_for` 결과 형태, Task 4 `project_tokens` 결과 형태
- Produces: `recommend(items, signals, top_k=5, min_matches=2, history=None, project_tokens=None) -> list[rec]`
  - `history: dict[plugin_key, count] | None`, `project_tokens: {"tokens", "visible"} | None`
  - `signals["user_msg_count"]`가 **없으면 w_conv=1.0** (기존 순수 대화 동작과 하위호환), 있으면 `w_conv = min(1.0, umc/8)`, `w_proj = 1 - w_conv`
  - `score = w_conv*conv_score + w_proj*(proj_score + hist_boost)`, `hist_boost = log(1+count)*2.0`
  - `min_matches` 게이트는 conv에만, proj는 매칭 1개부터, 이력만으로도(매칭 0) 추천 가능
  - BOOST_DISABLED(1.5)는 합산 점수에 적용, kind 판정 기존 유지
  - `reasons: list[str]` — `"이 프로젝트에서 N회 사용"` / `"프로젝트: a, b"` / `"대화: a, b"` (visible 토큰 상위 ≤3). Task 6·7·UI 소비.

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_recommender.py` 끝에 추가:

```python
UA = "understand-anything@understand-anything"
KL = "korean-law@korean-law-marketplace"


def test_recommend_blending_shifts_with_msg_count(claude_home):
    items = scanner.scan()["items"]
    hist = {KL: 3}
    proj = recommender.tokenize_ex("법령 판례 리서치 legal research")
    conv = {"texts": ["analyze codebase architecture",
                      "knowledge graph of components"], "tools": []}

    # 초반(umc=0): w_conv=0 → 이력+프로젝트만. korean-law가 뜨고 understand는 없음
    early = recommender.recommend(items, dict(conv, user_msg_count=0),
                                  history=hist, project_tokens=proj)
    assert early and early[0]["item"]["plugin"] == KL
    assert any("3회 사용" in r for r in early[0]["reasons"])
    assert all(r["item"]["invoke"] != "/understand-anything:understand"
               for r in early)

    # 중반(umc=4): 혼합 — 둘 다 등장
    mid = recommender.recommend(items, dict(conv, user_msg_count=4),
                                history=hist, project_tokens=proj)
    invokes = [r["item"]["invoke"] for r in mid]
    assert "/understand-anything:understand" in invokes
    assert any(r["item"]["plugin"] == KL for r in mid)

    # 후반(umc=20): w_proj=0 → 대화 신호가 지배
    late = recommender.recommend(items, dict(conv, user_msg_count=20),
                                 history=hist, project_tokens=proj)
    assert late[0]["item"]["invoke"] == "/understand-anything:understand"
    assert all(r["item"]["plugin"] != KL for r in late)


def test_recommend_history_only_item_needs_no_matches(claude_home):
    items = scanner.scan()["items"]
    recs = recommender.recommend(items, {"texts": [], "tools": [],
                                         "user_msg_count": 0},
                                 history={UA: 2})
    assert recs and recs[0]["item"]["plugin"] == UA
    assert recs[0]["reasons"] == ["이 프로젝트에서 2회 사용"]


def test_recommend_reasons_are_human_strings_no_bigram(claude_home):
    items = scanner.scan()["items"]
    signals = {"texts": ["특허번역 명세서 작업을 계속합니다"], "tools": []}
    recs = recommender.recommend(items, signals)
    kipo = next(r for r in recs if r["item"]["invoke"] == "/patent-en-ko-kipo")
    assert any(r.startswith("대화: ") for r in kipo["reasons"])
    joined = " ".join(kipo["reasons"])
    assert "니다" not in joined and "허번" not in joined
```

동시에 **허용된 기존 테스트 수정 1건** 적용 — `test_actionable_recommendation_for_disabled_plugin`의 마지막 줄:

```python
    assert any(("codebase" in r) or ("knowledge" in r) for r in top["reasons"])
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_recommender.py -v`
Expected: 신규 3개 FAIL (`TypeError: recommend() got an unexpected keyword argument 'history'` 등)

- [ ] **Step 3: 구현** — `recommender.py`의 `_corpus`와 `recommend`를 다음으로 교체:

```python
H_HISTORY = 2.0


def _corpus_ex(item):
    tx = tokenize_ex(
        f"{item['invoke']} {item['name']} {item['desc']} {item['category']}")
    return {"set": set(tx["tokens"]), "visible": tx["visible"]}


def _sub_score(query, corpus_set, df, n, min_matches):
    matched = [t for t in query if t in corpus_set]
    if len(matched) < min_matches:
        return 0.0, []
    score = sum(query[t] * math.log(1 + n / df[t]) for t in matched)
    score /= math.sqrt(len(corpus_set) or 1)
    return score, matched


def _visible_top(matched, visible, query, k=3):
    vs = [t for t in matched if t in visible]
    return sorted(vs, key=lambda t: -query[t])[:k]


def recommend(items, signals, top_k=5, min_matches=2,
              history=None, project_tokens=None):
    history = history or {}
    proj = project_tokens or {"tokens": [], "visible": set()}
    conv = tokenize_ex(" ".join(
        signals.get("texts", []) + signals.get("tools", [])))
    conv_q, proj_q = Counter(conv["tokens"]), Counter(proj["tokens"])
    if not conv_q and not proj_q and not history:
        return []
    umc = signals.get("user_msg_count")
    w_conv = 1.0 if umc is None else min(1.0, umc / 8)
    w_proj = 1.0 - w_conv
    corpora = [_corpus_ex(i) for i in items]
    df = Counter()
    for c in corpora:
        df.update(c["set"])
    n = max(len(items), 1)
    recs = []
    for item, corpus in zip(items, corpora):
        conv_score, conv_matched = _sub_score(
            conv_q, corpus["set"], df, n, min_matches)
        proj_score, proj_matched = _sub_score(
            proj_q, corpus["set"], df, n, 1)
        hist_count = history.get(item.get("plugin") or "", 0)
        hist_boost = math.log(1 + hist_count) * H_HISTORY
        score = w_conv * conv_score + w_proj * (proj_score + hist_boost)
        if score <= 0:
            continue
        actionable = item["source"] == "plugin" and item["state"] == "disabled"
        if actionable:
            score *= BOOST_DISABLED
        reasons = []
        if hist_count and w_proj > 0:
            reasons.append(f"이 프로젝트에서 {hist_count}회 사용")
        pv = _visible_top(proj_matched, proj["visible"], proj_q)
        if pv and proj_score > 0 and w_proj > 0:
            reasons.append("프로젝트: " + ", ".join(pv))
        cv = _visible_top(conv_matched, conv["visible"], conv_q)
        if cv and conv_score > 0 and w_conv > 0:
            reasons.append("대화: " + ", ".join(cv))
        recs.append({
            "item": item,
            "score": round(score, 4),
            "kind": "actionable" if actionable else "informational",
            "reasons": reasons,
        })
    recs.sort(key=lambda r: -r["score"])
    return recs[:top_k]
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_recommender.py -v`
Expected: 전부 PASS (수정된 1건 포함)

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/recommender.py brain/tests/test_recommender.py
git commit -m "feat(brain): continuous-blend scoring with history boost and human-readable reasons"
```

---

### Task 6: LLM 리파인 — `llm_refine.py`

**Files:**
- Create: `brain/skills_companion/llm_refine.py`
- Test: `brain/tests/test_llm_refine.py` (신규)

**Interfaces:**
- Consumes: Task 5의 rec dict 형태(`{"item": {...}, "score", "kind", "reasons"}`), `stores.read_json`/`atomic_write_json`, `paths.state_dir()`
- Produces: `refine(session_id, user_texts, user_msg_count, local_recs, top_k=5, runner=None) -> list[rec]`
  - 트리거: `umc ≥ 10` 창1, 캐시 msg_count 대비 `+15`면 창2 — **창 최대 2개**, 실패 시 같은 창에서 재시도 1회(창당 시도 ≤2)
  - `runner(prompt) -> str | None` 주입 가능; 기본 `subprocess.run(["claude","-p",prompt,"--model","haiku"], timeout=30)`
  - 캐시: `state/llm-recs/<session_id>.json` = `{ts, msg_count, window, recs, failed, attempts}`
  - 검증: JSON 배열 파싱, 후보 밖 invoke 버림, reason 80자 절단, 최대 3개
  - 병합: LLM 추천 최상위 고정(`reasons=[모델 이유]`, `llm: true`, kind는 로컬 rec 그대로), 로컬이 뒤 채움(중복 제거)
  - 모든 실패 경로에서 로컬 추천 반환 (추천 기능 절대 불사)

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_llm_refine.py` 신규:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_llm_refine.py -v`
Expected: 전부 FAIL (`ModuleNotFoundError: ... llm_refine`)

- [ ] **Step 3: 구현** — `brain/skills_companion/llm_refine.py` 신규:

```python
import json
import re
import subprocess
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


def default_runner(prompt):
    r = subprocess.run(["claude", "-p", prompt, "--model", "haiku"],
                       capture_output=True, text=True, timeout=TIMEOUT)
    return r.stdout if r.returncode == 0 else None


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
```

- [ ] **Step 4: 통과 확인**

Run: `tests/test_llm_refine.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/llm_refine.py brain/tests/test_llm_refine.py
git commit -m "feat(brain): haiku llm refine with session cache, retry cap, safe fallback"
```

---

### Task 7: CLI 배선 — `_cmd_recommend` v2

**Files:**
- Modify: `brain/skills_companion/cli.py:4-15` (import + `_cmd_recommend`)
- Test: `brain/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1~6 전부 (`extract_signals` 새 키, `history_for`, `project_tokens`, `recommend` 새 파라미터, `llm_refine.refine`)
- Produces: `recommend` CLI 출력 스키마 불변 — `{"session": str|None, "recommendations": list[rec]}`. LLM 후보 풀 확보를 위해 로컬 추천은 `top_k=max(args.top, 12)`로 뽑고 최종 반환은 `args.top`개.

- [ ] **Step 1: 실패하는 테스트 작성** — `brain/tests/test_cli.py` 끝에 추가:

```python
def test_recommend_blends_history_for_cwd(claude_home, write_transcript, capsys):
    write_transcript("SH", ["시작"], cwd="/tmp/work")   # umc=1 → 프로젝트/이력 가중 우세
    _run(capsys, ["activate", "--plugin", UA, "--session", "SH"])
    out = _run(capsys, ["recommend", "--top", "3"])
    top = out["recommendations"][0]
    assert top["item"]["invoke"] == "/understand-anything:understand"
    assert any("1회 사용" in r for r in top["reasons"])
```

- [ ] **Step 2: 실패 확인**

Run: `tests/test_cli.py -v`
Expected: 신규 1개 FAIL (이력이 recommend에 안 물려 recommendations가 비거나 다른 항목), 기존 PASS

- [ ] **Step 3: 구현** — `cli.py`의 import 줄에 `llm_refine` 추가:

```python
from . import (activation, context_report, inventory, lightweight, llm_refine,
               paths, recommender, revert, scanner, stores, transcripts)
```

`_cmd_recommend`를 다음으로 교체:

```python
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
            "recommendations": recs}
```

- [ ] **Step 4: 통과 확인 + 수동 스모크**

Run: `tests/test_cli.py -v` → 전부 PASS.
수동 확인 (실환경 읽기 전용, JSON이 나오고 reasons가 인간 가독인지):

```bash
cd /Users/earendel/Desktop/Work_with_Claude_Mac/skills-companion/brain && python3 -m skills_companion.cli recommend --top 5
```

Expected: JSON 1줄, `recommendations[].reasons`가 `"대화: …"`/`"프로젝트: …"`/`"이 프로젝트에서 N회 사용"` 형태(빈 배열 허용), 어미 조각("니다" 등) 없음. (주의: 이 호출은 실제 haiku 트리거 조건을 충족하면 claude CLI를 1회 부를 수 있음 — 30초 이내 반환·폴백 확인 겸용.)

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python3 -m pytest -q` → 전부 PASS 확인 후:

```bash
git add brain/skills_companion/cli.py brain/tests/test_cli.py
git commit -m "feat(brain): wire recommend CLI to history, project corpus, llm refine"
```

---

### Task 8: 카탈로그 UI v2 — `index.html` 재작성

**Files:**
- Rewrite: `shell/ui/index.html`

**Interfaces:**
- Consumes: 기존 Tauri 커맨드(`brain`, `notify`, `copy_text`, `autotype_reload`, `open_wizard`) — **main.rs 무변경**. brain 출력 스키마(scan/recommend/config-get/config-set/context-report) 그대로.
- Produces: 사이드바(168px) + 검색바(⌘K) + 히어로 추천 + 리스트 행 구조. 뷰: `✦ 이 세션`(기본) / 전체 / 카테고리별 / 비활성 플러그인 / 컨텍스트 리포트 / 설정. 스타일 토큰: 스펙 2.2 (다크 기본 `#101014`/`#17171d`/`#26262e`/`#e2e2e6`/`#9a9aa4`, 액센트 `#7c5dfa`, 라이트 `#fafafc`/`#fff`/`#e4e4ea`/`#1a1a1f`).
- 참고: v1의 groupBy 셀렉트·"비활성 플러그인만" 체크박스는 사이드바 내비게이션이 대체(승인 목업 기준). 검색·그룹핑·활성화/복사·설정·리포트 로직은 유지.

- [ ] **Step 1: `shell/ui/index.html` 전체를 다음 내용으로 교체** (Write로 통째 교체; 절대경로 사용):

```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Skills Companion</title>
<style>
:root{
  --bg:#fafafc; --panel:#ffffff; --line:#e4e4ea; --fg:#1a1a1f; --muted:#71717c;
  --accent:#7c5dfa; --accent-hi:#6a4be8; --accent-soft:rgba(124,93,250,.10);
  --accent-line:rgba(124,93,250,.35); --btn-bg:#ffffff; --btn-line:#d8d8e0;
  --hover:rgba(20,20,30,.05); --glow:0 0 24px rgba(124,93,250,.10);
  --ok:#16a34a; --bad:#dc2626; --man:#2563eb; --load:#d97706;
}
@media(prefers-color-scheme:dark){:root{
  --bg:#101014; --panel:#17171d; --line:#26262e; --fg:#e2e2e6; --muted:#9a9aa4;
  --accent:#7c5dfa; --accent-hi:#a48bff; --accent-soft:rgba(124,93,250,.14);
  --accent-line:rgba(124,93,250,.45); --btn-bg:#1c1c23; --btn-line:#32323c;
  --hover:rgba(255,255,255,.05); --glow:0 0 24px rgba(124,93,250,.15);
  --ok:#30d158; --bad:#ff453a; --man:#5b9dff; --load:#ffb340;
}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;display:flex;overflow:hidden;background:var(--bg);color:var(--fg);
font:13.5px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",sans-serif}
code.inv{font:600 12.5px ui-monospace,"SF Mono",Menlo,monospace;color:var(--accent-hi);word-break:break-all}
button{border:1px solid var(--btn-line);background:var(--btn-bg);color:var(--fg);
border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px;
transition:background 120ms ease,border-color 120ms ease;white-space:nowrap}
button:hover{border-color:var(--accent-line)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:hover{background:var(--accent-hi)}
select,input[type=search]{padding:6px 10px;border:1px solid var(--line);
border-radius:7px;background:var(--panel);color:var(--fg);font:inherit;font-size:12.5px}
/* ── 사이드바 ── */
#sb{width:168px;flex-shrink:0;border-right:1px solid var(--line);padding:12px 0;
display:flex;flex-direction:column;gap:1px;overflow-y:auto}
#sb .app{font-weight:700;font-size:13px;padding:2px 14px 10px}
.nav{padding:5px 14px;display:flex;justify-content:space-between;align-items:center;
cursor:pointer;font-size:12.5px;border-right:2px solid transparent;
transition:background 120ms ease}
.nav:hover{background:var(--hover)}
.nav.sel{background:var(--accent-soft);border-right-color:var(--accent);font-weight:600}
.nav .cnt{color:var(--muted);font-size:11px}
#sb .sep{border-top:1px solid var(--line);margin:8px 12px}
/* ── 메인 ── */
#main{flex:1;display:flex;flex-direction:column;min-width:0}
#topbar{display:flex;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line);
align-items:center;flex-shrink:0}
#q{flex:1;min-width:0}
#content{flex:1;overflow-y:auto;padding:0 14px 16px}
#err{color:var(--bad);padding:6px 14px;font-size:12.5px}
/* ── 히어로 추천 ── */
.hero{margin:12px 0 4px;padding:12px 14px;border-radius:10px;
background:linear-gradient(135deg,var(--accent-soft),transparent);
border:1px solid var(--accent-line);box-shadow:var(--glow)}
.hero h4{margin:0 0 6px;font-size:12.5px;color:var(--accent-hi);letter-spacing:.02em}
.hrow{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:5px 0}
.hrow .l{min-width:0;display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}
.why{color:var(--muted);font-size:11.5px}
/* ── 리스트 행 ── */
.gh{margin:14px 0 4px;font-size:11px;text-transform:uppercase;
letter-spacing:.06em;color:var(--muted);font-weight:700}
.gh small{font-weight:400;letter-spacing:0}
.lrow{display:flex;justify-content:space-between;align-items:center;gap:10px;
padding:6px 10px;border-radius:7px;transition:background 120ms ease}
.lrow:hover{background:var(--hover)}
.lrow .l{min-width:0;display:flex;gap:10px;align-items:baseline}
.lrow .d{color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.dot{width:7px;height:7px;border-radius:99px;flex-shrink:0;align-self:center}
@media(prefers-color-scheme:dark){.dot{box-shadow:0 0 6px currentColor}}
/* ── 설정·리포트 패널 ── */
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:14px;margin:12px 0}
.panel h3{margin:0 0 10px;font-size:13.5px}
.panel table{width:100%;border-collapse:collapse;font-size:12.5px}
.panel td{padding:4px 6px;border-top:1px solid var(--line)}
.muted{color:var(--muted)}
</style></head><body>
<div id="sb">
  <div class="app">🗂️ Skills Companion</div>
  <div id="nav"></div>
</div>
<div id="main">
  <div id="topbar">
    <input id="q" type="search" placeholder="⌕ 이름·설명·명령 검색 (⌘K)">
    <button id="refresh" title="새로고침">↻</button>
  </div>
  <div id="err" style="display:none"></div>
  <div id="content">로딩…</div>
</div>
<script>
const inv = (cmd, args) => window.__TAURI__.core.invoke(cmd, args);
const brain = (...args) => inv("brain", { args });
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function clearErr() {
  const el = document.getElementById("err");
  el.innerHTML = ""; el.style.display = "none";
}
async function brainSafe(...args) {
  try { const r = await brain(...args); clearErr(); return r; }
  catch (e) {
    const el = document.getElementById("err");
    el.innerHTML = "브레인 호출 실패: " + esc(String(e));
    el.style.display = "block";
    return null;
  }
}
const DOT = { loaded:"var(--load)", silenced:"var(--man)",
              enabled:"var(--ok)", disabled:"var(--bad)" };
const STATE_LABEL = { loaded:"로딩중", silenced:"수동", enabled:"활성", disabled:"비활성" };
let items = [], recs = [], config = {}, report = null, view = "session";

/* ── 액션 ── */
async function activatePlugin(pluginKey, invoke) {
  const r = await brainSafe("activate", "--plugin", pluginKey);
  if (!r) return;
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

/* ── 사이드바 ── */
function navEntries() {
  const cats = {};
  for (const i of items) cats[i.category] = (cats[i.category] || 0) + 1;
  const disabledN = items.filter(i => i.source === "plugin" && i.state === "disabled").length;
  return [
    { id: "session", label: "✦ 이 세션" },
    { id: "all", label: "전체", cnt: items.length },
    ...Object.keys(cats).sort().map(c => ({ id: "cat:" + c, label: c, cnt: cats[c] })),
    { id: "disabled", label: "비활성 플러그인", cnt: disabledN },
    { sep: true },
    { id: "report", label: "📊 컨텍스트 리포트" },
    { id: "settings", label: "⚙️ 설정" },
  ];
}
function renderSidebar() {
  document.getElementById("nav").innerHTML = navEntries().map(n => n.sep
    ? `<div class="sep"></div>`
    : `<div class="nav${view === n.id ? " sel" : ""}" data-view="${esc(n.id)}">
         <span>${esc(n.label)}</span>${n.cnt != null ? `<span class="cnt">${n.cnt}</span>` : ""}
       </div>`).join("");
}

/* ── 히어로 추천 ── */
function actionBtn(i) {
  return (i.source === "plugin" && i.state === "disabled")
    ? `<button class="primary" data-act="on" data-plugin="${esc(i.plugin)}" data-invoke="${esc(i.invoke)}">활성화</button>`
    : `<button data-act="copy" data-invoke="${esc(i.invoke)}">복사</button>`;
}
function heroHTML() {
  const top = recs.slice(0, 3);
  if (!top.length) return "";
  return `<div class="hero"><h4>✦ 이 세션 추천</h4>` + top.map(x =>
    `<div class="hrow"><span class="l"><code class="inv">${esc(x.item.invoke)}</code>
       <span class="why">${x.reasons.map(esc).join(" · ")}</span></span>
       ${actionBtn(x.item)}</div>`).join("") + `</div>`;
}

/* ── 리스트 행 ── */
function rowHTML(i) {
  const c = DOT[i.state] || "var(--muted)";
  return `<div class="lrow">
    <span class="l"><span class="dot" style="background:${c};color:${c}"
      title="${esc(STATE_LABEL[i.state] || i.state)}"></span>
      <code class="inv">${esc(i.invoke)}</code>
      <span class="d">${esc((i.desc || "").slice(0, 160))}</span></span>
    ${actionBtn(i)}</div>`;
}

/* ── 설정·리포트 뷰 ── */
function settingsHTML() {
  const rows = Object.entries(config.per_plugin || {});
  return `<div class="panel"><h3>⚙️ 설정</h3>
    <div style="margin-bottom:10px">기본 되돌림 정책:
      <select id="defPolicy">
        <option value="ask">물어보기 (ask)</option>
        <option value="auto-revert">자동 되돌림</option>
        <option value="keep">유지</option>
      </select>
      <label style="margin-left:12px"><input type="checkbox" id="notifs"> 추천 알림 켜기</label>
    </div>
    <table id="perPlugin">${rows.length
      ? "<tr><td><b>플러그인별 정책</b></td><td></td><td></td></tr>" + rows.map(([p, pol]) =>
        `<tr><td><code class="inv">${esc(p)}</code></td><td>${esc(pol)}</td>
         <td><button data-act="unset" data-plugin="${esc(p)}">해제</button></td></tr>`).join("")
      : ""}</table>
    <div style="margin-top:12px"><button data-act="wizard">🪶 경량화 마법사 다시 실행</button></div>
  </div>`;
}
function reportHTML() {
  if (!report) return `<div class="panel"><h3>📊 컨텍스트 리포트</h3><p class="muted">로딩…</p></div>`;
  return `<div class="panel"><h3>📊 컨텍스트 리포트 (추정)</h3>
    <table>${report.rows.map(r =>
      `<tr><td>${r.controllable ? "🎛" : "📎"} ${esc(r.label)}</td>
       <td style="text-align:right">${esc(r.tokens ?? "—")}</td>
       <td class="muted">${esc(r.advice)}</td></tr>`).join("")}
    <tr><td><b>합계(추정)</b></td>
    <td style="text-align:right"><b>${esc(report.total_estimate)}</b></td><td></td></tr>
    </table></div>`;
}

/* ── 메인 렌더 ── */
function render() {
  renderSidebar();
  const c = document.getElementById("content");
  if (view === "settings") {
    c.innerHTML = settingsHTML();
    document.getElementById("defPolicy").value = config.default_policy || "ask";
    document.getElementById("notifs").checked = !!config.notifications_enabled;
    return;
  }
  if (view === "report") { c.innerHTML = reportHTML(); return; }
  const q = document.getElementById("q").value.trim().toLowerCase();
  let pool = items;
  if (view === "disabled")
    pool = pool.filter(i => i.source === "plugin" && i.state === "disabled");
  else if (view.startsWith("cat:"))
    pool = pool.filter(i => i.category === view.slice(4));
  if (q) pool = pool.filter(i =>
    (i.invoke + " " + i.name + " " + i.desc).toLowerCase().includes(q));
  const groups = {};
  for (const i of pool) (groups[i.category] = groups[i.category] || []).push(i);
  const hero = (view === "session" && !q) ? heroHTML() : "";
  const list = Object.keys(groups).sort().map(k =>
    `<div class="gh">${esc(k)} <small>${groups[k].length}</small></div>` +
    groups[k].map(rowHTML).join("")).join("");
  c.innerHTML = hero + (list || `<p class="muted" style="margin-top:16px">결과 없음</p>`);
}

/* ── 데이터 로드 ── */
async function loadRecs() {
  const r = await brainSafe("recommend", "--top", "3");
  recs = r ? (r.recommendations || []) : [];
  if (view === "session") render();
}
async function loadSettings() {
  const c = await brainSafe("config-get");
  if (c) config = c;
  if (view === "settings") render();
}
async function loadReport() {
  const rep = await brainSafe("context-report");
  if (rep) report = rep;
  if (view === "report") render();
}
async function saveConfig(patch) {
  const c = await brainSafe("config-set", "--json", JSON.stringify(patch));
  if (!c) return;
  config = c;
  if (view === "settings") render();
}
async function load() {
  const r = await brainSafe("scan");
  if (r) items = r.items;
  render();
  loadRecs(); loadSettings(); loadReport();
}

/* ── 이벤트 ── */
document.addEventListener("click", e => {
  const nav = e.target.closest(".nav");
  if (nav) { view = nav.dataset.view; render(); return; }
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.act === "on") activatePlugin(b.dataset.plugin, b.dataset.invoke);
  else if (b.dataset.act === "copy") copyInvoke(b.dataset.invoke);
  else if (b.dataset.act === "unset") {
    const pp = { ...config.per_plugin }; delete pp[b.dataset.plugin];
    saveConfig({ per_plugin: pp });
  } else if (b.dataset.act === "wizard") inv("open_wizard");
  else if (b.id === "refresh") load();
});
document.addEventListener("change", e => {
  if (e.target.id === "defPolicy") saveConfig({ default_policy: e.target.value });
  else if (e.target.id === "notifs") saveConfig({ notifications_enabled: e.target.checked });
});
document.getElementById("q").addEventListener("input", render);
document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    document.getElementById("q").focus();
    document.getElementById("q").select();
  }
});
load();
</script></body></html>
```

- [ ] **Step 2: dev로 시각 검증 준비**

```bash
source "$HOME/.cargo/env" && cd /Users/earendel/Desktop/Work_with_Claude_Mac/skills-companion/shell/src-tauri && cargo tauri dev
```

(run_in_background. 주의: 릴리스 상주 인스턴스와 동시 폴링됨 — 다이얼로그가 헷갈리면 무시하고 메인 창만 검증.)

- [ ] **Step 3: 🛑 STOP — 사용자 시각 확인 (라이트/다크 둘 다)**

체크리스트: 사이드바 렌더·선택 하이라이트 / 카테고리·전체·비활성 뷰 전환 / 검색 + ⌘K 포커스 / 히어로 추천(있을 때만 렌더, 근거 문자열) / 리스트 행 상태 점·설명 ellipsis / 활성화·복사 버튼 동작(클립보드+알림) / 설정 뷰(정책 변경·알림 토글·마법사 버튼) / 리포트 뷰. **라이트 모드와 다크 모드 모두 확인.** 사용자 피드백 반영 후 재확인.

- [ ] **Step 4: 승인 후 커밋**

```bash
git add shell/ui/index.html
git commit -m "feat(ui): catalog v2 - sidebar, hero recommendations, list rows, modern productivity theme"
```

---

### Task 9: `revert.html`·`wizard.html` 일관성 리스타일

**Files:**
- Modify: `shell/ui/revert.html:3-15` (`<style>` 블록만)
- Modify: `shell/ui/wizard.html:3-19` (`<style>` 블록만)

**Interfaces:**
- Consumes: Task 8의 스타일 토큰 (동일 값 복제 — 파일 간 공유 불가, CSP상 외부 CSS 파일 대신 인라인 유지)
- Produces: 로직(HTML 구조·JS) 무변경, 색·라운딩·버튼·폰트만 교체

- [ ] **Step 1: `revert.html`의 `<style>` 블록을 다음으로 교체** (3~15행, `</style>` 전까지):

```css
:root{--bg:#fafafc;--panel:#fff;--line:#e4e4ea;--fg:#1a1a1f;--muted:#71717c;
--accent:#7c5dfa;--accent-hi:#6a4be8;--btn-bg:#fff;--btn-line:#d8d8e0;--bad:#dc2626}
@media(prefers-color-scheme:dark){:root{--bg:#101014;--panel:#17171d;--line:#26262e;
--fg:#e2e2e6;--muted:#9a9aa4;--accent:#7c5dfa;--accent-hi:#a48bff;
--btn-bg:#1c1c23;--btn-line:#32323c;--bad:#ff453a}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);
font:13.5px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",sans-serif}
.item{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:10px 12px;margin:8px 0}
code{font:600 12.5px ui-monospace,"SF Mono",Menlo,monospace;color:var(--accent-hi)}
label{margin-right:10px}
.remember{font-size:12px;color:var(--muted);display:block;margin-top:4px}
.actions{margin-top:14px;display:flex;gap:8px;justify-content:flex-end}
button{border:1px solid var(--btn-line);background:var(--btn-bg);color:var(--fg);
border-radius:6px;padding:7px 14px;cursor:pointer;transition:border-color 120ms ease}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
#err{color:var(--bad);padding:6px 0;font-size:12.5px;display:none}
```

- [ ] **Step 2: `wizard.html`의 `<style>` 블록을 다음으로 교체** (3~19행):

```css
:root{--bg:#fafafc;--panel:#fff;--line:#e4e4ea;--fg:#1a1a1f;--muted:#71717c;
--accent:#7c5dfa;--accent-hi:#6a4be8;--btn-bg:#fff;--btn-line:#d8d8e0;--bad:#dc2626}
@media(prefers-color-scheme:dark){:root{--bg:#101014;--panel:#17171d;--line:#26262e;
--fg:#e2e2e6;--muted:#9a9aa4;--accent:#7c5dfa;--accent-hi:#a48bff;
--btn-bg:#1c1c23;--btn-line:#32323c;--bad:#ff453a}}
body{margin:0;padding:18px;background:var(--bg);color:var(--fg);
font:13.5px/1.5 -apple-system,"Pretendard","Apple SD Gothic Neo",sans-serif}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:12px;margin:10px 0}
h3{margin:0 0 6px;font-size:14px}
.hint{font-size:12px;color:var(--muted);margin:2px 0 8px}
.row{display:flex;gap:8px;align-items:center;padding:2px 0}
code{font:600 12.5px ui-monospace,"SF Mono",Menlo,monospace;color:var(--accent-hi)}
details>summary{cursor:pointer;font-weight:600}
button{border:1px solid var(--btn-line);background:var(--btn-bg);color:var(--fg);
border-radius:6px;padding:8px 16px;cursor:pointer;transition:border-color 120ms ease}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.total{font-weight:700}
#done{display:none}
#err{color:var(--bad);padding:6px 0;font-size:12.5px;display:none}
.brain-error{background:rgba(220,38,38,.08);border:1px solid var(--bad);
border-radius:6px;padding:8px;margin:8px 0;color:var(--bad);font-size:13px}
```

- [ ] **Step 3: 🛑 STOP — 사용자 시각 확인**

dev 인스턴스에서 마법사 열기(설정 뷰의 버튼). 되돌림 다이얼로그는 HANDOFF의 가짜 leak 요령으로 띄우거나(끝나면 ledger 정리 확인) 통합 스모크(Task 10)에서 함께 확인해도 됨. 라이트/다크 둘 다.

- [ ] **Step 4: 승인 후 커밋**

```bash
git add shell/ui/revert.html shell/ui/wizard.html
git commit -m "feat(ui): restyle revert dialog and wizard with v2 tokens"
```

---

### Task 10: 통합 스모크 (dev)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 전체 테스트 최종 확인**

Run: `python3 -m pytest -q`
Expected: 전부 PASS (기존 55 + 신규 전부)

- [ ] **Step 2: dev 인스턴스에서 스펙 2.5 체크리스트 실행**

- 카탈로그 렌더·검색·⌘K·그룹(뷰) 전환
- 활성화 흐름: 비활성 플러그인 활성화 → 클립보드 `/reload-plugins` + 알림
- 복사 버튼 → 클립보드 + 알림
- 설정/리포트 뷰 전환, 정책 변경 저장 확인 (`config-get`으로 재확인)
- 히어로 근거 표시: 실제 세션에서 `"대화: …"`/`"이 프로젝트에서 N회 사용"` 문자열 확인
- 되돌림 다이얼로그 열림/닫힘 (필요 시 가짜 leak: `stores.ledger_add('<fake-sid>', '<꺼진 plugin>')` → 20초 내 다이얼로그, 끝나면 ledger 정리 확인)
- 마법사 열기

- [ ] **Step 3: 🛑 STOP — 사용자 통합 확인 호출.** 이상 없으면 dev 인스턴스 종료.

---

### Task 11: 릴리스 빌드 · 재배포 · 마무리

**Files:**
- Modify: `HANDOFF.md` (현재 상태 절 갱신), `README.md` (필요 시 상태 줄만)

- [ ] **Step 1: 릴리스 빌드** (run_in_background, ~2분)

```bash
source "$HOME/.cargo/env" && cd /Users/earendel/Desktop/Work_with_Claude_Mac/skills-companion/shell/src-tauri && cargo tauri build
```

빌드 전 `ls shell/src-tauri/capabilities/` — capability JSON 외 파일(특히 `.omc`)이 있으면 제거.

- [ ] **Step 2: 재배포 (HANDOFF 절차)**

```bash
launchctl unload ~/Library/LaunchAgents/com.earendel.skills-companion.plist
rm -rf "/Applications/Skills Companion.app"
cp -R "/Users/earendel/Desktop/Work_with_Claude_Mac/skills-companion/shell/src-tauri/target/release/bundle/macos/Skills Companion.app" /Applications/
launchctl load ~/Library/LaunchAgents/com.earendel.skills-companion.plist
pgrep -fl skills-companion   # 단일 인스턴스 확인
```

- [ ] **Step 3: 🛑 STOP — 사용자 실환경 스모크 호출** (트레이 → 창 열기, 추천·활성화·설정 확인. 앱 stderr는 `~/Library/Logs/skills-companion.log`)

- [ ] **Step 4: 문서 갱신 + 최종 커밋·push**

`HANDOFF.md`의 "현재 상태"/"이번 미션" 절을 v2 완료 상태로 갱신하고:

```bash
git add HANDOFF.md README.md
git commit -m "docs: recommender v2 + catalog UI v2 완료 상태 반영"
git push
```

- [ ] **Step 5: 수행 내역·남은 권장사항 요약 보고**

권장사항 후보(미리 기록): `state/llm-recs/` 오래된 세션 캐시 청소(스윕에 편승), BIGRAM_STOP·조사 목록의 실사용 기반 확장, 카테고리 규칙(CATEGORY_RULES) 재조정.
