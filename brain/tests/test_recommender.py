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
