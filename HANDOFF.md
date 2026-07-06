# HANDOFF — 추천 로직 v2 + 카탈로그 UI v2 (플랜 작성 → 구현)

> 새 세션의 실행자에게: 이 문서는 2026-07-06 세션(Task 15 실환경 마이그레이션 +
> v2 브레인스토밍)의 최종 스냅샷이다. **설계는 사용자 승인이 끝났다** — 이 세션의
> 첫 임무는 superpowers:writing-plans로 구현 플랜을 만드는 것이고, 설계를 다시
> 여는 것이 아니다.

## 현재 상태 (실측, 2026-07-06)

- **Task 20/20 완료.** 앱이 실환경에서 상주 중: `/Applications/Skills Companion.app`,
  LaunchAgent `com.earendel.skills-companion` (RunAtLoad, KeepAlive=false,
  stderr → `~/Library/Logs/skills-companion.log`).
- HEAD = origin/main (push 완료). 주요 최근 커밋: CSP 추가(bd254fc), installer(587d02d),
  Reopen/창닫기 결함 수정(091bdc1), README 20/20(3d2d8e4), StandardErrorPath(4ef2440).
- brain 테스트 **55개 전부 통과** (`cd brain && python3 -m pytest -q`).
- 훅 설치됨: SessionEnd 신호 훅 + 치트시트 SessionStart 훅 제거됨.
  `korean-law-key-sync.py` 훅 보존 확인됨.
- `/myskills`는 앱을 여는 스킬로 리포인트됨. 구 치트시트는 `~/.claude/backups/`.

## 이번 미션

**스펙**: `docs/superpowers/specs/2026-07-06-recommender-v2-ui-v2-design.md`
(사용자 승인 완료 — Part 1 추천 로직 v2, Part 2 카탈로그 UI v2, 결정 근거 포함)

1. superpowers:writing-plans로 구현 플랜 작성 → 사용자 승인.
2. 구현: Part 1(brain, TDD) → Part 2(UI, dev 시각 검증) → 통합 스모크 → 재배포.
3. 스펙의 "구현 순서 권고" 절 참조. 기존 테스트 55개 회귀 금지.

## 환경·절차 (실측 노하우)

- Rust 툴체인: `source "$HOME/.cargo/env"` 필수. tauri-cli 2.11.4.
- 빌드: `cd shell/src-tauri && cargo tauri build` (~2분, run_in_background 권장).
- **재배포 절차**: `launchctl unload ~/Library/LaunchAgents/com.earendel.skills-companion.plist`
  → `rm -rf "/Applications/Skills Companion.app"` → 번들 `cp -R` → `launchctl load ...`
  → `pgrep -fl skills-companion`으로 단일 인스턴스 확인.
- dev 검증: `cargo tauri dev` (릴리스 인스턴스와 동시 폴링되므로 헷갈리면 한쪽 종료).
- 앱 stderr는 LaunchAgent 로그 파일에서 확인 가능 (open_revert 실패 등).

## 함정 (이번 세션에서 실제로 밟은 것)

- **cwd가 있는 셸에서 파일을 만들면 OMC 훅이 `.omc/` 상태 디렉터리를 그 cwd에
  생성한다.** `capabilities/` 안에 `.omc`가 생기면 tauri 빌드가
  "missing field identifier"로 실패한다 — capabilities/에는 capability JSON만 둘 것.
- **`newest_session()` 휴리스틱은 동시 세션이 많으면 오귀속한다** (활성화가 조종
  세션에 귀속된 사례 관측). 스펙 1.2가 이 한계를 명시적으로 수용함 — 고치려 들지 말 것.
- 되돌림 다이얼로그는 "그 플러그인을 쓰는 마지막 살아있는 세션"이 끝날 때만 뜬다
  (held 규칙, revert.py). 스모크 테스트 시 다른 세션이 물고 있으면 조용히 kept 처리.
- 다이얼로그 검증 시 가짜 leak: `stores.ledger_add('<fake-sid>', '<꺼진 plugin>')`
  → transcript 없는 sid는 즉시 leak → 20초 내 다이얼로그. 끝나면 ledger 정리 확인.

## 절대 규칙 (스펙 C9/C12 — 변함없음, 서브에이전트에게도 전파)

앱/테스트/실행자 모두 다음 파일을 **절대 쓰지 않는다**:
`~/.claude.json`(직접) · `installed_plugins.json` · CLAUDE.md · MEMORY.md ·
앱 소유가 아닌 훅(특히 `korean-law-key-sync.py`).
MCP 변경은 `claude mcp remove/add-json -s user` 서브프로세스만.
`~/.claude/settings.json` 쓰기는 항상 앱 CLI 경유(atomic + 타임스탬프 백업).
brain은 stdlib 전용 유지(외부 의존성 도입 금지). UI는 외부 리소스 0(CSP).

## 문서

- 신규 스펙: `docs/superpowers/specs/2026-07-06-recommender-v2-ui-v2-design.md`
- 원 스펙(C1~C13): `docs/superpowers/specs/2026-07-06-skills-companion-design.md`
- 완료된 플랜(참고): `docs/superpowers/plans/2026-07-06-skills-companion.md`
- UI 목업(로컬): `.superpowers/brainstorm/2649-1783305889/content/` —
  `catalog-combined.html`(구조 확정안), `visual-style.html`(스타일 B 확정)
