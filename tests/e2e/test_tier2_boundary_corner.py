"""
tests/e2e/test_tier2_boundary_corner.py
Tier 2: Boundary Value Analysis (BVA), Stress, and Fault-Injection Edge Cases.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from PIL import Image, ImageDraw

from src.models.pipeline_models import Scene, StoryScript, VideoOutput, UploadResult
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import ImageGenerator
from src.poster.youtube_poster import YoutubePoster
from tests.conftest import create_synthetic_png_bytes


# ============================================================================
# 1. BVA Duration & Aspect Ratio Boundaries
# ============================================================================

@pytest.mark.parametrize("duration,expected_ratio", [
    (0.5, "9:16"),
    (30.0, "9:16"),
    (59.90, "9:16"),
    (59.99, "9:16"),
    (60.00, "16:9"),
    (60.01, "16:9"),
    (180.0, "16:9"),
    (3600.0, "16:9"),
])
def test_t2_duration_aspect_ratio_bva(duration, expected_ratio):
    """T2-BVA-01..08: Boundary Value Analysis for 60.0s Shorts vs Regular Video cutoff."""
    scenes = [Scene(scene_id=1, narration_text_vi="Cảnh kiểm thử", image_prompt_en="Prompt", duration=duration)]
    script = StoryScript(title_vi="Boundary Test", description_vi="", theme="", art_style="", scenes=scenes)
    assert script.target_aspect_ratio == expected_ratio


# ============================================================================
# 2. Vietnamese Diacritics & Typography Stress
# ============================================================================

def test_t2_vietnamese_diacritics_rendering():
    """T2-TYPO-01: Full Vietnamese tone marks and vowel combinations stress test."""
    complex_vietnamese_text = (
        "Thuở khai thiên lập địa, xứ sở quằn quại trong muôn vàn trắc trở. "
        "Ngọn núi sừng sững khuất tất sau ngàn tầng mây mù giông bão. "
        "Các nguyên âm dấu thanh: ắ, ằ, ẳ, ẵ, ặ, ế, ề, ể, ễ, ệ, ố, ồ, ổ, ỗ, ộ, "
        "ư, ứ, ừ, ử, ữ, ự, ý, ỳ, ỷ, ỹ, ỵ, đ."
    )
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((540, 1500), complex_vietnamese_text, fill=(255, 255, 0, 255), anchor="mm")
    assert img.size == (1080, 1920)


def test_t2_long_unbroken_text_wrapping():
    """T2-TYPO-02: Very long sentence (>300 chars) handles rendering without crashing."""
    long_text = "Đây là một câu chuyện vô cùng dài " * 15
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((540, 1500), long_text[:300], fill=(255, 255, 255, 255), anchor="mm")
    assert img.size == (1080, 1920)


# ============================================================================
# 3. Fault Injection: Gemini Rate Limits & Malformed Responses
# ============================================================================

@pytest.mark.asyncio
async def test_t2_gemini_rate_limit_resilience():
    """T2-FAULT-01: Handles Gemini HTTP 429 quota exhaustion gracefully."""
    rewriter = ContentRewriter(api_key="mock_key")
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(side_effect=Exception("429 Resource Exhausted"))
    rewriter.model = mock_model

    result = await rewriter.rewrite_content("Nội dung", {"name": "stories"})
    assert result["content"] == ""
    assert isinstance(result["themes"], list)


def test_t2_gemini_truncated_json_recovery():
    """T2-FAULT-02: Handles truncated / half-written JSON safely."""
    rewriter = ContentRewriter(api_key="mock_key")
    truncated_json = '{"title_vi": "Chuyện hay", "scenes": [{"scene_id": 1, "narration": "dở dang...'
    parsed = rewriter._parse_response(truncated_json)
    assert parsed["content"] == truncated_json
    assert isinstance(parsed["themes"], list)


# ============================================================================
# 4. Fault Injection: Image Generation Retries & Corrupt Payloads
# ============================================================================

@pytest.mark.asyncio
async def test_t2_pollinations_corrupt_payload_recovery(tmp_path: Path):
    """T2-FAULT-03: Discards <1KB corrupt image bytes and retries."""
    gen = ImageGenerator(output_dir=str(tmp_path))
    corrupt_data = b"TOO_SHORT"
    valid_data = create_synthetic_png_bytes(512, 512)

    res_bad = MagicMock(status_code=200, content=corrupt_data, raise_for_status=MagicMock())
    res_good = MagicMock(status_code=200, content=valid_data, raise_for_status=MagicMock())

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [res_bad, res_good]
        with patch("asyncio.sleep", new_callable=AsyncMock):
            path = await gen.generate_image("Prompt", width=512, height=512)
            assert Path(path).exists()
            assert mock_get.call_count == 2


# ============================================================================
# 5. Fault Injection: YouTube Poster Missing Files & Expired Cookies
# ============================================================================

@pytest.mark.asyncio
async def test_t2_poster_missing_video_file():
    """T2-FAULT-04: Fails fast if video file is missing."""
    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video("non_existent_path.mp4", "Title", "Desc", dry_run=False)
    assert res.success is False
    assert "not found" in (res.error or "").lower()
