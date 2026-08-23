"""
tests/test_ai_pipeline_adversarial.py
Adversarial Stress Test Suite for Milestone M2 AI Pipeline:
- ContentRewriter: Extreme inputs, massive text, broken JSON, missing keys, anti-repetition past themes.
- ImageGenerator: Edge-case aspect ratios, URL control character injection, corrupt payloads, network timeouts, retries & fallback models.
- StoryScript & Scene: Integrity verification, state transitions, dynamic duration & aspect ratios.
"""

import asyncio
import io
import json
import os
import re
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
from src.models.pipeline_models import Scene, StoryScript
from tests.conftest import (
    MockGeminiModel,
    create_synthetic_png,
    create_synthetic_png_bytes,
)


# ============================================================================
# TIER 1: ContentRewriter Adversarial Stress Tests
# ============================================================================

class TestContentRewriterAdversarial:
    """Adversarial test suite stress-testing ContentRewriter robustness."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("empty_input", [
        "",
        "   ",
        "\n\n\t\t\r\n",
        None,
        "   \t   \n   ",
    ])
    async def test_rewriter_extreme_empty_whitespace_inputs(self, empty_input):
        """Verify rewrite_story returns structured fallback on empty or whitespace inputs without raising uncaught exceptions."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = await rewriter.rewrite_story(empty_input, niche="stories")

        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert script.title_vi != ""
        assert script.description_vi != ""
        assert len(script.scenes) == 3
        for s in script.scenes:
            assert isinstance(s.scene_id, int)
            assert s.narration_text_vi != ""
            assert s.image_prompt_en != ""

    @pytest.mark.asyncio
    async def test_rewriter_massive_50k_character_input(self):
        """Verify handling of massive 50,000-character input text without memory explosion or crashes."""
        rewriter = ContentRewriter(api_key="mock_key")
        massive_text = "Câu chuyện về khu vườn tí hon ngập tràn kỳ diệu. " * 1000  # ~50k chars

        # Test fallback path with massive text
        script = await rewriter.rewrite_story(massive_text, niche="stories")
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert len(script.title_vi) <= 100  # Truncated safely in fallback title

        # Test prompt builder with massive text
        user_prompt = rewriter._build_story_user_prompt(massive_text, past_themes=["chủ đề cũ"])
        assert "[SOURCE INSPIRATION MATERIAL]" in user_prompt
        assert len(user_prompt) > 50000

    @pytest.mark.asyncio
    @pytest.mark.parametrize("special_text", [
        "🐶🐱🐭🐹🐰🦊🐻🐼🦁🐯🐨🐵 - Emojis Storm! ✨🔥🎉🚀💥",
        "Chào bạn \x00\x01\x02\x08\x0b\x0c\x0e\x1f null and control bytes",
        "مرحبا بك trong thế giới tí hon שלום עליכם mixed RTL and LTR",
        "Tiêu đề có dấu ngã ẵ ỡ ự ỳ ỹ ỷ ế ệ và ký tự đặc biệt: <>&\"'/$%^*()_+~",
        "Multi-line \n\r\n\t with \t tabs \v and \f formfeeds",
    ])
    async def test_rewriter_special_characters_and_emojis(self, special_text):
        """Verify handling of complex Unicode, emojis, RTL scripts, and non-printable control chars."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = await rewriter.rewrite_story(special_text, niche="stories")

        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert script.title_vi != ""

    @pytest.mark.parametrize("fenced_payload,expected_title", [
        ("```json\n{\"title_vi\": \"Tiêu Đề 1\", \"scenes\": [{\"scene_id\": 1, \"narration_text_vi\": \"A\", \"image_prompt_en\": \"B\"}]}\n```", "Tiêu Đề 1"),
        ("```JSON\n{\"title_vi\": \"Tiêu Đề 2\", \"scenes\": [{\"scene_id\": 1, \"narration_text_vi\": \"A\", \"image_prompt_en\": \"B\"}]}\n```", "Tiêu Đề 2"),
        ("```\n{\"title_vi\": \"Tiêu Đề 3\", \"scenes\": [{\"scene_id\": 1, \"narration_text_vi\": \"A\", \"image_prompt_en\": \"B\"}]}\n```", "Tiêu Đề 3"),
        ("Here is the JSON you requested:\n```json\n{\"title_vi\": \"Tiêu Đề 4\", \"scenes\": [{\"scene_id\": 1, \"narration_text_vi\": \"A\", \"image_prompt_en\": \"B\"}]}\n```\nEnjoy!", "Tiêu Đề 4"),
        ("Note: ```json\n{\"title_vi\": \"Tiêu Đề 5\", \"scenes\": [{\"scene_id\": 1, \"narration_text_vi\": \"A\", \"image_prompt_en\": \"B\"}]}", "Tiêu Đề 5"),
    ])
    def test_rewriter_markdown_code_fence_variants(self, fenced_payload, expected_title):
        """Verify code fence stripping across various markdown wrappers, casing, and conversational commentary."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = rewriter._parse_story_response(fenced_payload, niche="stories")

        assert isinstance(script, StoryScript)
        assert script.title_vi == expected_title

    @pytest.mark.parametrize("malformed_json", [
        '{"title_vi": "Unclosed JSON',
        '{"title_vi": "Missing colon" "theme": "Test"}',
        '{"title_vi": "Trailing comma", "scenes": [],}',
        "{'title_vi': 'Single quotes instead of double quotes'}",
        '{"title_vi": "Unescaped newline in \n string value"}',
        "<html><body>502 Bad Gateway</body></html>",
        "Plain conversational text without any braces whatsoever.",
        '{"nested": {"broken": [1, 2, }}',
    ])
    def test_rewriter_malformed_and_corrupt_json_fallback(self, malformed_json):
        """Verify parser falls back to valid 3-scene StoryScript on completely corrupted/malformed JSON."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = rewriter._parse_story_response(malformed_json, niche="stories")

        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert len(script.scenes) == 3
        assert script.scenes[0].scene_id == 1
        assert script.scenes[0].narration_text_vi != ""
        assert script.scenes[0].image_prompt_en != ""

    @pytest.mark.parametrize("missing_keys_payload", [
        json.dumps({}),
        json.dumps({"title_vi": "Chỉ có tiêu đề"}),
        json.dumps({"theme": "Chỉ có theme", "art_style": "anime"}),
        json.dumps({"scenes": "scenes_is_not_a_list"}),
        json.dumps({"scenes": [{"invalid": "no narration or prompt"}]}),
        json.dumps({"scenes": [{"scene_id": "not_an_int", "narration_text_vi": "N", "image_prompt_en": "P"}]}),
        json.dumps({"scenes": [{"scene_id": -5, "narration_text_vi": "N", "image_prompt_en": "P"}]}),
    ])
    def test_rewriter_missing_and_corrupt_schema_keys(self, missing_keys_payload):
        """Verify missing mandatory keys or invalid schema types gracefully fallback without raising."""
        rewriter = ContentRewriter(api_key="mock_key")
        script = rewriter._parse_story_response(missing_keys_payload, niche="stories")

        assert isinstance(script, StoryScript)
        assert script.scene_count >= 1
        assert script.title_vi != ""

    @pytest.mark.asyncio
    async def test_rewriter_repeated_past_themes_anti_repetition_stress(self):
        """Verify prompt builder handles large arrays of past themes and anti-repetition constraints."""
        rewriter = ContentRewriter(api_key="mock_key")

        # 1000 past themes
        huge_themes = [f"Chủ đề số {i}" for i in range(1000)]
        prompt = rewriter._build_story_user_prompt("Nội dung mới", past_themes=huge_themes)

        assert "[CRITICAL ANTI-REPETITION CONSTRAINT]" in prompt
        # Sliced to 20 themes to avoid prompt overflow
        assert "Chủ đề số 0" in prompt
        assert "Chủ đề số 19" in prompt
        assert "Chủ đề số 500" not in prompt

        # None past themes
        prompt_none = rewriter._build_story_user_prompt("Nội dung mới", past_themes=None)
        assert "[CRITICAL ANTI-REPETITION CONSTRAINT]" not in prompt_none

        # Empty list
        prompt_empty = rewriter._build_story_user_prompt("Nội dung mới", past_themes=[])
        assert "[CRITICAL ANTI-REPETITION CONSTRAINT]" not in prompt_empty

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_side_effect", [
        Exception("429 Resource Exhausted"),
        Exception("500 Internal Server Error"),
        Exception("503 Service Unavailable"),
        TimeoutError("Gemini call timed out"),
        RuntimeError("Fatal RPC connection drop"),
    ])
    async def test_rewriter_gemini_api_failures_return_fallback(self, error_side_effect):
        """Verify all categories of Gemini API runtime failures return structured fallback story."""
        rewriter = ContentRewriter(api_key="mock_key")
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(side_effect=error_side_effect)
        rewriter.model = mock_model

        script = await rewriter.rewrite_story("Nội dung đầu vào", niche="stories")
        assert isinstance(script, StoryScript)
        assert script.scene_count == 3
        assert script.title_vi != ""


# ============================================================================
# TIER 2: ImageGenerator Adversarial Stress Tests
# ============================================================================

class TestImageGeneratorAdversarial:
    """Adversarial test suite stress-testing ImageGenerator Pollinations.ai integration."""

    @pytest.mark.parametrize("aspect_ratio,expected_dim", [
        ("9:16", (1080, 1920)),
        ("16:9", (1920, 1080)),
        ("1:1", (1024, 1024)),
        ("4:5", (1080, 1350)),
        ("21:9", (2520, 1080)),
        ("9:21", (1080, 2520)),
        ("3:2", (1620, 1080)),
        ("2:3", (1080, 1620)),
        ("0:0", (1080, 1920)),      # Fallback
        ("-9:16", (1080, 1920)),    # Fallback
        ("invalid_ratio", (1080, 1920)), # Fallback
        ("", (1080, 1920)),         # Fallback
        ("1:2:3", (1080, 1920)),    # Malformed colon count
    ])
    def test_dimensions_unusual_aspect_ratios_matrix(self, aspect_ratio, expected_dim):
        """Verify get_dimensions_for_aspect_ratio handles unusual, extreme, and malformed aspect ratios."""
        dims = get_dimensions_for_aspect_ratio(aspect_ratio)
        assert dims == expected_dim
        assert dims[0] > 0
        assert dims[1] > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("special_prompt", [
        "A cute ant & a bee with ?query=param#fragment%20bonus",
        "A dog / cat \\ mouse = 100% + $50 #adventure?test=1&b=2",
        "Prompt with 'single' and \"double\" quotes and `backticks`",
        "Unicode prompts: 🐶 chú kiến nhỏ trong khu vườn tí hon 🌸",
        "A" * 1000,  # Extremely long prompt
    ])
    async def test_prompt_url_control_characters_injection_safe(self, tmp_path: Path, special_prompt):
        """Verify URL control characters (?&=#%+/) do not hijack Pollinations URL query string."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        valid_png = create_synthetic_png_bytes(512, 512)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            dest_file = tmp_path / "test_encoded.png"

            path = await gen.generate_image(
                prompt=special_prompt,
                width=512,
                height=512,
                custom_filepath=dest_file,
            )

            assert Path(path).exists()
            called_url = str(mock_get.call_args[0][0])

            # Query params should remain clean and intact
            assert "width=512" in called_url
            assert "height=512" in called_url
            assert "nologo=true" in called_url

            # Base URL structure should be preserved
            assert called_url.startswith("https://image.pollinations.ai/prompt/")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("corrupt_payload", [
        b"",                         # 0 bytes
        b"TOO_SHORT",               # 9 bytes
        b"\x00" * 500,               # 500 bytes of nulls (<1024)
        b"<!DOCTYPE html><html><body>500 Error</body></html>" + bytes(1000),  # HTML error page >= 1KB
        b"\x89PNG\r\n\x1a\n" + bytes(2000),  # Valid PNG magic number but corrupted chunk payload
    ])
    async def test_image_corrupt_payload_validation(self, tmp_path: Path, corrupt_payload):
        """Verify _verify_image_data rejects corrupt, undersized, or fake payloads."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        assert gen._verify_image_data(corrupt_payload) is False

    @pytest.mark.asyncio
    async def test_image_retry_and_turbo_fallback_flow(self, tmp_path: Path):
        """Verify ImageGenerator attempts retries with exponential backoff and switches to turbo model on last attempt."""
        gen = ImageGenerator(output_dir=str(tmp_path), default_model="flux", fallback_model="turbo", max_retries=3)
        valid_png = create_synthetic_png_bytes(512, 512)
        valid_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # First 2 attempts fail with timeout, 3rd succeeds
            mock_get.side_effect = [
                httpx.ConnectTimeout("Timeout 1"),
                httpx.ReadTimeout("Timeout 2"),
                valid_res,
            ]
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                img_path = await gen.generate_image("Prompt test", width=512, height=512)

                assert Path(img_path).exists()
                assert mock_get.call_count == 3
                assert mock_sleep.call_count == 2

                # Verify attempt 1 & 2 used flux, attempt 3 used turbo
                url1 = str(mock_get.call_args_list[0][0][0])
                url2 = str(mock_get.call_args_list[1][0][0])
                url3 = str(mock_get.call_args_list[2][0][0])

                assert "model=flux" in url1
                assert "model=flux" in url2
                assert "model=turbo" in url3

    @pytest.mark.asyncio
    async def test_image_retry_exhaustion_cleans_up_tmp_and_raises(self, tmp_path: Path):
        """Verify persistent network failures raise Exception and leave no orphan tmp files."""
        gen = ImageGenerator(output_dir=str(tmp_path), max_retries=3)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="Failed to generate image after 3 attempts"):
                    await gen.generate_image("Failed prompt")

                assert mock_get.call_count == 3
                # No leftover .tmp files
                tmp_files = list(tmp_path.glob("*.tmp"))
                assert len(tmp_files) == 0

    @pytest.mark.asyncio
    async def test_image_caching_and_corrupt_cache_invalidation(self, tmp_path: Path):
        """Verify valid cached image is reused, but 0-byte or corrupted cached file is re-generated."""
        gen = ImageGenerator(output_dir=str(tmp_path))

        valid_cache = tmp_path / "valid_scene.png"
        create_synthetic_png(valid_cache, 1080, 1920)

        corrupt_cache = tmp_path / "corrupt_scene.png"
        with open(corrupt_cache, "wb") as f:
            f.write(b"SHORT")  # <1024 bytes -> invalid

        scenes = [
            Scene(scene_id=1, narration_text_vi="C1", image_prompt_en="P1", image_path=str(valid_cache)),
            Scene(scene_id=2, narration_text_vi="C2", image_prompt_en="P2", image_path=str(corrupt_cache)),
        ]

        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            updated_scenes = await gen.generate_scene_images(scenes, aspect_ratio="9:16")

            # Scene 1 reused cache
            assert updated_scenes[0].image_path == str(valid_cache)
            # Scene 2 was re-generated
            assert updated_scenes[1].image_path != str(corrupt_cache)
            assert Path(updated_scenes[1].image_path).exists()
            assert Path(updated_scenes[1].image_path).stat().st_size > 1024
            # Exactly 1 HTTP call made for scene 2
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_image_scene_status_lifecycle_and_failure(self, tmp_path: Path):
        """Verify scene status transitions: pending -> image_ready / completed, or failed on error."""
        gen = ImageGenerator(output_dir=str(tmp_path))

        # Scene with audio already present
        scene_with_audio = Scene(
            scene_id=1,
            narration_text_vi="C1",
            image_prompt_en="P1",
            audio_path="/mock/audio.mp3",
            status="audio_ready",
        )

        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            updated = await gen.generate_scene_images([scene_with_audio])
            assert updated[0].status == "completed"

        # Scene generation failure marks scene status as 'failed'
        failing_scene = Scene(scene_id=2, narration_text_vi="C2", image_prompt_en="P2")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_fail:
            mock_get_fail.side_effect = httpx.ConnectTimeout("Timeout")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception):
                    await gen.generate_scene_images([failing_scene])
                assert failing_scene.status == "failed"


# ============================================================================
# TIER 3: Cross-Component Property & Invariant Stress Tests
# ============================================================================

class TestPipelineCrossComponentInvariants:
    """Stress-test pipeline invariants, scene counting, and aspect ratio dynamics."""

    def test_storyscript_aspect_ratio_invariants(self):
        """Verify StoryScript target_aspect_ratio dynamically reacts to duration and scene count."""
        # 3 scenes, duration 0 -> default shorts (<=4 scenes) -> 9:16
        script_shorts_scenes = StoryScript(
            title_vi="Shorts Script",
            description_vi="Mô tả",
            theme="Chủ đề",
            art_style="3D Pixar",
            scenes=[
                Scene(scene_id=1, narration_text_vi="C1", image_prompt_en="P1", duration=0.0),
                Scene(scene_id=2, narration_text_vi="C2", image_prompt_en="P2", duration=0.0),
                Scene(scene_id=3, narration_text_vi="C3", image_prompt_en="P3", duration=0.0),
            ]
        )
        assert script_shorts_scenes.is_shorts is True
        assert script_shorts_scenes.target_aspect_ratio == "9:16"

        # 6 scenes, duration 0 -> regular video (>4 scenes) -> 16:9
        script_regular_scenes = StoryScript(
            title_vi="Regular Script",
            description_vi="Mô tả",
            theme="Chủ đề",
            art_style="3D Pixar",
            scenes=[
                Scene(scene_id=i, narration_text_vi=f"C{i}", image_prompt_en=f"P{i}", duration=0.0)
                for i in range(1, 7)
            ]
        )
        assert script_regular_scenes.is_shorts is False
        assert script_regular_scenes.target_aspect_ratio == "16:9"

        # Explicit duration overrides scene count
        # 3 scenes with total duration = 75.0s -> regular video >=60s -> 16:9
        script_shorts_scenes.scenes[0].duration = 25.0
        script_shorts_scenes.scenes[1].duration = 25.0
        script_shorts_scenes.scenes[2].duration = 25.0
        assert script_shorts_scenes.total_duration == 75.0
        assert script_shorts_scenes.is_shorts is False
        assert script_shorts_scenes.target_aspect_ratio == "16:9"

        # 6 scenes with total duration = 45.0s -> shorts video <60s -> 9:16
        for s in script_regular_scenes.scenes:
            s.duration = 7.5
        assert script_regular_scenes.total_duration == 45.0
        assert script_regular_scenes.is_shorts is True
        assert script_regular_scenes.target_aspect_ratio == "9:16"

    def test_compose_scene_prompt_invariants(self):
        """Verify compose_scene_prompt preserves all elements and never drops prompt content."""
        prompt = "A majestic lion standing proudly on a cliff overlooking the savanna"
        art = "cinematic photorealistic 8k"
        char = "Golden male lion with dark flowing mane and amber eyes"

        composed = compose_scene_prompt(
            scene_prompt=prompt,
            art_style=art,
            character_style=char,
            quality_suffix="hyperdetailed, masterpiece",
        )

        assert prompt in composed
        assert char in composed
        assert "in " + art in composed
        assert "hyperdetailed, masterpiece" in composed
