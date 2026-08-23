"""
tests/test_ai_pipeline.py
Comprehensive unit and integration test suite for Milestone M2 AI Pipeline:
- ContentRewriter (Gemini 2.0 Flash multi-scene story generation, prompts, JSON parsing & fallbacks)
- ImageGenerator (Pollinations.ai visual consistency, aspect ratios, PIL verification & retries)
- AudioGenerator (Edge-TTS Southern Vietnamese synthesis, text normalization & duration tracking)
- End-to-End M2 Pipeline Integration (cross-component contracts & dynamic aspect ratio resolution)
"""

import asyncio
import io
import json
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from PIL import Image

from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import (
    ImageGenerator,
    compose_scene_prompt,
    get_dimensions_for_aspect_ratio,
)
from src.ai_pipeline.audio_generator import AudioGenerator
from src.memory.knowledge_base import KnowledgeBase
from src.models.pipeline_models import Scene, StoryScript
from tests.conftest import (
    MockEdgeTTSCommunicate,
    MockGeminiModel,
    create_synthetic_mp3,
    create_synthetic_png,
    create_synthetic_png_bytes,
)


# ============================================================================
# Section 1: ContentRewriter Tests (Gemini 2.0 Flash)
# ============================================================================

class TestContentRewriter:
    """Test suite for ContentRewriter."""

    def test_init_with_and_without_api_key(self, monkeypatch):
        """Verify initialization with explicit API key and environment fallback."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        rewriter_no_key = ContentRewriter(api_key=None)
        assert rewriter_no_key.api_key is None
        assert rewriter_no_key.model_name == "gemini-2.0-flash"

        monkeypatch.setenv("GEMINI_API_KEY", "env_mock_key")
        rewriter_env = ContentRewriter()
        assert rewriter_env.api_key == "env_mock_key"

        rewriter_explicit = ContentRewriter(api_key="explicit_key", model_name="gemini-2.0-flash")
        assert rewriter_explicit.api_key == "explicit_key"
        assert rewriter_explicit.model_name == "gemini-2.0-flash"

    def test_extract_past_themes_from_file(self, tmp_path: Path):
        """Verify extraction of past themes from knowledge base markdown file."""
        kb_file = tmp_path / "knowledge_base.md"
        kb = KnowledgeBase(filepath=str(kb_file))
        kb.append_entry("youtube", "stories", "Summary 1", ["khủng long", "tiền sử"])
        kb.append_entry("youtube", "stories", "Summary 2", ["mèo cam", "vũ trụ"])

        themes = ContentRewriter.extract_past_themes_from_file(str(kb_file))
        assert "khủng long" in themes
        assert "tiền sử" in themes
        assert "mèo cam" in themes
        assert "vũ trụ" in themes

        # Non-existent file returns empty list without raising
        non_existent_themes = ContentRewriter.extract_past_themes_from_file(str(tmp_path / "missing.md"))
        assert non_existent_themes == []

    def test_build_story_system_prompt_structure(self):
        """Verify story system prompt enforces Vietnamese narration, English prompts, and 3-6 scenes."""
        rewriter = ContentRewriter(api_key="mock_key")
        prompt = rewriter._build_story_system_prompt("stories")
        assert "VIETNAMESE" in prompt
        assert "ENGLISH" in prompt
        assert "art_style" in prompt
        assert "character_style" in prompt
        assert "narration_text_vi" in prompt
        assert "image_prompt_en" in prompt
        assert "3 to 6 sequential SCENES" in prompt
        assert "JSON SCHEMA" in prompt

    def test_build_story_user_prompt_with_and_without_themes(self):
        """Verify user prompt injects anti-repetition past themes constraint and source material."""
        rewriter = ContentRewriter(api_key="mock_key")

        # Without past themes
        prompt_no_themes = rewriter._build_story_user_prompt("Video về loài kiến nhỏ")
        assert "[SOURCE INSPIRATION MATERIAL]" in prompt_no_themes
        assert "Video về loài kiến nhỏ" in prompt_no_themes
        assert "[CRITICAL ANTI-REPETITION CONSTRAINT]" not in prompt_no_themes

        # With past themes
        past_themes = ["mèo cam", "khủng long", "rừng rậm"]
        prompt_with_themes = rewriter._build_story_user_prompt("Video về loài kiến nhỏ", past_themes)
        assert "[CRITICAL ANTI-REPETITION CONSTRAINT]" in prompt_with_themes
        assert "mèo cam, khủng long, rừng rậm" in prompt_with_themes
        assert "Video về loài kiến nhỏ" in prompt_with_themes

    def test_strip_code_fences_various_formats(self):
        """Verify code fence stripping handles json, generic markdown, and raw strings."""
        rewriter = ContentRewriter(api_key="mock_key")

        fenced_json = "```json\n{\"title_vi\": \"Test\"}\n```"
        assert rewriter._strip_code_fences(fenced_json) == '{"title_vi": "Test"}'

        fenced_plain = "```\n{\"title_vi\": \"Test\"}\n```"
        assert rewriter._strip_code_fences(fenced_plain) == '{"title_vi": "Test"}'

        raw_json = '{"title_vi": "Test"}'
        assert rewriter._strip_code_fences(raw_json) == '{"title_vi": "Test"}'

    def test_parse_story_response_valid_json(self):
        """Verify parsing valid JSON payload into strongly typed StoryScript."""
        rewriter = ContentRewriter(api_key="mock_key")
        payload = json.dumps({
            "title_vi": "Chú Kiến Nhỏ Dũng Cảm",
            "description_vi": "Mô tả câu chuyện chú kiến #shorts",
            "theme": "Côn trùng",
            "art_style": "cute 3D Pixar animation style",
            "character_style": "Tiny brown ant with green backpack",
            "niche": "stories",
            "summary": "Kiến vượt bão tìm đường về tổ.",
            "themes": ["kiến", "dũng cảm"],
            "scenes": [
                {
                    "scene_id": 1,
                    "narration_text_vi": "Trong khu vườn buổi sáng trong lành.",
                    "image_prompt_en": "A tiny cute ant walking on a leaf, 3D Pixar style"
                },
                {
                    "scene_id": 2,
                    "narration_text_vi": "Một cơn mưa lớn ập đến.",
                    "image_prompt_en": "Raindrops falling on a tiny ant, 3D Pixar style"
                },
                {
                    "scene_id": 3,
                    "narration_text_vi": "Chú kiến đã về đến tổ bình an.",
                    "image_prompt_en": "Ant celebrating at the anthill, 3D Pixar style"
                }
            ]
        })

        script = rewriter._parse_story_response(payload, niche="stories")
        assert isinstance(script, StoryScript)
        assert script.title_vi == "Chú Kiến Nhỏ Dũng Cảm"
        assert script.scene_count == 3
        assert script.scenes[0].scene_id == 1
        assert script.scenes[0].narration_text_vi == "Trong khu vườn buổi sáng trong lành."
        assert script.scenes[0].image_prompt_en == "A tiny cute ant walking on a leaf, 3D Pixar style"
        assert script.art_style == "cute 3D Pixar animation style"
        assert script.character_style == "Tiny brown ant with green backpack"

    def test_parse_story_response_markdown_fenced(self):
        """Verify parsing JSON wrapped in markdown code fence."""
        rewriter = ContentRewriter(api_key="mock_key")
        fenced_payload = (
            "```json\n"
            "{\n"
            '  "title_vi": "Cuộc Phiêu Lưu Dưới Đáy Biển",\n'
            '  "description_vi": "Khám phá đại dương",\n'
            '  "theme": "Đại dương",\n'
            '  "art_style": "cute 3D Pixar",\n'
            '  "scenes": [\n'
            '    {"scene_id": 1, "narration_text_vi": "Cá voi xanh bơi lội.", "image_prompt_en": "Blue whale swimming"},\n'
            '    {"scene_id": 2, "narration_text_vi": "Gặp rạn san hô rực rỡ.", "image_prompt_en": "Coral reef vibrant"},\n'
            '    {"scene_id": 3, "narration_text_vi": "Tìm thấy kho báu cổ.", "image_prompt_en": "Sunken treasure chest"}\n'
            "  ]\n"
            "}\n"
            "```"
        )

        script = rewriter._parse_story_response(fenced_payload, niche="stories")
        assert script.title_vi == "Cuộc Phiêu Lưu Dưới Đáy Biển"
        assert script.scene_count == 3

    def test_parse_story_response_embedded_in_text(self):
        """Verify regex recovery when JSON is surrounded by conversational LLM commentary."""
        rewriter = ContentRewriter(api_key="mock_key")
        wrapped_payload = (
            "Here is the generated story script for your YouTube channel:\n\n"
            "{\n"
            '  "title_vi": "Bí Mật Rừng Xanh",\n'
            '  "description_vi": "Chuyến phiêu lưu trong rừng",\n'
            '  "theme": "Thiên nhiên",\n'
            '  "art_style": "anime",\n'
            '  "scenes": [\n'
            '    {"scene_id": 1, "narration_text_vi": "Cảnh một.", "image_prompt_en": "Scene 1"},\n'
            '    {"scene_id": 2, "narration_text_vi": "Cảnh hai.", "image_prompt_en": "Scene 2"},\n'
            '    {"scene_id": 3, "narration_text_vi": "Cảnh ba.", "image_prompt_en": "Scene 3"}\n'
            "  ]\n"
            "}\n\n"
            "I hope you enjoy this script!"
        )

        script = rewriter._parse_story_response(wrapped_payload, niche="stories")
        assert script.title_vi == "Bí Mật Rừng Xanh"
        assert script.scene_count == 3

    def test_parse_story_response_alias_keys(self):
        """Verify normalization of alternative LLM keys (title_vn, narration, prompt)."""
        rewriter = ContentRewriter(api_key="mock_key")
        alias_payload = json.dumps({
            "title_vn": "Hành Trình Mới",
            "description_vn": "Mô tả mới",
            "topic": "Vũ trụ",
            "image_style": "cinematic sci-fi",
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "Tàu vũ trụ cất cánh.",
                    "prompt": "Spaceship launching into orbit"
                },
                {
                    "id": 2,
                    "text_vi": "Vượt qua vành đai tiểu hành tinh.",
                    "prompt_en": "Flying through asteroid belt"
                },
                {
                    "scene": 3,
                    "vietnamese": "Hạ cánh xuống hành tinh đỏ.",
                    "english_prompt": "Landing on red planet"
                }
            ]
        })

        script = rewriter._parse_story_response(alias_payload, niche="stories")
        assert script.title_vi == "Hành Trình Mới"
        assert script.scene_count == 3
        assert script.scenes[0].scene_id == 1
        assert script.scenes[0].narration_text_vi == "Tàu vũ trụ cất cánh."
        assert script.scenes[0].image_prompt_en == "Spaceship launching into orbit"
        assert script.scenes[1].scene_id == 2
        assert script.scenes[1].narration_text_vi == "Vượt qua vành đai tiểu hành tinh."
        assert script.scenes[2].scene_id == 3

    def test_parse_story_response_malformed_fallback(self):
        """Verify robust fallback to valid 3-scene StoryScript when JSON cannot be parsed."""
        rewriter = ContentRewriter(api_key="mock_key")
        malformed = "Chỉ là một đoạn văn bản tự do, hoàn toàn không có cấu trúc JSON nào cả."

        script = rewriter._parse_story_response(malformed, niche="stories")
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert len(script.scenes) == 3
        assert script.scenes[0].scene_id == 1
        assert script.scenes[0].narration_text_vi != ""
        assert script.scenes[0].image_prompt_en != ""

    @pytest.mark.asyncio
    async def test_rewrite_story_async_success(self, mock_gemini_model):
        """Verify full rewrite_story execution with mocked Gemini API."""
        rewriter = ContentRewriter(api_key="mock_key")
        rewriter.model = mock_gemini_model

        scraped_text = "Video về chú kiến nhỏ trong khu vườn tí hon khám phá tự nhiên."
        past_themes = ["khủng long", "mèo máy"]

        script = await rewriter.rewrite_story(scraped_text, niche="stories", past_themes=past_themes)
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert script.title_vi == "Hành Trình Chú Kiến Dũng Cảm"
        assert script.art_style == "cute 3D Pixar animation style, vibrant lighting"

        # Verify prompt received by mock
        assert len(mock_gemini_model.call_history) == 1
        called_prompt = mock_gemini_model.call_history[0]["prompt"]
        assert "khủng long, mèo máy" in called_prompt
        assert "Video về chú kiến nhỏ" in called_prompt

    @pytest.mark.asyncio
    async def test_rewrite_story_handles_empty_input(self):
        """Verify rewrite_story returns fallback on empty or whitespace scraped text."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = await rewriter.rewrite_story("", niche="stories")
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3

    @pytest.mark.asyncio
    async def test_rewrite_story_handles_api_exception(self):
        """Verify rewrite_story returns structured fallback on Gemini API errors (e.g. 429)."""
        rewriter = ContentRewriter(api_key="mock_key")
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(side_effect=Exception("429 Resource has been exhausted"))
        rewriter.model = mock_model

        script = await rewriter.rewrite_story("Nội dung nguồn", niche="stories")
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3

    @pytest.mark.asyncio
    async def test_backward_compatibility_rewrite_content(self, mock_gemini_model):
        """Verify backward compatible rewrite_content method returns dictionary."""
        rewriter = ContentRewriter(api_key="mock_key")
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=MagicMock(
            text=json.dumps({
                "content": "Nội dung bài đăng tiếng Việt",
                "image_prompt": "A cute cat on a table, 3D style",
                "summary": "Tóm tắt bài đăng",
                "themes": ["mèo", "hài hước"]
            })
        ))
        rewriter.model = mock_model

        result = await rewriter.rewrite_content(
            raw_content="Nội dung nguồn",
            niche={"name": "stories", "description": "Story niche", "tone": "engaging"},
            knowledge_history="Theme cũ: chó",
            platform="youtube",
        )

        assert isinstance(result, dict)
        assert result["content"] == "Nội dung bài đăng tiếng Việt"
        assert result["image_prompt"] == "A cute cat on a table, 3D style"
        assert result["summary"] == "Tóm tắt bài đăng"
        assert result["themes"] == ["mèo", "hài hước"]


