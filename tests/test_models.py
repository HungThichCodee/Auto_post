"""
Unit tests for Pipeline Data Models (Milestone M1).
Tests ScrapedVideo, Scene, StoryScript, VideoOutput, UploadResult for:
- Default values and auto-initialization
- Validation and error cases
- Backward compatibility and properties
- Recursive round-trip JSON/dict serialization and deserialization
- Dict alias parsing from LLM / legacy outputs
"""

import pytest
from datetime import datetime
from src.models import (
    ScrapedVideo,
    Scene,
    StoryScript,
    VideoOutput,
    UploadResult,
)
from src.scraper.base_scraper import ScrapedContent


# ==========================================
# 1. Package Exports Test
# ==========================================

def test_models_package_imports():
    """Verify all pipeline models are exported properly from src.models."""
    assert ScrapedVideo is not None
    assert Scene is not None
    assert StoryScript is not None
    assert VideoOutput is not None
    assert UploadResult is not None


# ==========================================
# 2. ScrapedVideo Tests
# ==========================================

def test_scraped_video_creation_defaults():
    """Test ScrapedVideo creation with default and auto-populated fields."""
    video = ScrapedVideo(title="Top 10 Strange Animals")
    assert video.title == "Top 10 Strange Animals"
    assert video.description == ""
    assert video.channel == ""
    assert video.url == ""
    assert video.timestamp == ""
    assert video.views == ""
    assert video.duration_str == ""
    assert video.tags == []
    assert video.raw_text == "Top 10 Strange Animals"
    assert video.platform == "youtube"
    assert video.is_short is False
    assert video.scraped_at != ""
    # Check ISO timestamp format
    datetime.fromisoformat(video.scraped_at)


def test_scraped_video_empty_title_validation():
    """Test that empty or whitespace title raises ValueError."""
    with pytest.raises(ValueError, match="title"):
        ScrapedVideo(title="")
    with pytest.raises(ValueError, match="title"):
        ScrapedVideo(title="   ")


def test_scraped_video_raw_text_assembly():
    """Test that raw_text assembles title, description, and views when omitted."""
    video = ScrapedVideo(
        title="Epic Story",
        description="A tale of magic and wonder.",
        views="50K views"
    )
    assert "Epic Story" in video.raw_text
    assert "A tale of magic and wonder." in video.raw_text
    assert "Views: 50K views" in video.raw_text


def test_scraped_video_compat_properties():
    """Test backward compatibility properties matching ScrapedContent."""
    video = ScrapedVideo(
        title="Cat Adventures",
        description="Funny cats compilation",
        channel="PetChannel",
        url="https://www.youtube.com/watch?v=12345",
        views="100K views",
        duration_str="03:45",
        timestamp="1 day ago",
        tags=["#cats", "#funny"]
    )
    assert isinstance(video, ScrapedContent)
    assert video.text == video.raw_text
    assert video.source_url == "https://www.youtube.com/watch?v=12345"
    assert video.author == "PetChannel"
    assert video.hashtags == ["#cats", "#funny"]
    assert video.engagement["views"] == "100K views"
    assert video.engagement["duration"] == "03:45"
    assert video.engagement["timestamp"] == "1 day ago"


def test_scraped_video_compat_setters():
    """Test property setters on ScrapedVideo for backward compatibility."""
    video = ScrapedVideo(title="Initial Title")
    video.text = "Updated raw text"
    assert video.raw_text == "Updated raw text"
    assert video.text == "Updated raw text"

    video.source_url = "https://youtube.com/watch?v=abc"
    assert video.url == "https://youtube.com/watch?v=abc"

    video.author = "New Author"
    assert video.channel == "New Author"

    video.hashtags = ["#newtag"]
    assert video.tags == ["#newtag"]

    video.engagement = {"views": "20K", "duration": "01:30", "timestamp": "now"}
    assert video.views == "20K"
    assert video.duration_str == "01:30"
    assert video.timestamp == "now"


def test_scraped_video_shorts_auto_detection():
    """Test that URLs containing /shorts/ automatically set is_short=True."""
    video = ScrapedVideo(title="Quick Short", url="https://www.youtube.com/shorts/xyz123")
    assert video.is_short is True


