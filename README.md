# Skills Companion

정적 스킬 치트시트를 대체하는 상주 크로스플랫폼 트레이 앱.

## 무엇을 만드는가

Claude Code의 스킬/플러그인 카탈로그를 다기준(facet)으로 보여주고, 활성 세션의
트랜스크립트에서 **AI 없이** 추천을 뽑아내며, 비활성 플러그인을 원클릭으로
활성화하고 세션 종료 시 정책에 따라 되돌리는 트레이 앱입니다. 첫 실행 시
경량화 마법사와 컨텍스트 리포트를 제공합니다.

## 아키텍처

- **Python 두뇌** (`brain/`) — 모든 로직(스캔·추천·활성화·되돌림·상태 저장)을
  JSON-out CLI 뒤에 캡슐화. Python 3.9+ stdlib only, `SKILLS_COMPANION_CLAUDE_HOME`
  env 하나로 가짜 `~/.claude` 트리를 주입해 완전 단위 테스트 가능.
- **Tauri v2 셸** (`shell/`) — Rust로 트레이/메뉴/창/다이얼로그/클립보드/알림/
  macOS 자동타이핑만 담당하고, 두뇌를 서브프로세스로 호출. npm/node 불필요
  (정적 `ui/` + `withGlobalTauri`).
- **SessionEnd 훅** (`hooks/`) — 신호 파일만 떨어뜨리고, 상주 셸이 반응.

## 현재 상태

구현 진행 중 — **Task 19/20 완료** (Task 15 제외 전부): Python 두뇌(테스트 55개 통과), SessionEnd 훅+설치기, Tauri 셸(트레이·brain 브리지·폴 루프·카탈로그·되돌림 다이얼로그·경량화 마법사·컨텍스트 리포트) 빌드 성공. 남은 것: Task 15 실환경 마이그레이션(사용자 확인 게이트) + 수동 시각 검증.

## 문서

- [HANDOFF.md](HANDOFF.md) — 세션 인수인계 스냅샷(환경 실측, 절대 규칙, 확인 게이트)
- [설계 스펙](docs/superpowers/specs/2026-07-06-skills-companion-design.md) — 승인된 스펙, 제약 C1~C13
- [구현 플랜](docs/superpowers/plans/2026-07-06-skills-companion.md) — 20 태스크 / 92 스텝 실행 플랜

## 테스트

```bash
cd brain && python3 -m pytest -q
```
