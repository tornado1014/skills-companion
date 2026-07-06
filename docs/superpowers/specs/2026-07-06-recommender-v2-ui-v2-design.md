# Skills Companion — 추천 로직 v2 + 카탈로그 UI v2 설계

- 날짜: 2026-07-06 (Task 15 실환경 마이그레이션 완료 직후)
- 상태: **사용자 승인 완료** (구조·스타일은 비주얼 목업으로 확정)
- 선행 스펙: `2026-07-06-skills-companion-design.md` — 제약 C1~C13 전부 계승, 재조사 금지
- 목업 아카이브: `.superpowers/brainstorm/2649-1783305889/content/` (git 미추적, 로컬 참고용)

## 배경 / 문제

1. **추천 근거가 무의미한 조각**: `recommender.tokenize()`가 한글을 무조건 2글자
   bigram으로 쪼개 "니다·스트·이트" 같은 어미·조사 조각이 신호와 UI 근거로 노출.
   한글 불용어 필터 없음. cwd(프로젝트) 신호 미사용. 세션 초반/후반 로직 동일.
2. **카탈로그 UI가 투박**: 구 치트시트 HTML과 대동소이한 카드 나열. 설정·리포트가
   페이지 하단에 적체. 시각 위계·밀도·완성도 부족.

## 결정 요약

| 결정 | 선택 | 비고 |
|---|---|---|
| 종합 판단 수단 | **하이브리드** — 평소 로컬 스코어링, 대화 축적 시 세션당 ≤2회 haiku | 20초 폴링마다 LLM 불가 |
| 프로젝트 신호 | **이력 + 파일 지표 둘 다** | cwd별 활성화 이력 + CLAUDE.md 등 |
| 단계 메커니즘 | **연속 블렌딩(접근 B)** | 하드 3단계 상태기계 기각(절벽 효과) |
| UI 구조 | **사이드바+리스트 행 + 히어로 추천** (B+C 조합) | 목업 승인 |
| UI 스타일 | **모던 프로덕티비티** (Linear/Raycast 계열) | 목업 승인 |

---

# Part 1 — 추천 로직 v2 (brain)

## 1.1 신호 수집 확장 — `transcripts.extract_signals`

반환 dict에 추가 (기존 `texts`/`tools` 유지, 하위호환):

- `cwd`: transcript에서 마지막으로 관측된 `cwd` 필드 값 (없으면 `""`)
- `user_texts`: user 턴 텍스트만 (tail 범위 내 최근 `last_n`개)
- `user_msg_count`: tail 범위 내 user 턴 수 (블렌딩 가중치와 LLM 트리거의 입력)

## 1.2 활성화 이력 스토어 — `stores.py`

- 파일: `state/activation-history.json` (앱 소유 상태 — settings.json 아님, C9/C12 무관)
- 스키마: `{cwd: {plugin_key: {"count": int, "last_ts": float}}}`
- 기록 시점: `activation.activate()` 성공 시. cwd는 `cli.py`의 activate 분기가
  `extract_signals`로 추출해 전달 (activate의 cwd 파라미터는 이미 존재, 연결만 누락).
- **알려진 한계(기록)**: 세션 귀속은 `newest_session()` 휴리스틱 — 동시 세션이 많으면
  cwd가 다른 세션의 것일 수 있음. Task 15 스모크에서 실제 관측됨. 이번 범위에서는
  수용하고, 이력은 count 누적이라 소수 오귀속에 강건함.

## 1.3 프로젝트 코퍼스

- cwd에서 존재하는 것만 읽기 (각 앞 4KB, OSError 무시):
  `CLAUDE.md`, `README.md`, `package.json`(name/description/dependencies 키 이름),
  `pyproject.toml`, `Cargo.toml`(name/description 줄)
- 토큰화(1.4)하여 항목 코퍼스와 매칭. 캐시 없음(폴링당 재독 — 수 KB, 무부담).

## 1.4 토큰화 개선 — `recommender.tokenize`

