# HANDOFF — Task 15 (실환경 마이그레이션) 실행용

> 새 세션의 실행자에게: 이 문서는 구현 세션(2026-07-06)의 최종 스냅샷이다.
> **20개 태스크 중 19개 완료** — 남은 것은 Task 15 하나이며, 사용자가 이미
> 실행을 승인하고 이 세션을 시작했다. Task 15는 실제 `~/.claude`를 바꾸는
> 유일한 태스크다: 신중히, 단계마다 검증하며, 되돌릴 수 있게 진행하라.

## 현재 상태 (실측, 2026-07-06)

- HEAD `02a8c75` = origin/main. 커밋 전부 push됨.
- brain 테스트 **55개 전부 통과** (`cd brain && python3 -m pytest -q`).
- `cargo build` 클린 (debug). 릴리스 빌드(`cargo tauri build`)는 아직 안 함.
- 최종 전체 브랜치 리뷰(opus) 통과. 유일한 결함(wizard `#err`)은 02a8c75로 수정됨.
- 태스크별 리뷰 기록·Minor 발견 원장: `.superpowers/sdd/progress.md`
  (**git 미추적 로컬 파일** — 이 체크아웃에만 존재. 지우지 말 것).
- 툴체인: rustup + tauri-cli 2.11.4 설치됨 (`source "$HOME/.cargo/env"` 필요).

## 사전점검 결과 (2026-07-06, 읽기 전용으로 이미 통과)

1. **`claude mcp` 플래그 현행 확인** — `remove <name> -s user` /
   `add-json <name> <json> -s user` 유효. `lightweight.py:88,101`이 이미
   `-s user`를 넘김. (기본 scope는 "local"이므로 이 플래그가 핵심.)
2. **치트시트 훅 문자열 매칭 확인** — 실제 settings.json의 SessionStart 훅은
   `bash /Users/earendel/.claude/skills-cheatsheet/open.sh` →
   `installer.remove_cheatsheet_hook`의 부분문자열 `skills-cheatsheet/open.sh`와
   일치. 같이 있는 `korean-law-key-sync.py` 훅은 필터가 보존함(테스트 검증됨).
3. **wizard `#err` 수정 반영** — 3개 UI 파일 모두 `id="err"` 존재.

## Task 15 실행 순서 (플랜 + 최종 리뷰 전제조건 병합)

플랜 원문: `docs/superpowers/plans/2026-07-06-skills-companion.md` Task 15
(§2356~2461). 아래는 최종 리뷰가 요구한 선행 항목을 끼워 넣은 권장 순서:

1. **CSP 추가 (릴리스 빌드 전에!)** — `shell/src-tauri/tauri.conf.json`의
   `app`에 `"security": {"csp": "default-src 'self'; style-src 'self' 'unsafe-inline'"}`
   추가. Tauri v2가 번들 자산의 인라인 스크립트에 해시를 자동 주입함.
   `cargo tauri dev`로 메인 창이 정상 렌더링되는지 사용자와 함께 확인 후 커밋.
   (구현 세션에서 미룬 이유: 시각 검증 없이 CSP를 넣으면 UI가 깨져도 모름.)
2. **수동 백업** — `cp ~/.claude/settings.json ~/.claude/settings.json.pre-t15`
   (앱이 타임스탬프 백업을 만들지만 별도 1부가 싼 보험).
3. **플랜 Step 1** — `cargo tauri build`(수 분, **run_in_background**) →
   `/Applications`에 복사 → 실행 + pgrep 확인. 트레이 아이콘은 사용자가 확인.
4. **플랜 Step 2** — `install-hooks` (SessionEnd 신호 훅 추가 + 치트시트
   SessionStart 훅 제거가 한 번에 수행됨) → 브리프의 검증 파이썬 스니펫 실행.
5. **플랜 Step 3** — `/myskills` SKILL.md 교체 + 치트시트 HTML을
   `~/.claude/backups/`로 아카이브 (mv, 되돌림 가능).
6. **플랜 Step 4** — `installer/com.earendel.skills-companion.plist` 생성,
   `~/Library/LaunchAgents/`에 복사, `launchctl load`, 등록 확인.
7. **플랜 Step 5 스모크 테스트** — 사용자와 인터랙티브로. 추천 트레이 노출,
   활성화 클릭→클립보드/자동타이핑, `/exit`→되돌림 다이얼로그, `/myskills`.
   대기 불가한 leak-sweep 검증은 브리프가 허용한 가짜 old-mtime 방식으로.
8. **플랜 Step 6 커밋** + README "현재 상태"를 20/20으로 갱신 → push.

## 알려진 한계 (이번엔 고치지 않아도 되지만 인지할 것)

- `main.rs`의 `brain_dir()`은 `~/Desktop/Work_with_Claude_Mac/skills-companion/brain`
  하드코딩 — 이 머신에서는 정상 동작. 배포/패키징 시 수정 필요(원장 기록됨).
- `main.rs`는 PATH의 `python3`, 훅 스크립트는 `/usr/bin/python3` 사용.
  LaunchAgent 기본 PATH에 `/usr/bin`이 포함되므로 양쪽 다 해석되지만,
  앱이 LaunchAgent로 떴을 때 brain 호출이 실패하면 이 지점부터 의심할 것
  (증상: 트레이 추천 없음 / UI에 "브레인 호출 실패").
- 되돌림 방법: 훅 = `uninstall-hooks` verb + settings 백업 복원, 치트시트 =
  backups에서 mv 복원 + SessionStart 훅 재추가, LaunchAgent = `launchctl unload` + plist 삭제.

## 절대 규칙 (스펙 C9/C12 — 변함없음, 서브에이전트에게도 전파)

앱/테스트/실행자 모두 다음 파일을 **절대 쓰지 않는다**:
`~/.claude.json`(직접) · `installed_plugins.json` · CLAUDE.md · MEMORY.md ·
앱 소유가 아닌 훅(특히 `korean-law-key-sync.py`는 건드리지 말 것).
MCP 변경은 `claude mcp remove/add-json -s user` 서브프로세스만.
`~/.claude/settings.json` 쓰기는 항상 앱 CLI 경유(atomic + 타임스탬프 백업).

## 문서

- 플랜: `docs/superpowers/plans/2026-07-06-skills-companion.md` (Task 15 섹션)
- 스펙: `docs/superpowers/specs/2026-07-06-skills-companion-design.md` (C1~C13 재조사 금지)
- 구현 세션 리뷰 원장: `.superpowers/sdd/progress.md` (로컬)
- 태스크별 브리프/리포트: `.superpowers/sdd/task-*-{brief,report}.md` (로컬)
