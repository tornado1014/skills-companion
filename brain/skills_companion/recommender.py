import math
import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "be", "this", "that", "it", "i", "you", "we",
    "need", "want", "please", "let", "use", "using", "make", "help",
}

BOOST_DISABLED = 1.5


def tokenize(text):
    text = text.lower()
    en = [t for t in re.findall(r"[a-z][a-z0-9_-]{1,}", text) if t not in STOPWORDS]
    bigrams = []
    for chunk in re.findall(r"[가-힣]{2,}", text):
        bigrams.extend(chunk[i:i + 2] for i in range(len(chunk) - 1))
    return en + bigrams


def _corpus(item):
    return set(tokenize(
        f"{item['invoke']} {item['name']} {item['desc']} {item['category']}"))


def recommend(items, signals, top_k=5, min_matches=2):
    query = Counter(tokenize(" ".join(
        signals.get("texts", []) + signals.get("tools", []))))
    if not query:
        return []
    corpora = [_corpus(i) for i in items]
    df = Counter()
    for c in corpora:
        df.update(c)
    n = max(len(items), 1)
    recs = []
    for item, corpus in zip(items, corpora):
        matched = [t for t in query if t in corpus]
        if len(matched) < min_matches:
            continue
        score = sum(query[t] * math.log(1 + n / df[t]) for t in matched)
        score /= math.sqrt(len(corpus) or 1)
        actionable = item["source"] == "plugin" and item["state"] == "disabled"
        if actionable:
            score *= BOOST_DISABLED
        recs.append({
            "item": item,
            "score": round(score, 4),
            "kind": "actionable" if actionable else "informational",
            "reasons": sorted(matched, key=lambda t: -query[t])[:5],
        })
    recs.sort(key=lambda r: -r["score"])
    return recs[:top_k]
