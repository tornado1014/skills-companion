# Skills Companion

정적 스킬 치트시트를 대체하는 상주 크로스플랫폼 트레이 앱.

## 무엇을 만드는가

Claude Code의 스킬/플러그인 카탈로그를 사이드바+검색+히어로 추천 구조로 보여주고,
활성 세션의 트랜스크립트·프로젝트 파일·활성화 이력에서 **하이브리드**(평소 로컬
스코어링, 대화 축적 시 세션당 ≤2회 haiku 리파인)로 추천을 뽑아내며, 비활성
플러그인을 원클릭으로 활성화하고 세션 종료 시 정책에 따라 되돌리는 트레이
앱입니다. 첫 실행 시 경량화 마법사와 컨텍스트 리포트를 제공합니다.

## 아키텍처

- **Python 두뇌** (`brain/`) — 모든 로직(스캔·추천·활성화·되돌림·상태 저장)을
  JSON-out CLI 뒤에 캡슐화. Python 3.9+ stdlib only, `SKILLS_COMPANION_CLAUDE_HOME`
  env 하나로 가짜 `~/.claude` 트리를 주입해 완전 단위 테스트 가능.
- **Tauri v2 셸** (`shell/`) — Rust로 트레이/메뉴/창/다이얼로그/클립보드/알림/
  macOS 자동타이핑만 담당하고, 두뇌를 서브프로세스로 호출. npm/node 불필요
  (정적 `ui/` + `withGlobalTauri`).
- **SessionEnd 훅** (`hooks/`) — 신호 파일만 떨어뜨리고, 상주 셸이 반응.

## 현재 상태

**v1 Task 20/20 + 추천 로직 v2·카탈로그 UI v2 완료** (2026-07-07 재배포).
Python 두뇌 테스트 87개 통과. 추천 v2: 조사 스트립 토큰화·프로젝트 코퍼스·
cwd별 활성화 이력·연속 블렌딩·haiku 리파인(세션당 ≤2회, 전면 폴백), 근거는
인간 가독 문자열(`"이 프로젝트에서 3회 사용"`, `"대화: 특허, 보정서"`).
UI v2: 사이드바+검색(⌘K)+히어로 추천+리스트 행, 모던 프로덕티비티 토큰
(라이트/다크). 이후 추가: 크로스플랫폼 Windows 포트(mari 상주), 트레이·창
제목에 추적 세션 이름 표시. `/Applications` 설치 + LaunchAgent 자동 시작 유지.

## 문서

- [HANDOFF.md](HANDOFF.md) — 세션 인수인계 스냅샷(환경 실측, 절대 규칙, 확인 게이트)
- [설계 스펙 v1](docs/superpowers/specs/2026-07-06-skills-companion-design.md) — 승인된 스펙, 제약 C1~C13
- [설계 스펙 v2](docs/superpowers/specs/2026-07-06-recommender-v2-ui-v2-design.md) — 추천 로직 v2 + UI v2
- [구현 플랜 v1](docs/superpowers/plans/2026-07-06-skills-companion.md) — 20 태스크 / 92 스텝 실행 플랜
- [구현 플랜 v2](docs/superpowers/plans/2026-07-06-recommender-v2-ui-v2.md) — 11 태스크 실행 플랜

## 테스트

```bash
cd brain && python3 -m pytest -q
```
