# HANDOFF — Skills Companion 구현 시작용

> 새 세션의 실행자에게: 이 문서는 설계 세션(2026-07-06)의 최종 상태 스냅샷이다.
> 스펙과 플랜이 이미 **완성·승인·커밋**되어 있다. 여기서 할 일은 플랜 실행뿐이다.

## 무엇을 만드는가 (한 줄)

정적 스킬 치트시트를 대체하는 **상주 크로스플랫폼 트레이 앱**: 다기준 카탈로그 +
무-AI 세션 추천 + 원클릭 플러그인 활성화(세션 스코프 되돌림) + 첫 실행 경량화
마법사 + 컨텍스트 리포트. Tauri v2 셸(Rust) + Python 두뇌(stdlib only).

## 문서 (이 순서로 읽기)

1. `docs/superpowers/plans/2026-07-06-skills-companion.md` — **실행할 플랜.**
   20 태스크 / 92 스텝, 태스크별 완전한 테스트·구현 코드 포함. Global Constraints
   섹션이 모든 태스크에 바인딩됨.
2. `docs/superpowers/specs/2026-07-06-skills-companion-design.md` — 승인된 스펙.
   **C1~C13 제약은 문서 검증 완료**된 플랫폼 사실 — 재조사 불필요, 위반 금지.

## 커밋 상태

- `e376b2c` 스펙 초판 → `aa5605e` 플랜(15태스크) → `a19b1fc` 증보(마법사·리포트,
  태스크 16~20). 소스 코드는 아직 없음 — Task 1부터 시작.

## 실행 방법 (사용자 확정)

- **superpowers:subagent-driven-development** — 태스크별 신선한 서브에이전트,
  태스크 간 리뷰. 플랜 순서(1→20)대로. Phase 4의 16~18은 brain-only라
  Phase 1+Task 14 뒤에 앞당겨도 됨(플랜에 명시).
- 태스크마다 커밋(메시지는 플랜에 있음).

## 환경 사실 (설계 세션에서 실측)

- Python 3.12.12 + pytest 9.0.1 ✓ (brain 테스트: `cd brain && python3 -m pytest -q`)
- **rustc/cargo 미설치** — Task 10 Step 1이 설치함(rustup + tauri-cli).
  cargo/tauri-cli 빌드는 수 분 소요 → **run_in_background**로.
- 테스트 격리 열쇠: `SKILLS_COMPANION_CLAUDE_HOME` env → 가짜 `~/.claude` 트리.
  테스트가 실제 `~/.claude`를 만지면 안 됨(fixture가 보장).

## 절대 규칙 (스펙 C9/C12 — 서브에이전트에게 반드시 전파)

앱/테스트/실행자 모두 다음 파일을 **절대 쓰지 않는다**:
`~/.claude.json` · `installed_plugins.json` · CLAUDE.md · MEMORY.md ·
앱 소유가 아닌 훅. MCP 변경은 `claude mcp remove/add-json` 서브프로세스만.
`~/.claude/settings.json` 쓰기는 항상 atomic + 타임스탬프 백업.

## 사용자 확인이 필요한 스텝 (자동 진행 금지)

- **Task 15 전체** (실제 `~/.claude` 마이그레이션: 훅 설치, /myskills 재배선,
  치트시트 은퇴, LaunchAgent) — 현재 실환경에는 치트시트+SessionStart 훅이
  **가동 중**(메모리 `claude-startup-context-tuning` 참고). Task 15 전까지 건드리지 말 것.
- 각 태스크의 "Manual verify" 스텝 중 실제 settings.json을 바꾸는 것
  (T12 Step 2의 활성화 실험 등) — 실험 후 반드시 원복(방법 명시돼 있음).

## 알려진 드리프트 리스크 (플랜 Self-Review에 명시)

- Tauri v2 Rust API 이름(T10/T11/T20) — 컴파일러 안내대로 수정 허용.
  brain JSON 계약이 안정 인터페이스이므로 셸 수정이 두뇌에 영향 없음.
- `claude mcp remove/add-json` 플래그 — T17 테스트는 fake runner라 안전.
  실사용 전 `claude mcp --help`로 1회 확인 권장.

## 설계 결정 요약 (왜 이렇게인지)

- 훅은 신호만, 상주 앱이 질문/되돌림 (C4: SessionEnd는 비대화형, C5: 불신뢰 → leak sweep)
- 활성화 완료는 클립보드 `/reload-plugins` + 맥 한정 자동타이핑 (C1~C3)
- 활성화/되돌림 = 플러그인 전용; 스킬 가시성 변경은 마법사(경량화)만
- 되돌림 정책: 전역 `ask` + 플러그인별 기억
- 마법사 기본: 스킬 전부 '수동' 체크(해제=자동 유지), 플러그인은 옵트인,
  MCP 보관/에이전트 보관은 접힌 '고급'
- 로컬→전역: 스킬만 이동(충돌 차단), 프로젝트 플러그인은 읽기전용 표시 (C13)
