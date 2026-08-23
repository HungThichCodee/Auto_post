"""
tests/integration/test_pipeline_integration.py
Integration tests for multi-stage pipeline execution, error resilience, and knowledge base tracking.
"""

import argparse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.main import cmd_run, cmd_generate, cmd_post
from src.memory.knowledge_base import KnowledgeBase


@pytest.mark.asyncio
async def test_cmd_generate_dry_run(tmp_path: Path):
    """Verify cmd_generate execution with dry_run=True."""
    mock_rewriter = MagicMock()
    mock_rewriter.rewrite_content = AsyncMock(return_value={
        "content": "Nội dung hoạt hình 3D",
        "image_prompt": "A cute ant in a sunny forest",
        "summary": "Tóm tắt kiểm thử",
        "themes": ["kiến", "thiên nhiên"]
    })

    with patch("src.main.ContentRewriter", return_value=mock_rewriter):
        args = argparse.Namespace(
            niche="stories",
            platform="youtube",
            dry_run=True,
        )
        result = await cmd_generate(args, raw_content="Nội dung kiểm thử")
        assert result is not None
        assert result["content"] == "Nội dung hoạt hình 3D"
        assert result["image_path"] == ""  # Skipped in dry run


@pytest.mark.asyncio
async def test_cmd_post_dry_run():
    """Verify cmd_post execution with dry_run=True returns True without opening browser."""
    args = argparse.Namespace(
        platform="youtube",
        dry_run=True,
    )
    success = await cmd_post(args, content="Nội dung test", image_path="")
    assert success is True


@pytest.mark.asyncio
async def test_pipeline_anti_repetition_integration(tmp_path: Path):
    """Verify past themes from KnowledgeBase are passed into the AI generation step."""
    kb_path = tmp_path / "knowledge_base.md"
    kb = KnowledgeBase(filepath=str(kb_path))
    kb.append_entry("youtube", "stories", "Tập 1", ["khủng long", "tiền sử"])

    mock_rewriter = MagicMock()
    mock_rewriter.rewrite_content = AsyncMock(return_value={
        "content": "Tập mới về robot",
        "image_prompt": "A cute robot in space",
        "summary": "Tập 2 robot",
        "themes": ["robot"]
    })

    with patch("src.main.KnowledgeBase", return_value=kb):
        with patch("src.main.ContentRewriter", return_value=mock_rewriter):
            args = argparse.Namespace(
                niche="stories",
                platform="youtube",
                dry_run=True,
            )
            await cmd_generate(args)

            # Inspect call arguments to rewrite_content
            call_kwargs = mock_rewriter.rewrite_content.call_args[1]
            assert "khủng long" in call_kwargs["knowledge_history"]
            assert "khủng long" in call_kwargs["niche"]["avoid_themes"]


@pytest.mark.asyncio
async def test_pipeline_e2e_dry_run_run_command(tmp_path: Path):
    """Verify cmd_run executes full pipeline with dry_run=True and updates knowledge base."""
    kb_path = tmp_path / "knowledge_base.md"
    kb = KnowledgeBase(filepath=str(kb_path))

    with patch("src.main.KnowledgeBase", return_value=kb):
        with patch("src.main.cmd_scrape", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = []

            with patch("src.main.cmd_generate", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {
                    "content": "Nội dung hoàn chỉnh",
                    "image_prompt": "Prompt",
                    "summary": "Tóm tắt pipeline",
                    "themes": ["chú mèo", "phiêu lưu"]
                }

                with patch("src.main.cmd_post", new_callable=AsyncMock) as mock_post:
                    mock_post.return_value = True

                    args = argparse.Namespace(
                        platforms="youtube",
                        dry_run=True,
                    )
                    await cmd_run(args)

                    assert mock_gen.call_count == 1
                    assert mock_post.call_count == 1
                    assert kb.get_entry_count() >= 1
                    themes = kb.get_recent_themes()
                    assert "chú mèo" in themes