def test_scraped_video_roundtrip_serialization():
    """Test round-trip serialization for ScrapedVideo."""
    original = ScrapedVideo(
        title="Test Video",
        description="Detailed description",
        channel="MyChannel",
        url="https://youtube.com/watch?v=999",
        timestamp="2 days ago",
        views="12K views",
        duration_str="04:20",
        tags=["#test", "#video"],
        is_short=False
    )
    d = original.to_dict()
    restored = ScrapedVideo.from_dict(d)
    assert restored.title == original.title
    assert restored.description == original.description
    assert restored.channel == original.channel
    assert restored.url == original.url
    assert restored.views == original.views
    assert restored.duration_str == original.duration_str
    assert restored.tags == original.tags
    assert restored.is_short == original.is_short


def test_scraped_video_from_legacy_dict():
    """Test deserializing legacy ScrapedContent dictionary format."""
    legacy_data = {
        "text": "Legacy Title Line\nLegacy description line",
        "source_url": "https://youtube.com/watch?v=legacy",
        "author": "LegacyAuthor",
        "hashtags": ["#legacy"],
        "engagement": {"views": "1M views", "duration": "10:00"}
    }
    video = ScrapedVideo.from_dict(legacy_data)
    assert video.title == "Legacy Title Line"
    assert video.url == "https://youtube.com/watch?v=legacy"
    assert video.channel == "LegacyAuthor"
    assert video.tags == ["#legacy"]
    assert video.views == "1M views"
    assert video.duration_str == "10:00"


# ==========================================
# 3. Scene Tests
# ==========================================

def test_scene_creation_defaults():
    """Test Scene creation and default values."""
    scene = Scene(
        scene_id=1,
        narration_text_vi="Ngày xửa ngày xưa có một chú mèo nhỏ.",
        image_prompt_en="A tiny cute fluffy kitten playing in a vibrant flower meadow."
    )
    assert scene.scene_id == 1
    assert scene.narration_text_vi == "Ngày xửa ngày xưa có một chú mèo nhỏ."
    assert scene.image_prompt_en == "A tiny cute fluffy kitten playing in a vibrant flower meadow."
    assert scene.image_path is None
    assert scene.audio_path is None
    assert scene.duration == 0.0
    assert scene.status == "pending"
    assert scene.subtitle_text == scene.narration_text_vi


def test_scene_validation_errors():
    """Test Scene validation errors for invalid fields."""
    # Invalid scene_id (< 1)
    with pytest.raises(ValueError, match="scene_id"):
        Scene(scene_id=0, narration_text_vi="Test", image_prompt_en="Prompt")
    with pytest.raises(ValueError, match="scene_id"):
        Scene(scene_id=-1, narration_text_vi="Test", image_prompt_en="Prompt")

    # Empty narration_text_vi
    with pytest.raises(ValueError, match="narration_text_vi"):
        Scene(scene_id=1, narration_text_vi="", image_prompt_en="Prompt")
    with pytest.raises(ValueError, match="narration_text_vi"):
        Scene(scene_id=1, narration_text_vi="   ", image_prompt_en="Prompt")

    # Empty image_prompt_en
    with pytest.raises(ValueError, match="image_prompt_en"):
        Scene(scene_id=1, narration_text_vi="Test", image_prompt_en="")
    with pytest.raises(ValueError, match="image_prompt_en"):
        Scene(scene_id=1, narration_text_vi="Test", image_prompt_en="   ")

    # Negative duration
    with pytest.raises(ValueError, match="duration"):
        Scene(scene_id=1, narration_text_vi="Test", image_prompt_en="Prompt", duration=-1.5)

    # Invalid status
    with pytest.raises(ValueError, match="Invalid status"):
        Scene(scene_id=1, narration_text_vi="Test", image_prompt_en="Prompt", status="nonexistent")


def test_scene_roundtrip_serialization():
    """Test Scene serialization and deserialization."""
    scene = Scene(
        scene_id=2,
        narration_text_vi="Bỗng nhiên một cơn bão ập tới.",
        image_prompt_en="Dark stormy clouds gathering over the meadow, dramatic lighting.",
        image_path="/tmp/scene2.png",
        audio_path="/tmp/scene2.mp3",
        duration=4.82,
        status="completed",
        subtitle_text="Cơn bão ập tới!"
    )
    d = scene.to_dict()
    restored = Scene.from_dict(d)
    assert restored == scene


