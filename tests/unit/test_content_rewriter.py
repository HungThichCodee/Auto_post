"""
tests/unit/test_content_rewriter.py
Unit tests for ContentRewriter Gemini story generation, prompts, JSON parsing, and fallbacks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.ai_pipeline.content_rewriter import ContentRewriter


def test_init_without_api_key(monkeypatch):
    """Verify ContentRewriter initializes cleanly without API key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    rewriter = ContentRewriter(api_key=None)
    assert rewriter.api_key is None


def test_build_system_prompt_rules():
    """Verify system prompt enforces Vietnamese text and English image prompts."""
    rewriter = ContentRewriter(api_key="mock_key")
    niche = {
        "name": "stories",
        "description": "Dramatic stories with lessons",
        "tone": "dramatic"
    }
    prompt = rewriter._build_system_prompt(niche, platform="youtube")
    assert "VIETNAMESE" in prompt
    assert "image_prompt" in prompt
    assert "English" in prompt
    assert "JSON format" in prompt
    assert "'content'" in prompt
    assert "'image_prompt'" in prompt


def test_build_user_prompt_injects_anti_repetition():
    """Verify user prompt injects past knowledge history to avoid repetition."""
    rewriter = ContentRewriter(api_key="mock_key")
    history = "- **Themes**: mèo cam, phiêu lưu rừng rậm"
    raw_content = "Video nguồn về các loài động vật hoang dã."

    user_prompt = rewriter._build_user_prompt(raw_content, knowledge_history=history)
    assert "Previous Knowledge/History (Avoid repeating these ideas/themes exactly)" in user_prompt
    assert "mèo cam, phiêu lưu rừng rậm" in user_prompt
    assert "Video nguồn về các loài động vật hoang dã." in user_prompt


def test_parse_response_clean_json():
    """Verify parsing clean JSON string into structured dictionary."""
    rewriter = ContentRewriter(api_key="mock_key")
    json_payload = (
        '{\n'
        '  "content": "Nội dung câu chuyện tiếng Việt.",\n'
        '  "image_prompt": "A cute ant in a sunny forest, 3D Pixar style",\n'
        '  "summary": "Tóm tắt câu chuyện chú kiến.",\n'
        '  "themes": ["kiến", "thiên nhiên"]\n'
        '}'
    )
    parsed = rewriter._parse_response(json_payload)
    assert parsed["content"] == "Nội dung câu chuyện tiếng Việt."
    assert parsed["image_prompt"] == "A cute ant in a sunny forest, 3D Pixar style"
    assert parsed["summary"] == "Tóm tắt câu chuyện chú kiến."
    assert parsed["themes"] == ["kiến", "thiên nhiên"]


def test_parse_response_strips_markdown_code_fences():
    """Verify parser strips ```json and ``` codeblock fences."""
    rewriter = ContentRewriter(api_key="mock_key")
    fenced_json = (
        '```json\n'
        '{\n'
        '  "content": "Câu chuyện hoạt hình",\n'
        '  "image_prompt": "3D render of a cat",\n'
        '  "summary": "Tóm tắt",\n'
        '  "themes": ["mèo"]\n'
        '}\n'
        '```'
    )
    parsed = rewriter._parse_response(fenced_json)
    assert parsed["content"] == "Câu chuyện hoạt hình"
    assert parsed["image_prompt"] == "3D render of a cat"
    assert parsed["themes"] == ["mèo"]


def test_parse_response_malformed_json_fallback():
    """Verify parser returns structured fallback dictionary on malformed JSON."""
    rewriter = ContentRewriter(api_key="mock_key")
    malformed = "Đây là văn bản tự do không theo định dạng JSON."
    parsed = rewriter._parse_response(malformed)

    assert parsed["content"] == malformed
    assert "cinematic lighting" in parsed["image_prompt"]
    assert isinstance(parsed["themes"], list)


@pytest.mark.asyncio
async def test_rewrite_content_async_success():
    """Verify full rewrite_content workflow with mocked Gemini model."""
    rewriter = ContentRewriter(api_key="mock_key")
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{\n'
        '  "content": "Nội dung câu chuyện kiểm thử",\n'
        '  "image_prompt": "A heroic cat warrior with glowing armor",\n'
        '  "summary": "Tóm tắt mèo chiến binh",\n'
        '  "themes": ["chiến binh", "mèo"]\n'
        '}'
    )
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    rewriter.model = mock_model

    result = await rewriter.rewrite_content(
        raw_content="Nội dung nguồn",
        niche={"name": "stories", "description": "Epic stories", "tone": "epic"},
        knowledge_history="Theme cũ: chó, chim",
        platform="youtube",
    )

    assert result["content"] == "Nội dung câu chuyện kiểm thử"
    assert result["image_prompt"] == "A heroic cat warrior with glowing armor"
    assert result["themes"] == ["chiến binh", "mèo"]


@pytest.mark.asyncio
async def test_rewrite_content_handles_api_exception():
    """Verify rewrite_content catches Gemini exceptions and returns safe empty dict."""
    rewriter = ContentRewriter(api_key="mock_key")
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(side_effect=Exception("429 Resource Exhausted"))
    rewriter.model = mock_model

    result = await rewriter.rewrite_content(
        raw_content="Nội dung nguồn",
        niche={"name": "stories"},
    )

    assert result["content"] == ""
    assert result["image_prompt"] == ""
    assert result["themes"] == []
