import re

from . import paths, stores

CATEGORY_RULES = [
    ("특허 · 번역", ["patent", "kipo", "welo", "oa-", "invention", "translat",
                    "gl-postedit", "globallink", "특허", "번역", "명세서"]),
    ("카카오 · 콘텐츠", ["kakao", "카톡", "chat-summary", "briefing", "curate",
                       "needs", "digest", "카카오"]),
    ("소셜 · 스카우팅", ["linkedin", "twitter", "threads", "slack", "scout"]),
    ("노트 · 지식", ["obsidian", "vault", "matjip", "graphify", "daily-bible",
                   "care-group", "볼트", "노트", "묵상"]),
    ("사고 · 프로세스", ["grill", "domain-modeling", "decision", "brainstorm",
                      "plan", "critic", "handoff", "teach", "triage"]),
    ("QA · 자동화", ["browse", "dogfood", "qa", "agent-browser", "electron",
                   "macos", "ssh", "gstack"]),
    ("문서 · 시각화", ["interactive-learning", "pptx", "metrics", "retro", "hwp",
                    "defuddle", "dashboard", "visualiz", "학습"]),
    ("시스템 · 설정", ["skill", "setup", "ship", "review", "launcher", "transplant"]),
]


def parse_frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None, None
    return _scalar(m.group(1), "name"), _scalar(m.group(1), "description")


def _scalar(fm, key):
    mb = re.search(rf"^{key}:\s*[>|]\s*\n((?:[ \t]+.*\n?)+)", fm, re.M)
    if mb:
        return " ".join(x.strip() for x in mb.group(1).splitlines() if x.strip())
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    if not m:
        return None
    val = m.group(1).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        val = val[1:-1]
    return val.strip()


def categorize(name, desc):
    hay = f"{name} {desc}".lower()
    for cat, kws in CATEGORY_RULES:
        if any(kw in hay for kw in kws):
            return cat
    return "기타"


def find_plugin_root(pname):
    cache = paths.plugin_cache_dir()
    if not cache.is_dir():
        return None
    for mk in sorted(cache.iterdir()):
        cand = mk / pname
        if cand.is_dir():
            vers = sorted(v for v in cand.iterdir() if v.is_dir())
            if vers:
                return vers[-1]
    return None


def scan():
    settings = stores.read_json(paths.settings_path(), {})
    overrides = settings.get("skillOverrides", {})
    enabled = settings.get("enabledPlugins", {})
    items = []
    if paths.skills_dir().is_dir():
        for sk in sorted(paths.skills_dir().glob("*/SKILL.md")):
            folder = sk.parent.name
            name, desc = parse_frontmatter(sk)
            name, desc = name or folder, desc or ""
            silenced = overrides.get(name) or overrides.get(folder)
            items.append({
                "invoke": f"/{folder}", "name": name, "desc": desc,
                "source": "personal", "plugin": None,
                "category": categorize(f"{folder} {name}", desc),
                "state": "silenced" if silenced else "loaded",
                "invocation": "manual" if silenced else "auto",
            })
    for key, on in enabled.items():
        pname = key.split("@", 1)[0]
        root = find_plugin_root(pname)
        if root is None:
            continue
        state = "enabled" if on else "disabled"
        for sk in sorted(root.glob("skills/**/SKILL.md")):
            n, ds = parse_frontmatter(sk)
            if not n:
                continue
            items.append({"invoke": f"/{pname}:{n}", "name": n, "desc": ds or "",
                          "source": "plugin", "plugin": key, "category": pname,
                          "state": state, "invocation": "auto"})
        for cmd in sorted(root.glob("commands/**/*.md")):
            n, ds = parse_frontmatter(cmd)
            n = n or cmd.stem
            items.append({"invoke": f"/{pname}:{n}", "name": n,
                          "desc": ds or "(command)", "source": "plugin",
                          "plugin": key, "category": pname,
                          "state": state, "invocation": "command"})
    return {"items": items}