def test_scene_from_llm_dict_aliases():
    """Test Scene.from_dict() handling of various LLM response aliases."""
    raw_llm_item = {
        "scene_number": 3,
        "narration": "Chú mèo tìm thấy một hang đá bí mật.",
        "image_prompt": "Kitten entering a glowing mystical cave, cinematic 8k",
        "duration": "5.5"
    }
    scene = Scene.from_dict(raw_llm_item)
    assert scene.scene_id == 3
    assert scene.narration_text_vi == "Chú mèo tìm thấy một hang đá bí mật."
    assert scene.image_prompt_en == "Kitten entering a glowing mystical cave, cinematic 8k"
    assert scene.duration == 5.5
    assert scene.status == "pending"


# ==========================================
# 4. StoryScript Tests
# ==========================================

def test_story_script_creation():
    """Test StoryScript creation with scenes."""
    s1 = Scene(scene_id=1, narration_text_vi="Đoạn 1", image_prompt_en="Prompt 1", duration=3.0)
    s2 = Scene(scene_id=2, narration_text_vi="Đoạn 2", image_prompt_en="Prompt 2", duration=4.0)

    script = StoryScript(
        title_vi="Hành Trình Mèo Con",
        description_vi="Câu chuyện về chú mèo dũng cảm.",
        theme="Lòng dũng cảm",
        art_style="3D Pixar animation",
        scenes=[s1, s2],
        niche="stories",
        character_style="Cute ginger kitten with blue eyes"
    )
    assert script.title_vi == "Hành Trình Mèo Con"
    assert script.scene_count == 2
    assert script.total_duration == 7.0
    assert script.is_shorts is True
    assert script.target_aspect_ratio == "9:16"


def test_story_script_empty_title_validation():
    """Test that empty title raises ValueError."""
    with pytest.raises(ValueError, match="title_vi"):
        StoryScript(title_vi="", description_vi="Desc", theme="Theme", art_style="Style")


def test_story_script_nested_scenes_dict_conversion():
    """Test that raw dicts in scenes list are auto-converted to Scene objects."""
    raw_scenes = [
        {"scene_id": 1, "narration_text_vi": "Nội dung 1", "image_prompt_en": "Prompt 1", "duration": 2.5},
        {"scene_id": 2, "narration_text_vi": "Nội dung 2", "image_prompt_en": "Prompt 2", "duration": 3.5},
    ]
    script = StoryScript(
        title_vi="Chuyện Cổ Tích",
        description_vi="Mô tả",
        theme="Cổ tích",
        art_style="Anime",
        scenes=raw_scenes
    )
    assert len(script.scenes) == 2
    assert all(isinstance(s, Scene) for s in script.scenes)
    assert script.scenes[0].duration == 2.5
    assert script.scenes[1].narration_text_vi == "Nội dung 2"


def test_story_script_duration_and_aspect_ratio_calc():
    """Test duration calculations and 9:16 vs 16:9 aspect ratio switching."""
    # Under 60 seconds -> Shorts 9:16
    short_scenes = [
        Scene(scene_id=i, narration_text_vi=f"Đoạn {i}", image_prompt_en=f"Prompt {i}", duration=10.0)
        for i in range(1, 6)
    ]
    short_script = StoryScript(
        title_vi="Video Ngắn",
        description_vi="Desc",
        theme="Shorts",
        art_style="Style",
        scenes=short_scenes
    )
    assert short_script.total_duration == 50.0
    assert short_script.is_shorts is True
    assert short_script.target_aspect_ratio == "9:16"

    # Exactly or over 60 seconds -> Regular 16:9
    long_scenes = [
        Scene(scene_id=i, narration_text_vi=f"Đoạn {i}", image_prompt_en=f"Prompt {i}", duration=15.0)
        for i in range(1, 6)
    ]
    long_script = StoryScript(
        title_vi="Video Dài",
        description_vi="Desc",
        theme="Long",
        art_style="Style",
        scenes=long_scenes
    )
    assert long_script.total_duration == 75.0
    assert long_script.is_shorts is False
    assert long_script.target_aspect_ratio == "16:9"


