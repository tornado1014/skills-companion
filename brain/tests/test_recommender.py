import json

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
    assert any(("codebase" in r) or ("knowledge" in r) for r in top["reasons"])


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
    assert "특허번역" in joined            # 온전 토큰이 노출됨
    # bigram·어미 조각이 단독 근거로 나열되지 않음 ("특허번역" 부분열은 무관)
    listed = [t for r in kipo["reasons"] if r.startswith("대화: ")
              for t in r[len("대화: "):].split(", ")]
    assert "허번" not in listed and "니다" not in listed and "합니" not in listed