# ============================================================================
# Section 2: ImageGenerator Tests (Pollinations.ai)
# ============================================================================

class TestImageGenerator:
    """Test suite for ImageGenerator."""

    def test_dimensions_resolution_mapping(self):
        """Verify aspect ratio string resolution to width and height tuples."""
        assert get_dimensions_for_aspect_ratio("9:16") == (1080, 1920)
        assert get_dimensions_for_aspect_ratio("16:9") == (1920, 1080)
        assert get_dimensions_for_aspect_ratio("1:1") == (1024, 1024)
        assert get_dimensions_for_aspect_ratio("4:5") == (1080, 1350)
        # Draft resolution
        assert get_dimensions_for_aspect_ratio("9:16", high_res=False) == (719, 1278)

    def test_compose_scene_prompt_consistency(self):
        """Verify prompt composition with character style prefix, art style suffix, and deduplication."""
        composed = compose_scene_prompt(
            scene_prompt="A tiny ant walking happily on a giant leaf",
            art_style="3D Pixar animation style",
            character_style="Tiny brave brown ant with blue backpack",
        )
        assert composed.startswith("Tiny brave brown ant with blue backpack")
        assert "A tiny ant walking happily on a giant leaf" in composed
        assert "in 3D Pixar animation style" in composed
        assert "8k resolution" in composed

        # Deduplication: if art style is already in prompt, do not duplicate
        composed_dedup = compose_scene_prompt(
            scene_prompt="A tiny ant in 3D Pixar animation style exploring a garden",
            art_style="3D Pixar animation style",
            character_style="Tiny brown ant",
        )
        # Should only contain '3D Pixar animation style' once in main prompt body
        assert composed_dedup.count("3D Pixar animation style") == 1

    def test_image_generator_init_and_output_dir(self, tmp_path: Path):
        """Verify output directory creation during initialization."""
        img_dir = tmp_path / "custom_images"
        gen = ImageGenerator(output_dir=str(img_dir))
        assert img_dir.exists()
        assert gen.output_dir == img_dir
        assert gen.default_model == "flux"
        assert gen.fallback_model == "turbo"

    def test_generate_filename_format(self):
        """Verify generated filename contains timestamp and hash."""
        gen = ImageGenerator()
        fn = gen._generate_filename("A brave ant sailing on a leaf", prefix="scene_01")
        assert fn.startswith("scene_01_")
        assert fn.endswith(".png")

    def test_verify_image_data(self):
        """Verify _verify_image_data distinguishes valid PNGs from corrupt/undersized bytes."""
        gen = ImageGenerator()

        valid_bytes = create_synthetic_png_bytes(512, 512)
        assert gen._verify_image_data(valid_bytes) is True

        corrupt_bytes = b"SHORT_CORRUPT"
        assert gen._verify_image_data(corrupt_bytes) is False

        oversized_garbage = b"X" * 2048
        assert gen._verify_image_data(oversized_garbage) is False

    @pytest.mark.asyncio
    async def test_generate_image_success_mock(self, tmp_path: Path):
        """Verify single image download with valid PNG mock response."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        valid_png = create_synthetic_png_bytes(1080, 1920)

        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            dest_file = tmp_path / "out_img.png"

            path = await gen.generate_image(
                prompt="A tiny ant in a sunny forest",
                width=1080,
                height=1920,
                seed=12345,
                model="flux",
                custom_filepath=dest_file,
            )

            assert Path(path).exists()
            assert Path(path) == dest_file
            img = Image.open(path)
            assert img.size == (1080, 1920)

            # Verify query URL parameters
            called_url = str(mock_get.call_args[0][0])
            assert "width=1080" in called_url
            assert "height=1920" in called_url
            assert "seed=12345" in called_url
            assert "model=flux" in called_url

    @pytest.mark.asyncio
    async def test_generate_image_url_encoding(self, tmp_path: Path):
        """Verify special characters (&, #, quotes, slashes) are properly URL encoded."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        valid_png = create_synthetic_png_bytes(512, 512)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            special_prompt = 'Cute "ant" & "bee" / garden #nature'
            await gen.generate_image(special_prompt, width=512, height=512)

            called_url = str(mock_get.call_args[0][0])
            assert "%20" in called_url or "+" in called_url
            # Ampersand in prompt should be escaped so it's not a query delimiter
            assert "%26" in called_url or "/prompt/" in called_url

    @pytest.mark.asyncio
    async def test_generate_image_retry_on_corrupt_payload(self, tmp_path: Path):
        """Verify retrying when initial download is corrupt or <1KB."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        corrupt_res = MagicMock(status_code=200, content=b"TOO_SHORT", raise_for_status=MagicMock())
        valid_res = MagicMock(status_code=200, content=create_synthetic_png_bytes(512, 512), raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [corrupt_res, valid_res]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                path = await gen.generate_image("Prompt", width=512, height=512)
                assert Path(path).exists()
                assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_image_fallback_to_turbo_on_last_retry(self, tmp_path: Path):
        """Verify fallback to turbo model on the final retry attempt."""
        gen = ImageGenerator(output_dir=str(tmp_path), max_retries=3)
        valid_res = MagicMock(status_code=200, content=create_synthetic_png_bytes(512, 512), raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # 2 failures followed by success on 3rd attempt
            mock_get.side_effect = [
                httpx.ConnectTimeout("Timeout 1"),
                httpx.ConnectTimeout("Timeout 2"),
                valid_res,
            ]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                path = await gen.generate_image("Prompt")
                assert Path(path).exists()
                assert mock_get.call_count == 3

                # 3rd call should use turbo fallback model
                third_call_url = str(mock_get.call_args_list[2][0][0])
                assert "model=turbo" in third_call_url

    @pytest.mark.asyncio
    async def test_generate_image_retry_exhaustion_raises(self, tmp_path: Path):
        """Verify exception raised when all retries are exhausted."""
        gen = ImageGenerator(output_dir=str(tmp_path), max_retries=3)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectTimeout("Persistent timeout")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="Failed to generate image"):
                    await gen.generate_image("Prompt")
                assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_scene_images_batch_success(self, tmp_path: Path):
        """Verify batch generation of images for all scenes in a StoryScript."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        scenes = [
            Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1"),
            Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2"),
            Scene(scene_id=3, narration_text_vi="Cảnh 3", image_prompt_en="Prompt 3"),
        ]

        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            updated_scenes = await gen.generate_scene_images(
                scenes=scenes,
                art_style="cute 3D Pixar animation",
                character_style="Tiny brown ant",
                aspect_ratio="9:16",
            )

            assert len(updated_scenes) == 3
            for s in updated_scenes:
                assert s.image_path is not None
                assert Path(s.image_path).exists()
                assert s.status == "image_ready"
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_scene_images_skips_existing_cached_images(self, tmp_path: Path):
        """Verify scene images that already exist on disk are reused without making network calls."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        existing_img = tmp_path / "existing_scene_1.png"
        create_synthetic_png(existing_img, 1080, 1920)

        scenes = [
            Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", image_path=str(existing_img)),
            Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2"),
        ]

        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            updated = await gen.generate_scene_images(scenes, aspect_ratio="9:16")

            assert updated[0].image_path == str(existing_img)
            assert updated[1].image_path is not None
            # Only scene 2 required a network call
            assert mock_get.call_count == 1


# ============================================================================
# Section 3: AudioGenerator Tests (Edge-TTS & Mutagen)
# ============================================================================

class TestAudioGenerator:
    """Test suite for AudioGenerator."""

    def test_init_and_defaults(self, tmp_path: Path):
        """Verify AudioGenerator initialization and default settings."""
        audio_dir = tmp_path / "audio_out"
        gen = AudioGenerator(output_dir=str(audio_dir))
        assert audio_dir.exists()
        assert gen.default_voice == "vi-VN-NamMinhNeural"
        assert gen.rate == "+0%"
        assert gen.pitch == "+0Hz"

    def test_normalize_vietnamese_text_markdown_stripping(self):
        """Verify stripping of markdown headers, bold, italic, code blocks, and links."""
        gen = AudioGenerator()
        markdown_text = (
            "# Tiêu đề lớn\n"
            "> Lời trích dẫn hay.\n"
            "Đây là chữ **in đậm** và chữ *in nghiêng*, cùng với ~~gạch ngang~~.\n"
            "Xem thêm tại [Báo Dân Trí](https://dantri.com.vn).\n"
            "Đoạn mã: `print('hello')`.\n"
            "- Mục 1\n- Mục 2"
        )
        normalized = gen.normalize_vietnamese_text(markdown_text)
        assert "#" not in normalized
        assert ">" not in normalized
        assert "**" not in normalized
        assert "*" not in normalized
        assert "~~" not in normalized
        assert "[" not in normalized
        assert "http" not in normalized
        assert "in đậm" in normalized
        assert "in nghiêng" in normalized
        assert "Báo Dân Trí" in normalized

    def test_normalize_vietnamese_text_emoji_removal(self):
        """Verify removal of emojis and disruptive punctuation symbols."""
        gen = AudioGenerator()
        emoji_text = "🐶 Chú chó thông minh 🐱 và cô mèo tinh nghịch! ✨🔥🎉 @kenh_hay #shorts"
        normalized = gen.normalize_vietnamese_text(emoji_text)
        assert "Chú chó thông minh và cô mèo tinh nghịch!" in normalized
        assert "✨" not in normalized
        assert "🔥" not in normalized
        assert "@" not in normalized
        assert "#" not in normalized

    def test_normalize_vietnamese_text_abbreviations_and_slang(self):
        """Verify expansion of common Vietnamese chat abbreviations and slang."""
        gen = AudioGenerator()
        slang_text = "Hôm nay mk ko đi làm dc vs mn ở tp HCM và HN, mn có bt j mới ko? ns rùi mà."
        normalized = gen.normalize_vietnamese_text(slang_text)
        assert "mình không đi làm được với mọi người ở thành phố Hồ Chí Minh và Hà Nội" in normalized
        assert "biết gì mới không" in normalized
        assert "nói rồi mà" in normalized

    def test_normalize_vietnamese_text_currency_percentage_units(self):
        """Verify normalization of numbers, currencies, percentages, and measurement units."""
        gen = AudioGenerator()
        units_text = "Giá 50k, giảm 20%, nhiệt độ 35°C, vận tốc 60km/h trên đoạn đường 100km diện tích 50m2."
        normalized = gen.normalize_vietnamese_text(units_text)
        assert "50 nghìn" in normalized
        assert "20 phần trăm" in normalized
        assert "35 độ C" in normalized
        assert "60 ki-lô-mét trên giờ" in normalized
        assert "100 ki-lô-mét" in normalized
        assert "50 mét vuông" in normalized

    def test_normalize_vietnamese_text_punctuation_spacing(self):
        """Verify punctuation spacing and ellipsis cleanup."""
        gen = AudioGenerator()
        punct_text = "Xin chào các bạn ...  Hôm nay thế nào ??? Thật tuyệt !!! ,vui quá"
        normalized = gen.normalize_vietnamese_text(punct_text)
        assert "Xin chào các bạn." in normalized
        assert "Hôm nay thế nào?" in normalized
        assert "Thật tuyệt!" in normalized
        assert ", vui quá" in normalized or ",vui" not in normalized

    def test_get_audio_duration_with_synthetic_mp3(self, tmp_path: Path):
        """Verify exact duration extraction from MPEG-1 Layer 3 MP3 file."""
        gen = AudioGenerator()
        mp3_file = tmp_path / "test_audio.mp3"
        create_synthetic_mp3(mp3_file, duration_seconds=4.5)

        duration = gen.get_audio_duration(mp3_file)
        assert duration > 4.0
        assert duration < 5.0

    def test_get_audio_duration_missing_or_empty_raises(self, tmp_path: Path):
        """Verify get_audio_duration raises ValueError on missing or empty file."""
        gen = AudioGenerator()
        with pytest.raises(ValueError, match="missing or empty"):
            gen.get_audio_duration(tmp_path / "non_existent.mp3")

        empty_file = tmp_path / "empty.mp3"
        empty_file.touch()
        with pytest.raises(ValueError, match="missing or empty"):
            gen.get_audio_duration(empty_file)

    @pytest.mark.asyncio
    async def test_generate_single_audio_success(self, tmp_path: Path, monkeypatch):
        """Verify single audio generation with mocked Edge-TTS Communicate."""
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))
        dest_mp3 = tmp_path / "single_test.mp3"

        duration = await gen.generate_single_audio(
            text="Trong khu vườn ngập tràn ánh nắng ban mai rực rỡ.",
            output_path=dest_mp3,
            voice="vi-VN-NamMinhNeural",
        )

        assert dest_mp3.exists()
        assert duration > 0.0
        assert dest_mp3.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_generate_single_audio_empty_text_raises(self, tmp_path: Path):
        """Verify ValueError raised when text is empty after normalization."""
        gen = AudioGenerator(output_dir=str(tmp_path))
        with pytest.raises(ValueError, match="empty after normalization"):
            await gen.generate_single_audio(
                text="   ✨🔥   ",
                output_path=tmp_path / "empty.mp3",
            )

    @pytest.mark.asyncio
    async def test_generate_single_audio_retry_and_recover(self, tmp_path: Path, monkeypatch):
        """Verify generate_single_audio retries on transient exception."""
        attempts = 0

        class FlakyMockCommunicate:
            def __init__(self, text, **kwargs):
                self.text = text
                self.duration = 2.5

            async def save(self, path):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise IOError("Simulated network glitch")
                create_synthetic_mp3(path, duration_seconds=self.duration)

        monkeypatch.setattr("edge_tts.Communicate", FlakyMockCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            dest_file = tmp_path / "flaky.mp3"
            duration = await gen.generate_single_audio("Xin chào", dest_file)
            assert dest_file.exists()
            assert duration > 0.0
            assert attempts == 2

    @pytest.mark.asyncio
    async def test_generate_audio_compatibility_alias(self, tmp_path: Path, monkeypatch):
        """Verify backward compatible generate_audio method."""
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))
        dest = tmp_path / "alias_test.mp3"

        duration = await gen.generate_audio("Xin chào các bạn", str(dest))
        assert dest.exists()
        assert duration > 0.0

    @pytest.mark.asyncio
    async def test_generate_scene_audios_batch_success(self, tmp_path: Path, monkeypatch):
        """Verify batch generation of audio files for all scenes in a StoryScript."""
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))
        scenes = [
            Scene(scene_id=1, narration_text_vi="Cảnh một: Buổi sáng trong lành.", image_prompt_en="Sunny morning"),
            Scene(scene_id=2, narration_text_vi="Cảnh hai: Mưa bão kéo đến bất ngờ.", image_prompt_en="Storm coming"),
            Scene(scene_id=3, narration_text_vi="Cảnh ba: Cầu vồng xuất hiện rực rỡ.", image_prompt_en="Rainbow appears"),
        ]

        updated_scenes = await gen.generate_scene_audios(scenes, voice="vi-VN-NamMinhNeural")

        assert len(updated_scenes) == 3
        for s in updated_scenes:
            assert s.audio_path is not None
            assert Path(s.audio_path).exists()
            assert s.duration > 0.0
            assert s.status == "audio_ready"


# ============================================================================
# Section 4: End-to-End M2 Pipeline Integration Tests
# ============================================================================

class TestM2PipelineIntegration:
    """Integration test suite connecting StoryScript -> ImageGenerator -> AudioGenerator."""

    @pytest.mark.asyncio
    async def test_full_m2_pipeline_mock_flow(self, tmp_path: Path, mock_gemini_model, monkeypatch):
        """Verify the complete M2 pipeline flow from scraped text to ready scenes."""
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)

        images_dir = tmp_path / "images"
        audio_dir = tmp_path / "audio"
        kb_file = tmp_path / "kb.md"

        # 1. KnowledgeBase setup
        kb = KnowledgeBase(filepath=str(kb_file))
        kb.append_entry("youtube", "stories", "Previous ant story", ["kiến lửa", "khu vườn"])

        # 2. ContentRewriter step
        rewriter = ContentRewriter(api_key="mock_key")
        rewriter.model = mock_gemini_model
        past_themes = rewriter.extract_past_themes_from_file(str(kb_file))

        scraped_text = "Video hướng dẫn khám phá thế giới tí hon của các loài côn trùng."
        story_script = await rewriter.rewrite_story(scraped_text, niche="stories", past_themes=past_themes)

        assert isinstance(story_script, StoryScript)
        assert story_script.scene_count == 3

        # 3. ImageGenerator step
        image_gen = ImageGenerator(output_dir=str(images_dir))
        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            story_script.scenes = await image_gen.generate_scene_images(
                scenes=story_script.scenes,
                art_style=story_script.art_style,
                character_style=story_script.character_style,
                aspect_ratio=story_script.target_aspect_ratio,
            )

        for s in story_script.scenes:
            assert s.image_path is not None
            assert Path(s.image_path).exists()
            assert s.status == "image_ready"

        # 4. AudioGenerator step
        audio_gen = AudioGenerator(output_dir=str(audio_dir))
        story_script.scenes = await audio_gen.generate_scene_audios(
            scenes=story_script.scenes,
            voice="vi-VN-NamMinhNeural",
        )

        for s in story_script.scenes:
            assert s.audio_path is not None
            assert Path(s.audio_path).exists()
            assert s.duration > 0.0
            # Both image and audio are ready -> status is 'completed'
            assert s.status == "completed"

        # 5. Verify StoryScript total duration and dynamic aspect ratio
        assert story_script.total_duration > 0.0
        assert story_script.is_shorts is True  # duration ~3*3s = 9s < 60s
        assert story_script.target_aspect_ratio == "9:16"

    def test_story_script_duration_and_aspect_ratio_sync(self):
        """Verify dynamic aspect ratio switching at 60.0s boundary."""
        # Shorts (<60s)
        shorts_scenes = [
            Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="P1", duration=25.0),
            Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="P2", duration=30.0),
        ]
        shorts_script = StoryScript(
            title_vi="Shorts Video",
            description_vi="",
            theme="",
            art_style="",
            scenes=shorts_scenes,
        )
        assert shorts_script.total_duration == 55.0
        assert shorts_script.is_shorts is True
        assert shorts_script.target_aspect_ratio == "9:16"

        # Regular Video (>=60s)
        regular_scenes = [
            Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="P1", duration=35.0),
            Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="P2", duration=35.0),
        ]
        regular_script = StoryScript(
            title_vi="Regular Video",
            description_vi="",
            theme="",
            art_style="",
            scenes=regular_scenes,
        )
        assert regular_script.total_duration == 70.0
        assert regular_script.is_shorts is False
        assert regular_script.target_aspect_ratio == "16:9"