def test_story_script_add_scene():
    """Test add_scene method with both Scene object and dict."""
    script = StoryScript(
        title_vi="Tiêu đề",
        description_vi="Mô tả",
        theme="Chủ đề",
        art_style="Style"
    )
    assert script.scene_count == 0

    # Add via Scene instance
    script.add_scene(Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1"))
    assert script.scene_count == 1

    # Add via dict
    script.add_scene({"narration_text_vi": "Cảnh 2", "image_prompt_en": "Prompt 2"})
    assert script.scene_count == 2
    assert script.scenes[1].scene_id == 2
    assert script.scenes[1].narration_text_vi == "Cảnh 2"


def test_story_script_roundtrip_serialization():
    """Test full recursive round-trip serialization of StoryScript."""
    s1 = Scene(scene_id=1, narration_text_vi="Lời thoại 1", image_prompt_en="Image 1", duration=4.0)
    s2 = Scene(scene_id=2, narration_text_vi="Lời thoại 2", image_prompt_en="Image 2", duration=5.0)

    original = StoryScript(
        title_vi="Hành Trình Kì Diệu",
        description_vi="Mô tả chi tiết với #hashtag",
        theme="Phiêu lưu",
        art_style="3D Pixar animation",
        scenes=[s1, s2],
        niche="stories",
        character_style="Young brave explorer boy",
        summary="Cậu bé khám phá thế giới bí ẩn.",
        themes=["Phiêu lưu", "Dũng cảm"]
    )

    d = original.to_dict()
    restored = StoryScript.from_dict(d)

    assert restored.title_vi == original.title_vi
    assert restored.description_vi == original.description_vi
    assert restored.theme == original.theme
    assert restored.art_style == original.art_style
    assert restored.scene_count == 2
    assert restored.scenes[0].narration_text_vi == s1.narration_text_vi
    assert restored.scenes[1].image_prompt_en == s2.image_prompt_en
    assert restored.character_style == original.character_style
    assert restored.themes == original.themes


def test_story_script_from_gemini_raw_json():
    """Test parsing raw JSON structure output by Gemini 2.0 Flash."""
    raw_gemini_dict = {
        "title": "Mèo Con Và Chiếc Hộp Bí Mật",
        "description": "Câu chuyện cảm động về tình bạn #meocon #truyenhay",
        "topic": "Tình bạn",
        "image_style": "Cute 3D cartoon style, soft lighting",
        "character_description": "Small white kitten with green eyes",
        "scenes": [
            {
                "scene_number": 1,
                "narration": "Một buổi sáng đẹp trời, Mèo Con tìm thấy một chiếc hộp.",
                "image_prompt": "Cute white kitten looking curiously at a small wooden box on green grass"
            },
            {
                "scene_number": 2,
                "narration": "Khi mở nắp hộp, một ánh sáng lấp lánh phát ra.",
                "image_prompt": "Glowing magical sparkles rising from an open wooden box, kitten looking amazed"
            }
        ]
    }
    script = StoryScript.from_dict(raw_gemini_dict)
    assert script.title_vi == "Mèo Con Và Chiếc Hộp Bí Mật"
    assert script.theme == "Tình bạn"
    assert script.art_style == "Cute 3D cartoon style, soft lighting"
    assert script.scene_count == 2
    assert script.scenes[0].scene_id == 1
    assert script.scenes[0].narration_text_vi == "Một buổi sáng đẹp trời, Mèo Con tìm thấy một chiếc hộp."
    assert script.scenes[1].scene_id == 2


# ==========================================
# 5. VideoOutput Tests
# ==========================================

def test_video_output_creation():
    """Test VideoOutput creation with valid fields."""
    output = VideoOutput(
        video_path="output/videos/video_123.mp4",
        duration=42.5,
        aspect_ratio="9:16",
        resolution=(1080, 1920),
        fps=30,
        file_size_bytes=15000000,
        scene_count=4,
        has_subtitles=True
    )
    assert output.video_path == "output/videos/video_123.mp4"
    assert output.duration == 42.5
    assert output.aspect_ratio == "9:16"
    assert output.resolution == (1080, 1920)
    assert output.fps == 30
    assert output.file_size_bytes == 15000000
    assert output.scene_count == 4
    assert output.has_subtitles is True
    assert output.created_at != ""


def test_video_output_validation():
    """Test VideoOutput validation errors."""
    # Empty video_path
    with pytest.raises(ValueError, match="video_path"):
        VideoOutput(video_path="", duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920))

    # Duration <= 0
    with pytest.raises(ValueError, match="duration"):
        VideoOutput(video_path="v.mp4", duration=0.0, aspect_ratio="9:16", resolution=(1080, 1920))
    with pytest.raises(ValueError, match="duration"):
        VideoOutput(video_path="v.mp4", duration=-5.0, aspect_ratio="9:16", resolution=(1080, 1920))

    # FPS <= 0
    with pytest.raises(ValueError, match="fps"):
        VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920), fps=0)

    # Negative file size
    with pytest.raises(ValueError, match="file_size_bytes"):
        VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920), file_size_bytes=-1)

    # Invalid resolution
    with pytest.raises(ValueError, match="resolution"):
        VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=(0, 1920))

    # Invalid aspect ratio
    with pytest.raises(ValueError, match="Invalid aspect_ratio"):
        VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="21:9", resolution=(1080, 1920))


