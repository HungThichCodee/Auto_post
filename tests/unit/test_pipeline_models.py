"""
tests/unit/test_pipeline_models.py
Unit tests for pipeline data models (ScrapedVideo, Scene, StoryScript, VideoOutput, UploadResult).
"""

import pytest
from datetime import datetime
from src.models.pipeline_models import (
    ScrapedVideo,
    Scene,
    StoryScript,
    VideoOutput,
    UploadResult,
)


def test_scraped_video_instantiation_and_defaults():
    """Verify ScrapedVideo field defaults, auto-initialization, and to_dict serialization."""
    video = ScrapedVideo(
        title="Bí Ẩn Loài Kiến Tí Hon",
        description="Khám phá tập tính của loài kiến.",
        channel="Thế Giới Côn Trùng",
        url="https://www.youtube.com/watch?v=sample123",
        views="25K",
        duration_str="0:45",
        tags=["kien", "dongvat"],
    )
    assert video.title == "Bí Ẩn Loài Kiến Tí Hon"
    assert video.channel == "Thế Giới Côn Trùng"
    assert video.platform == "youtube"
    assert video.is_short is False
    assert video.scraped_at != ""
    assert "Bí Ẩn Loài Kiến Tí Hon" in video.raw_text

    # Test backward compatibility properties
    assert video.text == video.raw_text
    assert video.source_url == video.url
    assert video.author == video.channel
    assert video.hashtags == ["kien", "dongvat"]
    assert video.engagement["views"] == "25K"

    # Test serialization
    data = video.to_dict()
    assert data["title"] == "Bí Ẩn Loài Kiến Tí Hon"
    assert data["author"] == "Thế Giới Côn Trùng"


def test_scraped_video_shorts_url_detection():
    """Verify automatic is_short flag detection for YouTube Shorts URLs."""
    short_video = ScrapedVideo(
        title="Shorts Video",
        url="https://www.youtube.com/shorts/abcdef12345",
    )
    assert short_video.is_short is True


def test_scraped_video_empty_title_validation():
    """Verify empty title raises ValueError."""
    with pytest.raises(ValueError, match="title"):
        ScrapedVideo(title="")
    with pytest.raises(ValueError, match="title"):
        ScrapedVideo(title="   ")


def test_scraped_video_from_dict_and_aliases():
    """Verify deserialization from dict with legacy ScrapedContent aliases."""
    data = {
        "text": "Tiêu đề từ text\nMô tả video\nViews: 10K",
        "source_url": "https://youtu.be/legacy123",
        "author": "Kênh Cũ",
        "hashtags": ["cu", "test"],
        "engagement": {"views": "10K", "duration": "1:00"}
    }
    video = ScrapedVideo.from_dict(data)
    assert video.title == "Tiêu đề từ text"
    assert video.url == "https://youtu.be/legacy123"
    assert video.channel == "Kênh Cũ"
    assert video.tags == ["cu", "test"]
    assert video.views == "10K"


def test_scene_instantiation_and_validation():
    """Verify Scene instantiation, validation rules, and default properties."""
    scene = Scene(
        scene_id=1,
        narration_text_vi="Xin chào các bạn đã quay trở lại.",
        image_prompt_en="A sunny morning in a forest, 3D Pixar style",
    )
    assert scene.scene_id == 1
    assert scene.duration == 0.0
    assert scene.status == "pending"
    assert scene.subtitle_text == "Xin chào các bạn đã quay trở lại."
    assert scene.image_path is None
    assert scene.audio_path is None

    # Mutate properties
    scene.duration = 4.5
    scene.image_path = "output/scene_1.png"
    scene.audio_path = "output/audio/scene_1.mp3"
    scene.status = "completed"

    data = scene.to_dict()
    assert data["duration"] == 4.5
    assert data["status"] == "completed"
    assert data["image_path"] == "output/scene_1.png"


def test_scene_invalid_inputs():
    """Verify invalid scene inputs raise ValueError."""
    # Invalid scene_id
    with pytest.raises(ValueError, match="scene_id"):
        Scene(scene_id=0, narration_text_vi="A", image_prompt_en="B")

    # Empty narration
    with pytest.raises(ValueError, match="narration_text_vi"):
        Scene(scene_id=1, narration_text_vi="", image_prompt_en="B")

    # Empty image prompt
    with pytest.raises(ValueError, match="image_prompt_en"):
        Scene(scene_id=1, narration_text_vi="A", image_prompt_en="")

    # Negative duration
    with pytest.raises(ValueError, match="duration"):
        Scene(scene_id=1, narration_text_vi="A", image_prompt_en="B", duration=-1.0)

    # Invalid status
    with pytest.raises(ValueError, match="status"):
        Scene(scene_id=1, narration_text_vi="A", image_prompt_en="B", status="unknown_status")


