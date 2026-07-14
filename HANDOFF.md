# HANDOFF — 추천 로직 v2 + 카탈로그 UI v2 **완료** 스냅샷

> 새 세션의 실행자에게: v2 미션(추천 로직 v2 + 카탈로그 UI v2)은 구현·재배포까지
> **완료**되었다. 이 문서는 2026-07-14 실측 스냅샷이다. 새 작업이 없다면 여기서
> 할 일은 없고, 새 미션을 받으면 아래 절대 규칙·함정 절을 먼저 읽을 것.

## 현재 상태 (실측, 2026-07-14)

- **v1 Task 20/20 + v2 플랜 11 태스크 완료.** 앱 상주 중:
  `/Applications/Skills Companion.app` (2026-07-07 01:11 빌드 = a36425b),
  LaunchAgent `com.earendel.skills-companion` (RunAtLoad, KeepAlive=false,
  stderr → `~/Library/Logs/skills-companion.log`).
- HEAD = origin/main (push 완료). 주요 커밋: brain v2 5개(3bd130a…c9f9463),
  UI v2 + llm runner 강화 + Windows 포트(08f3041), 트레이 세션-이름 표시
  (f2a4a9b, a36425b).
- brain 테스트 **87개 전부 통과** (`cd brain && python3 -m pytest -q`).
- Windows(mari)에도 상주 설치 완료 — 크로스플랫폼 mac-ism 수정 내역은
  메모리 `skills-companion-windows-port` 참조.

## v2에서 달라진 것 (요약)

- `transcripts.extract_signals` → `cwd`/`user_texts`/`user_msg_count` 추가.
- `recommender.tokenize_ex` — 조사 스트립 온전 토큰(2배 가중)·bigram 불용어·
  `visible` 집합(근거 노출은 온전 토큰만). `tokenize()`는 하위호환 래퍼.
- `stores.history_add/history_for` — `state/activation-history.json`, cwd별 누적.
- `recommender.project_tokens` — cwd의 CLAUDE.md/README/package.json/
  pyproject.toml/Cargo.toml 앞 4KB.
- `recommender.recommend` — 연속 블렌딩 `w_conv=min(1,umc/8)`,
  `hist_boost=log(1+n)*2.0`, reasons는 인간 가독 문자열. min_matches는 대화에만.
- `llm_refine.py` — 트리거 창 2개(umc≥10, +15), 창당 재시도 1회, 30초 타임아웃,
  프로세스 그룹 kill(파이프 행 방지), 캐시 `state/llm-recs/<sid>.json`, 전면 폴백.
- UI: 사이드바(168px)+검색(⌘K)+히어로 추천+그룹 패널 리스트 행,
  모던 프로덕티비티 토큰(액센트 #7c5dfa, 라이트/다크). revert/wizard 동일 토큰.
- `main.rs`/CLI 스키마 하위호환 유지 (`reasons: list[str]`).

## 환경·절차 (실측 노하우)

- Rust 툴체인: `source "$HOME/.cargo/env"` 필수. tauri-cli 2.11.4.
- 빌드: `cd shell/src-tauri && cargo tauri build` (~2분, run_in_background 권장).
- **재배포 절차**: `launchctl unload ~/Library/LaunchAgents/com.earendel.skills-companion.plist`
  → `rm -rf "/Applications/Skills Companion.app"` → 번들 `cp -R` → `launchctl load ...`
  → `pgrep -fl skills-companion`으로 단일 인스턴스 확인.
  (앱이 종료돼 있으면 `launchctl kickstart gui/$UID/com.earendel.skills-companion`.)
- dev 검증: `cargo tauri dev` (릴리스 인스턴스와 동시 폴링되므로 헷갈리면 한쪽 종료).
- 창 캡처로 자가 검증 가능: pyobjc로 `kCGWindowNumber` 조회 →
  `screencapture -x -o -l <id>` (앱이 다른 스페이스에 있어도 잡힘).
- 앱 stderr는 LaunchAgent 로그 파일에서 확인 가능 (open_revert 실패 등).

## 함정 (실제로 밟은 것)

- **cwd가 있는 셸에서 파일을 만들면 OMC 훅이 `.omc/` 상태 디렉터리를 그 cwd에
  생성한다.** `capabilities/` 안에 `.omc`가 생기면 tauri 빌드가
  "missing field identifier"로 실패한다 — capabilities/에는 capability JSON만 둘 것.
- **`newest_session()` 휴리스틱은 동시 세션이 많으면 오귀속한다** — 스펙 1.2가
  수용한 한계. 고치려 들지 말 것 (이력은 count 누적이라 소수 오귀속에 강건).
- `claude -p` 서브프로세스는 stdout 파이프를 자식(MCP 서버 등)이 물고 있으면
  타임아웃이 안 듣는다 — llm_refine.default_runner가 임시파일 + 프로세스 그룹
  kill로 해결해 둠. 되돌리지 말 것.
- 되돌림 다이얼로그는 "그 플러그인을 쓰는 마지막 살아있는 세션"이 끝날 때만 뜬다
  (held 규칙, revert.py). 스모크 시 다른 세션이 물고 있으면 조용히 kept 처리.
- 다이얼로그 검증 시 가짜 leak: `stores.ledger_add('<fake-sid>', '<꺼진 plugin>')`
  → transcript 없는 sid는 즉시 leak → 20초 내 다이얼로그. 끝나면 ledger 정리 확인.

## 절대 규칙 (스펙 C9/C12 — 변함없음, 서브에이전트에게도 전파)

앱/테스트/실행자 모두 다음 파일을 **절대 쓰지 않는다**:
`~/.claude.json`(직접) · `installed_plugins.json` · CLAUDE.md · MEMORY.md ·
앱 소유가 아닌 훅(특히 `korean-law-key-sync.py`).
MCP 변경은 `claude mcp remove/add-json -s user` 서브프로세스만.
`~/.claude/settings.json` 쓰기는 항상 앱 CLI 경유(atomic + 타임스탬프 백업).
brain은 stdlib 전용 유지(외부 의존성 도입 금지). UI는 외부 리소스 0(CSP).

## 남은 권장사항 (선택)

- `state/llm-recs/` 오래된 세션 캐시 청소를 sweep에 편승시키기.
- `BIGRAM_STOP`·조사 목록의 실사용 기반 확장 (recommend 근거 잡음 관측 시).
- `CATEGORY_RULES` 재조정 — 플러그인 카테고리가 pname 그대로라 사이드바가 김.

## 문서

- v2 스펙: `docs/superpowers/specs/2026-07-06-recommender-v2-ui-v2-design.md`
- v2 플랜: `docs/superpowers/plans/2026-07-06-recommender-v2-ui-v2.md`
- 원 스펙(C1~C13): `docs/superpowers/specs/2026-07-06-skills-companion-design.md`
- 완료된 v1 플랜: `docs/superpowers/plans/2026-07-06-skills-companion.md`