def test_video_output_roundtrip_serialization():
    """Test VideoOutput round-trip serialization."""
    original = VideoOutput(
        video_path="output/render.mp4",
        duration=65.2,
        aspect_ratio="16:9",
        resolution=(1920, 1080),
        fps=30,
        file_size_bytes=25000000,
        scene_count=6,
        has_subtitles=True
    )
    d = original.to_dict()
    assert isinstance(d["resolution"], list)
    restored = VideoOutput.from_dict(d)
    assert restored.video_path == original.video_path
    assert restored.duration == original.duration
    assert restored.aspect_ratio == original.aspect_ratio
    assert restored.resolution == (1920, 1080)
    assert restored.fps == 30


# ==========================================
# 6. UploadResult Tests
# ==========================================

def test_upload_result_success():
    """Test UploadResult on successful upload."""
    result = UploadResult(
        success=True,
        platform="youtube",
        video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status="published"
    )
    assert result.success is True
    assert result.platform == "youtube"
    assert result.video_id == "dQw4w9WgXcQ"
    assert result.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert result.post_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert result.status == "published"
    assert result.error is None
    assert result.uploaded_at != ""


def test_upload_result_failure_auto_status():
    """Test UploadResult failure normalizes published status to failed."""
    result = UploadResult(
        success=False,
        platform="youtube",
        error="Upload button not clickable"
    )
    assert result.success is False
    assert result.status == "failed"
    assert result.error == "Upload button not clickable"


def test_upload_result_dry_run():
    """Test UploadResult in dry_run mode."""
    result = UploadResult(
        success=True,
        status="dry_run",
        video_id=None,
        url=None
    )
    assert result.success is True
    assert result.status == "dry_run"
    assert result.post_url == ""


def test_upload_result_roundtrip_serialization():
    """Test UploadResult round-trip serialization."""
    original = UploadResult(
        success=True,
        platform="youtube",
        video_id="abc123xyz",
        url="https://youtube.com/watch?v=abc123xyz",
        status="published"
    )
    d = original.to_dict()
    restored = UploadResult.from_dict(d)
    assert restored.success == original.success
    assert restored.video_id == original.video_id
    assert restored.url == original.url
    assert restored.status == original.status
    assert restored.error == original.error


def test_upload_result_from_legacy_dict():
    """Test UploadResult from legacy PostResult dict with post_url."""
    legacy_data = {
        "success": True,
        "platform": "youtube",
        "post_url": "https://youtube.com/watch?v=legacy123",
        "error": None
    }
    result = UploadResult.from_dict(legacy_data)
    assert result.success is True
    assert result.url == "https://youtube.com/watch?v=legacy123"
    assert result.post_url == "https://youtube.com/watch?v=legacy123"
