from skills_companion import scanner


def _by_invoke(items):
    return {i["invoke"]: i for i in items}


def test_scan_personal_states(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    kipo = items["/patent-en-ko-kipo"]
    assert kipo["source"] == "personal" and kipo["plugin"] is None
    assert kipo["state"] == "silenced" and kipo["invocation"] == "manual"
    dm = items["/domain-modeling"]
    assert dm["state"] == "loaded" and dm["invocation"] == "auto"


def test_scan_includes_disabled_plugin_items(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    ua = items["/understand-anything:understand"]
    assert ua["source"] == "plugin"
    assert ua["plugin"] == "understand-anything@understand-anything"
    assert ua["state"] == "disabled" and ua["invocation"] == "auto"
    kl = items["/korean-law:research"]
    assert kl["state"] == "enabled" and kl["invocation"] == "command"
    assert kl["plugin"] == "korean-law@korean-law-marketplace"


def test_categorize_korean_keywords(claude_home):
    items = _by_invoke(scanner.scan()["items"])
    assert items["/patent-en-ko-kipo"]["category"] == "특허 · 번역"
