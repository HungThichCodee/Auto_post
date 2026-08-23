"""
tests/e2e/test_tier3_pairwise_combinations.py
Tier 3: Pairwise Combinatorial Interaction Testing across pipeline configurations.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.pipeline_models import Scene, StoryScript, VideoOutput
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import ImageGenerator
from src.poster.youtube_poster import YoutubePoster
from tests.conftest import create_synthetic_png_bytes, create_synthetic_mp3, create_synthetic_mp4


PAIRWISE_COMBINATIONS = [
    # (Niche, Duration, Expected Ratio, Art Style, Dry Run)
    ("stories", 45.0, "9:16", "3D Pixar animation", True),
    ("stories", 75.0, "16:9", "Makoto Shinkai anime", False),
    ("humor", 30.0, "9:16", "Comic gag style", True),
    ("humor", 65.0, "16:9", "Funny 3D caricature", False),
    ("health", 50.0, "9:16", "Clean photorealistic 8k", True),
    ("health", 80.0, "16:9", "Infographic 3D style", False),
    ("science", 40.0, "9:16", "Sci-fi cinematic space", True),
    ("science", 90.0, "16:9", "Epic astronomy documentary", False),
    ("mythology", 55.0, "9:16", "Vietnamese lacquer painting", True),
    ("mythology", 120.0, "16:9", "Ancient mythological epic", False),
]


@pytest.mark.parametrize("niche,duration,expected_ratio,art_style,dry_run", PAIRWISE_COMBINATIONS)
@pytest.mark.asyncio
async def test_t3_pairwise_pipeline_combinations(
    tmp_path: Path,
    niche: str,
    duration: float,
    expected_ratio: str,
    art_style: str,
    dry_run: bool,
):
    """T3-PAIR-01..10: Cross-feature interaction test matrix."""
    # 1. Build StoryScript
    scenes = [
        Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", duration=duration / 2),
        Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2", duration=duration / 2),
    ]
    script = StoryScript(
        title_vi=f"Tiêu đề {niche}",
        description_vi=f"Mô tả {niche}",
        theme=niche,
        art_style=art_style,
        niche=niche,
        scenes=scenes,
    )

    assert script.target_aspect_ratio == expected_ratio
    assert script.art_style == art_style

    # 2. Mock Image Gen
    gen = ImageGenerator(output_dir=str(tmp_path))
    valid_png = create_synthetic_png_bytes(512, 512)
    mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_res
        img_path = await gen.generate_image(f"{script.scenes[0].image_prompt_en}, {art_style}", width=512, height=512)
        assert Path(img_path).exists()

    # 3. Mock Video File Creation
    video_file = tmp_path / f"video_{niche}.mp4"
    create_synthetic_mp4(video_file, duration_seconds=duration, aspect_ratio=expected_ratio)
    assert video_file.exists()

    # 4. Mock Poster Execution
    mock_bm = MagicMock()
    poster = YoutubePoster(browser_manager=mock_bm, cookies_json="[]")
    upload_res = await poster.upload_video(
        video_path=str(video_file),
        title=script.title_vi,
        description=script.description_vi,
        dry_run=dry_run,
    )

    if dry_run:
        assert upload_res.status == "dry_run"
        assert upload_res.success is True