- **조사 스트립**: 한글 어절 끝의 조사 목록(을/를/이/가/은/는/에/에서/으로/로/과/와/
  의/도/만/까지/부터/처럼/보다 등) 제거 후 어간이 2자 이상이면 **온전 토큰**으로 추가.
  온전 토큰 가중 2배 (Counter에 2회 계상).
- **한글 bigram 불용어**: bigram은 유지하되 차단 세트 도입 — 초기 목록:
  니다/습니/세요/하세/어요/예요/해줘/해서/하는/있는/없는/그리/리고/하지/지만/
  에서/으로/한다/했다/합니/입니/것을/것이/그것/저것 (구현 중 확장 가능, 상수로 관리)
- **근거 노출 규칙**: `reasons` 후보는 온전 토큰·영어 토큰만 — bigram은 점수에만
  기여하고 사용자에게 보이지 않는다.

## 1.5 연속 블렌딩 스코어 — `recommender.recommend`

```
w_conv = min(1.0, user_msg_count / 8)
w_proj = 1 - w_conv
score  = w_conv * conv_score          # 기존 TF-IDF식, 개선 토큰 입력
       + w_proj * (proj_score + hist_boost)
hist_boost = log(1 + history_count(cwd, plugin)) * H   # H 상수, 기본 2.0
```

- `min_matches=2` 게이트는 **conv_score에만** 적용. 이력 부스트 항목은 매칭 0이어도
  추천 가능 (근거: "이 프로젝트에서 N회 사용").
- BOOST_DISABLED(1.5) 및 actionable/informational 판정은 기존 유지.
- 출력 스키마 유지 + `reasons`는 인간 가독 문자열(1.7) 배열로 의미 변경
  (형태는 동일한 `list[str]` — UI/셸 하위호환).

## 1.6 LLM 리파인 — 신규 `llm_refine.py`

- **트리거**: `user_msg_count ≥ 10`에서 최초 1회, 이후 캐시 시점 대비 +15 메시지면
  1회 더 — **세션당 최대 2회**.
- **호출**: `subprocess.run(["claude", "-p", prompt, "--model", "haiku"], timeout=30)`
  (runner 주입 가능하게 설계 — 테스트에서 mock).
  입력 프롬프트: 최근 user 텍스트 15개(각 500자 절단) + 로컬 상위 후보 12개
  (invoke + desc 1줄). 요구 출력: JSON `[{"invoke": str, "reason": str}]` 최대 3개.
- **검증**: 출력 파싱 실패·후보 목록 밖 invoke는 버림.
- **캐시**: `state/llm-recs/<session_id>.json` = `{ts, msg_count, recs, failed}`.
  실패 시 `failed: true` 마킹 — 같은 트리거 창에서 재시도 1회만.
- **병합**: 캐시가 유효하면(같은 세션) LLM 추천을 최상위 고정, `reasons=[모델 이유]`,
  kind 판정은 기존 규칙(비활성 플러그인=actionable). 로컬 추천이 뒤를 채움(중복 제거).
- **폴백**: CLI 부재·타임아웃·불량 출력 → 로컬 추천만. 추천 기능은 절대 죽지 않는다.
- **프라이버시**: 대화 일부가 claude CLI로 전송됨 — 이미 Anthropic에 있는 대화
  데이터이므로 신규 노출 아님 (명시적 수용).

## 1.7 근거(reasons) 문자열 규약

- 이력: `"이 프로젝트에서 3회 사용"`
- 프로젝트 파일: `"프로젝트: pdf, merge"` (매칭 온전 토큰 상위 ≤3)
- 대화: `"대화: 특허, 보정서"` (〃)
- LLM: 모델이 준 한 줄 이유 그대로 (≤80자 절단)

## 1.8 테스트 (pytest, 기존 55개 회귀 금지)

- tokenize: 어미 bigram 차단, 조사 스트립·온전 토큰 가중, reasons에 bigram 부재
- history: activate→기록 누적, cwd별 부스트 반영
- blending: user_msg_count 0/4/20에서 상위 항목이 이력→혼합→대화 순으로 이동
- llm_refine: mock runner로 성공/타임아웃/불량 JSON/후보 밖 invoke/재시도 상한
- extract_signals: cwd·user_texts·user_msg_count 추출

