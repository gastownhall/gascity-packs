from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "gastown/agents/mayor/prompt.template.md"


def test_collision_guidance_is_proxy_safe():
    text = PROMPT.read_text()
    assert "Prefix collisions are fatal" in text
    assert "do not run" in text and "gc bd rename-prefix" in text
    assert "verified backup" in text
    assert "never delete or rewrite" in text

