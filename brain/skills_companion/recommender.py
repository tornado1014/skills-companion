import json
import math
import os
import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "be", "this", "that", "it", "i", "you", "we",
    "need", "want", "please", "let", "use", "using", "make", "help",
}

BOOST_DISABLED = 1.5

# 한글 어절 끝 조사 — 긴 것 먼저 매칭
_JOSA = sorted([
    "에서부터", "으로부터", "으로서", "으로써", "에게서", "까지", "부터",
    "처럼", "보다", "에서", "에게", "한테", "으로", "이나", "이라",
    "라도", "마저", "조차", "은", "는", "이", "가", "을", "를",
    "에", "의", "도", "만", "와", "과", "로",
], key=len, reverse=True)

# 어미·기능어 bigram 차단 세트 (스펙 1.4 초기 목록, 구현 중 확장 가능)
BIGRAM_STOP = {
    "니다", "습니", "세요", "하세", "어요", "예요", "해줘", "해서", "하는",
    "있는", "없는", "그리", "리고", "하지", "지만", "에서", "으로", "한다",
    "했다", "합니", "입니", "것을", "것이", "그것", "저것",
}


def _strip_josa(word):
    for j in _JOSA:
        if word.endswith(j) and len(word) - len(j) >= 2:
            return word[: -len(j)]
    return word


def tokenize_ex(text):
    text = text.lower()
    en = [t for t in re.findall(r"[a-z][a-z0-9_-]{1,}", text) if t not in STOPWORDS]
    tokens = list(en)
    visible = set(en)
    for chunk in re.findall(r"[가-힣]{2,}", text):
        stem = _strip_josa(chunk)
        if len(stem) >= 2:
            tokens.extend((stem, stem))          # 온전 토큰 2배 가중
            visible.add(stem)
        tokens.extend(b for b in (chunk[i:i + 2] for i in range(len(chunk) - 1))
                      if b not in BIGRAM_STOP)
    return {"tokens": tokens, "visible": visible}


def tokenize(text):
    return tokenize_ex(text)["tokens"]


_PROJECT_TEXT_FILES = ("CLAUDE.md", "README.md", "pyproject.toml")


def project_tokens(cwd, head_bytes=4096):
    if not cwd:
        return {"tokens": [], "visible": set()}
    parts = []
    for name in _PROJECT_TEXT_FILES:
        try:
            with open(os.path.join(cwd, name), encoding="utf-8",
                      errors="ignore") as f:
                parts.append(f.read(head_bytes))
        except OSError:
            continue
    try:
        with open(os.path.join(cwd, "package.json"), encoding="utf-8",
                  errors="ignore") as f:
            pkg = json.loads(f.read(head_bytes))
        parts.append(str(pkg.get("name", "")))
        parts.append(str(pkg.get("description", "")))
        parts.extend((pkg.get("dependencies") or {}).keys())
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    try:
        with open(os.path.join(cwd, "Cargo.toml"), encoding="utf-8",
                  errors="ignore") as f:
            for line in f.read(head_bytes).splitlines():
                if line.strip().startswith(("name", "description")):
                    parts.append(line)
    except OSError:
        pass
    return tokenize_ex(" ".join(p for p in parts if p))


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