---

# Part 2 — 카탈로그 UI v2 (shell/ui)

## 2.1 구조 (목업 확정안)

- **좌측 사이드바** (고정 168px): 앱 타이틀 / `✦ 이 세션`(기본 선택) / 카테고리별
  항목+카운트 / `비활성 플러그인` / 구분선 / `📊 컨텍스트 리포트` / `⚙️ 설정`.
  설정·리포트는 사이드바 목적지로 승격 — 메인 영역을 교체 렌더링.
- **상단 검색바**: 이름·설명·명령 통합 검색, **⌘K로 포커스**. 새로고침 버튼.
- **히어로 추천 영역**: `✦ 이 세션` 뷰 상단. 추천 ≤3개, 각 행 = invoke + 인간 가독
  근거 + 액션(활성화/복사). 추천 없으면 영역 자체를 렌더링하지 않음.
- **리스트 행**: 카드 그리드 → 밀도 높은 행. 행 = 상태 점(활성 초록·비활성 빨강·
  수동 파랑·로딩중 주황) + `invoke` 코드 + 한 줄 설명(ellipsis) + 우측 액션 버튼.
  그룹 헤더는 소문자 대비 대문자 스타일 라벨(11px, letter-spacing).
- 기존 그룹/필터/검색 로직(render(), GLBL 등)은 유지하되 렌더 출력만 새 구조로.

## 2.2 스타일 토큰 (모던 프로덕티비티)

- 다크(기본): bg `#101014`, 카드 `#17171d`, 보더 `#26262e`, 텍스트 `#e2e2e6`,
  뮤트 `#9a9aa4`, **액센트 `#7c5dfa`** (호버 밝힘 `#a48bff`)
- 라이트: bg `#fafafc`, 카드 `#ffffff`, 보더 `#e4e4ea`, 텍스트 `#1a1a1f`,
  액센트 동일 계열 — `prefers-color-scheme` 미디어쿼리, 기존 CSS 변수 체계 유지
- 히어로: 액센트 그라디언트 배경 + `box-shadow: 0 0 24px rgba(124,93,250,.15)` 글로우
- 상태 점: 다크에서 `box-shadow: 0 0 6px currentColor` 미광
- 폰트: **CSP상 외부 로드 불가** → 시스템 스택.
  본문 `-apple-system, "Pretendard", "Apple SD Gothic Neo", sans-serif`,
  코드 `ui-monospace, "SF Mono", Menlo, monospace`. 외부 리소스 0 유지.
- 라운딩: 컨테이너 10px, 행 7px, 버튼 6px. 트랜지션 120ms ease.

## 2.3 일관성 리스타일

`revert.html`·`wizard.html`도 같은 토큰(색·라운딩·버튼·폰트)으로 교체. 로직 무변경.

## 2.4 무변경 (비범위)

- `main.rs` 로직·트레이 메뉴·brain CLI 스키마 (recommend 출력 형태 동일)
- 형태소 분석기 등 외부 의존성 도입 없음 (brain은 stdlib 유지)
- 창 크기(980×720)·tauri.conf.json·CSP 정책

## 2.5 검증

- brain 쪽은 pytest. UI는 `cargo tauri dev`로 수동 시각 검증(라이트/다크 모두) —
  카탈로그 렌더·검색·⌘K·그룹 전환·활성화/복사·설정/리포트 뷰 전환·히어로 근거 표시.
- 기존 기능 회귀 체크리스트: 활성화 흐름(클립보드+알림), 되돌림 다이얼로그 열림/닫힘,
  마법사 열기.

## 구현 순서 권고 (플랜 작성 시 참고)

Part 1(brain, TDD 가능) → Part 2(UI, 시각 검증) → 통합 스모크(dev) → 릴리스 빌드·
재설치·LaunchAgent 재기동(HANDOFF의 재배포 절차).
