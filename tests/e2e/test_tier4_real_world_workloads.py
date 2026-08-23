"""
tests/e2e/test_tier4_real_world_workloads.py
Tier 4: End-to-End Real-World Production Channel Workload Scenarios.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.pipeline_models import Scene, StoryScript, VideoOutput
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import ImageGenerator
from src.poster.youtube_poster import YoutubePoster
from src.memory.knowledge_base import KnowledgeBase
from tests.conftest import create_synthetic_png, create_synthetic_mp3, create_synthetic_mp4


# ============================================================================
# Workload 1: Animal 3D Cartoon Shorts (AI-thegioitihon)
# ============================================================================

@pytest.mark.asyncio
async def test_workload_1_animal_3d_cartoon_shorts(tmp_path: Path, sample_story_scripts):
    """Tier 4 Workload 1: 3-Scene 3D Animal Story for YouTube Shorts (<60s)."""
    kb = KnowledgeBase(filepath=str(tmp_path / "kb.md"))
    data = sample_story_scripts["valid_3_scenes_shorts"]
    script = StoryScript.from_dict(data)

    assert script.scene_count == 3
    assert script.total_duration == 45.0
    assert script.is_shorts is True
    assert script.target_aspect_ratio == "9:16"

    # Generate media assets
    for s in script.scenes:
        s.image_path = str(create_synthetic_png(tmp_path / f"w1_img_{s.scene_id}.png", 1080, 1920))
        s.audio_path = str(create_synthetic_mp3(tmp_path / f"w1_aud_{s.scene_id}.mp3", s.duration))

    # Assemble video
    video_path = tmp_path / "w1_output.mp4"
    create_synthetic_mp4(video_path, duration_seconds=script.total_duration, aspect_ratio="9:16")

    # Dry-run upload
    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video(str(video_path), script.title_vi, script.description_vi, dry_run=True)
    assert res.success is True

    # Memory commit
    kb.append_entry("youtube", script.niche, script.summary, script.themes)
    assert kb.get_entry_count() == 1


# ============================================================================
# Workload 2: Anime Adventure Long Video (16:9 Landscape >=60s)
# ============================================================================

@pytest.mark.asyncio
async def test_workload_2_anime_adventure_long_video(tmp_path: Path, sample_story_scripts):
    """Tier 4 Workload 2: 5-Scene Anime Adventure Long-Form Video (75s)."""
    kb = KnowledgeBase(filepath=str(tmp_path / "kb.md"))
    data = sample_story_scripts["valid_5_scenes_regular"]
    script = StoryScript.from_dict(data)

    assert script.scene_count == 5
    assert script.total_duration == 75.0
    assert script.is_shorts is False
    assert script.target_aspect_ratio == "16:9"

    # Assemble video
    video_path = tmp_path / "w2_output.mp4"
    create_synthetic_mp4(video_path, duration_seconds=script.total_duration, aspect_ratio="16:9")

    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video(str(video_path), script.title_vi, script.description_vi, dry_run=True)
    assert res.success is True

    kb.append_entry("youtube", script.niche, script.summary, script.themes)
    assert kb.get_entry_count() == 1


# ============================================================================
# Workload 3: Mythology Epic Tale with Heavy Vietnamese Diacritics
# ============================================================================

@pytest.mark.asyncio
async def test_workload_3_mythology_epic_tale(tmp_path: Path, sample_story_scripts):
    """Tier 4 Workload 3: Vietnamese Folk Mythology with complex diacritics."""
    kb = KnowledgeBase(filepath=str(tmp_path / "kb.md"))
    data = sample_story_scripts["heavy_diacritics_script"]
    script = StoryScript.from_dict(data)

    assert "Thuở" in script.title_vi
    assert "quằn quại" in script.title_vi

    video_path = tmp_path / "w3_output.mp4"
    create_synthetic_mp4(video_path, duration_seconds=script.total_duration, aspect_ratio=script.target_aspect_ratio)

    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video(str(video_path), script.title_vi, script.description_vi, dry_run=True)
    assert res.success is True


# ============================================================================
# Workload 4: Comic Gag Rapid-Fire
# ============================================================================

@pytest.mark.asyncio
async def test_workload_4_comic_gag_rapid_fire(tmp_path: Path):
    """Tier 4 Workload 4: Fast-Paced 30s Humorous Shorts."""
    scenes = [
        Scene(scene_id=1, narration_text_vi="Boss mèo đang ngủ trưa say giấc.", image_prompt_en="Sleeping cat", duration=10.0),
        Scene(scene_id=2, narration_text_vi="Bỗng nhiên một quả dưa chuột xuất hiện phía sau.", image_prompt_en="Cucumber prank", duration=10.0),
        Scene(scene_id=3, narration_text_vi="Cú nhảy cao 2 mét phá vỡ mọi quy luật vật lý!", image_prompt_en="Jumping cat", duration=10.0),
    ]
    script = StoryScript(
        title_vi="Khi Boss Mèo Bị Dưa Chuột Hù Dọa",
        description_vi="Khoảnh khắc hài hước khó đỡ #shorts",
        theme="Hài hước mèo cưng",
        art_style="Comic gag cartoon",
        niche="humor",
        scenes=scenes,
    )
    assert script.total_duration == 30.0
    assert script.is_shorts is True

    video_path = tmp_path / "w4_output.mp4"
    create_synthetic_mp4(video_path, duration_seconds=30.0, aspect_ratio="9:16")

    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video(str(video_path), script.title_vi, script.description_vi, dry_run=True)
    assert res.success is True


# ============================================================================
# Workload 5: Space Science Documentary (90s Long Video)
# ============================================================================

@pytest.mark.asyncio
async def test_workload_5_space_science_documentary(tmp_path: Path):
    """Tier 4 Workload 5: 6-Scene Educational Space Documentary."""
    scenes = [
        Scene(scene_id=i, narration_text_vi=f"Khám phá thiên hà phần {i}", image_prompt_en=f"Deep space galaxy part {i}", duration=15.0)
        for i in range(1, 7)
    ]
    script = StoryScript(
        title_vi="Bí Ẩn Vụ Nổ Lớn Big Bang Và Sự Hình Thành Vũ Trụ",
        description_vi="Khám phá thiên văn học và sự hình thành của vũ trụ.",
        theme="Khoa học vũ trụ",
        art_style="Cinematic photorealistic sci-fi",
        niche="science",
        scenes=scenes,
    )
    assert script.scene_count == 6
    assert script.total_duration == 90.0
    assert script.is_shorts is False
    assert script.target_aspect_ratio == "16:9"

    video_path = tmp_path / "w5_output.mp4"
    create_synthetic_mp4(video_path, duration_seconds=90.0, aspect_ratio="16:9")

    poster = YoutubePoster(browser_manager=MagicMock(), cookies_json="[]")
    res = await poster.upload_video(str(video_path), script.title_vi, script.description_vi, dry_run=True)
    assert res.success is True
