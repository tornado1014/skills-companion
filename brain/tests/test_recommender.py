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
