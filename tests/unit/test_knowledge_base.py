"""
tests/unit/test_knowledge_base.py
Unit tests for KnowledgeBase long-term memory management and anti-repetition.
"""

from pathlib import Path
from src.memory.knowledge_base import KnowledgeBase


def test_kb_init_creates_file_with_header(tmp_path: Path):
    """Verify KnowledgeBase auto-creates markdown file with header."""
    kb_path = tmp_path / "sub_dir" / "kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))
    assert kb_path.exists()
    content = kb_path.read_text(encoding="utf-8")
    assert content.startswith("# Knowledge Base\n\n")


def test_kb_read_history_empty_and_populated(tmp_path: Path):
    """Verify read_history on fresh and non-existent files."""
    kb_path = tmp_path / "test_kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))
    assert "# Knowledge Base" in kb.read_history()

    # Non-existent file
    kb_missing = KnowledgeBase(filepath=str(tmp_path / "non_existent.md"))
    # Manually remove if created
    (tmp_path / "non_existent.md").unlink()
    assert kb_missing.read_history() == ""


def test_kb_append_entry_formatting(tmp_path: Path):
    """Verify markdown formatting of appended entries."""
    kb_path = tmp_path / "test_kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))

    kb.append_entry(
        platform="youtube",
        niche="stories",
        content_summary="Hành trình của chú kiến tí hon",
        themes=["kiến", "lòng dũng cảm", "khu vườn"],
        post_url="https://youtu.be/test_video_1",
    )

    content = kb.read_history()
    assert "### " in content
    assert "| youtube | stories" in content
    assert "- **Summary**: Hành trình của chú kiến tí hon" in content
    assert "- **Themes**: kiến, lòng dũng cảm, khu vườn" in content
    assert "- **Post URL**: https://youtu.be/test_video_1" in content
    assert "---\n\n" in content


def test_kb_get_entry_count(tmp_path: Path):
    """Verify entry count calculation matches number of separators."""
    kb_path = tmp_path / "test_kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))
    assert kb.get_entry_count() == 0

    for i in range(5):
        kb.append_entry(
            platform="youtube",
            niche="stories",
            content_summary=f"Tập {i+1}",
            themes=[f"theme_{i+1}"],
        )

    assert kb.get_entry_count() == 5


def test_kb_get_recent_themes_token_extraction(tmp_path: Path):
    """Verify extraction and whitespace stripping of theme tokens."""
    kb_path = tmp_path / "test_kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))

    kb.append_entry("youtube", "stories", "Summary 1", ["mèo cam", " rừng rậm "])
    kb.append_entry("youtube", "stories", "Summary 2", [" chú chó ", "tình bạn"])

    themes = kb.get_recent_themes(n=10)
    assert "mèo cam" in themes
    assert "rừng rậm" in themes
    assert "chú chó" in themes
    assert "tình bạn" in themes


def test_kb_get_recent_themes_window_limit(tmp_path: Path):
    """Verify recent themes extraction respects the window size N."""
    kb_path = tmp_path / "test_kb.md"
    kb = KnowledgeBase(filepath=str(kb_path))

    # Append 10 entries with distinct themes
    for i in range(1, 11):
        kb.append_entry("youtube", "stories", f"Entry {i}", [f"unique_theme_{i}"])

    # Query only last 3 entries
    recent_themes = kb.get_recent_themes(n=3)
    assert len(recent_themes) == 3
    assert "unique_theme_8" in recent_themes
    assert "unique_theme_9" in recent_themes
    assert "unique_theme_10" in recent_themes
    assert "unique_theme_1" not in recent_themes


def test_kb_corrupt_entry_resilience(tmp_path: Path):
    """Verify KnowledgeBase handles malformed or empty files safely."""
    kb_path = tmp_path / "corrupt_kb.md"
    kb_path.write_text("random garbage\n---\nno themes line here\n---\n", encoding="utf-8")
    kb = KnowledgeBase(filepath=str(kb_path))

    themes = kb.get_recent_themes(n=5)
    assert isinstance(themes, list)
    assert kb.get_entry_count() == 2