def test_scene_from_dict_aliases():
    """Verify Scene.from_dict parses various LLM naming aliases."""
    raw_dict = {
        "scene_number": 2,
        "narration": "Đây là phân cảnh 2.",
        "image_prompt": "A magical forest at twilight",
        "duration": "5.5"
    }
    scene = Scene.from_dict(raw_dict)
    assert scene.scene_id == 2
    assert scene.narration_text_vi == "Đây là phân cảnh 2."
    assert scene.image_prompt_en == "A magical forest at twilight"
    assert scene.duration == 5.5


def test_story_script_aggregation_and_properties():
    """Verify StoryScript scene aggregation, duration sums, and aspect ratio logic."""
    scenes = [
        Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", duration=15.0),
        Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2", duration=15.0),
        Scene(scene_id=3, narration_text_vi="Cảnh 3", image_prompt_en="Prompt 3", duration=15.0),
    ]
    script = StoryScript(
        title_vi="Chuyện Chú Mèo Cam",
        description_vi="Một câu chuyện hoạt hình 3D.",
        theme="Mèo cam phiêu lưu",
        art_style="3D Pixar style",
        scenes=scenes,
    )
    assert script.scene_count == 3
    assert script.total_duration == 45.0
    assert script.is_shorts is True
    assert script.target_aspect_ratio == "9:16"


def test_story_script_regular_video_duration():
    """Verify StoryScript with duration >= 60s classifies as regular 16:9 video."""
    scenes = [
        Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", duration=25.0),
        Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2", duration=25.0),
        Scene(scene_id=3, narration_text_vi="Cảnh 3", image_prompt_en="Prompt 3", duration=20.0),
    ]
    script = StoryScript(
        title_vi="Anime Hành Trình Kỳ Ảo",
        description_vi="Video dài 70 giây.",
        theme="Anime",
        art_style="Makoto Shinkai style",
        scenes=scenes,
    )
    assert script.total_duration == 70.0
    assert script.is_shorts is False
    assert script.target_aspect_ratio == "16:9"


def test_story_script_auto_scene_conversion_and_add_scene():
    """Verify raw scene dictionaries are automatically converted into Scene objects."""
    raw_script = {
        "title_vi": "Khám Phá Vũ Trụ",
        "description_vi": "Bí ẩn các vì sao.",
        "theme": "Khoa học vũ trụ",
        "art_style": "Cinematic sci-fi",
        "scenes": [
            {"scene_id": 1, "narration_text_vi": "Vũ trụ bao la", "image_prompt_en": "Deep space nebula", "duration": 10.0}
        ]
    }
    script = StoryScript.from_dict(raw_script)
    assert len(script.scenes) == 1
    assert isinstance(script.scenes[0], Scene)

    # Test add_scene with dict
    script.add_scene({"narration": "Hố đen kỳ bí", "image_prompt": "Supermassive black hole", "duration": 12.0})
    assert len(script.scenes) == 2
    assert script.scenes[1].scene_id == 2
    assert script.scenes[1].narration_text_vi == "Hố đen kỳ bí"


def test_video_output_model_and_validation():
    """Verify VideoOutput model serialization and validation constraints."""
    vo = VideoOutput(
        video_path="output/final_video_001.mp4",
        duration=45.2,
        aspect_ratio="9:16",
        resolution=(1080, 1920),
        fps=30,
        file_size_bytes=1048576,
        scene_count=3,
    )
    assert vo.aspect_ratio == "9:16"
    assert vo.resolution == (1080, 1920)
    assert vo.file_size_bytes == 1048576

    data = vo.to_dict()
    assert data["resolution"] == [1080, 1920]

    # Deserialization
    vo_restored = VideoOutput.from_dict(data)
    assert vo_restored.resolution == (1080, 1920)
    assert vo_restored.duration == 45.2

    # Validation errors
    with pytest.raises(ValueError, match="duration"):
        VideoOutput(video_path="test.mp4", duration=0.0, aspect_ratio="9:16", resolution=(1080, 1920))

    with pytest.raises(ValueError, match="aspect_ratio"):
        VideoOutput(video_path="test.mp4", duration=10.0, aspect_ratio="invalid_ratio", resolution=(1080, 1920))


def test_upload_result_model_and_states():
    """Verify UploadResult states (published, dry_run, failed) and backward compatibility."""
    # Published state
    pub = UploadResult(success=True, video_id="yt_vid_123", url="https://youtu.be/yt_vid_123", status="published")
    assert pub.success is True
    assert pub.status == "published"
    assert pub.post_url == "https://youtu.be/yt_vid_123"

    # Dry-run state
    dry = UploadResult(success=True, status="dry_run")
    assert dry.status == "dry_run"

    # Failed state auto-assignment
    failed = UploadResult(success=False, error="Selector timeout")
    assert failed.status == "failed"
    assert failed.error == "Selector timeout"

    # Invalid status
    with pytest.raises(ValueError, match="status"):
        UploadResult(success=True, status="non_existent_status")
