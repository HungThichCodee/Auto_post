"""
Adversarial Stress Test Suite for Pipeline Data Models (Milestone M1).
Authors: challenger_m1_1 (Critic / Specialist)

Exhaustive stress testing across 7 challenge dimensions:
1. Boundary & Invariant validation (negative numbers, zero dimensions, invalid enums, whitespace strings).
2. Corrupted / Fuzzed / Malformed JSON and dict structures in from_dict().
3. Deep nested roundtrips with multi-scene StoryScript and JSON encoding integrity.
4. Vietnamese diacritics, combining marks, emojis, and Unicode preservation.
5. Duck-typing and complete bi-directional compatibility with legacy ScrapedContent and PostResult callers.
6. Dynamic aspect ratio & duration classification oracles.
7. High-volume fuzzing generator & stress test.
"""

import json
import pytest
import random
import string
from datetime import datetime
from typing import Dict, Any

from src.models import (
    ScrapedVideo,
    Scene,
    StoryScript,
    VideoOutput,
    UploadResult,
)
from src.scraper.base_scraper import ScrapedContent


# ==============================================================================
# 1. BOUNDARY & INVARIANT VALIDATION STRESS TESTS
# ==============================================================================

class TestBoundaryAndInvariantValidation:
    """Stress test boundary conditions, invalid types, and invariant checks."""

    @pytest.mark.parametrize("bad_title", [
        "",
        "   ",
        "\t\t\n",
        "\r\n   \t",
        None,
    ])
    def test_scraped_video_invalid_titles(self, bad_title):
        """ScrapedVideo must reject empty, whitespace-only, or None titles."""
        with pytest.raises(ValueError, match="title"):
            ScrapedVideo(title=bad_title)

    @pytest.mark.parametrize("bad_id", [0, -1, -100, -9999])
    def test_scene_invalid_scene_ids(self, bad_id):
        """Scene must reject non-positive scene_id values."""
        with pytest.raises(ValueError, match="scene_id"):
            Scene(scene_id=bad_id, narration_text_vi="Đoạn thoại", image_prompt_en="Visual prompt")

    @pytest.mark.parametrize("bad_type_id", [1.5, "1", [1], {"id": 1}, None])
    def test_scene_non_integer_scene_ids(self, bad_type_id):
        """Scene must reject float, string, or collection types for scene_id."""
        with pytest.raises(ValueError, match="scene_id"):
            Scene(scene_id=bad_type_id, narration_text_vi="Đoạn thoại", image_prompt_en="Visual prompt")

    @pytest.mark.parametrize("bad_narration", ["", "   ", "\t\n", None])
    def test_scene_empty_narration(self, bad_narration):
        """Scene must reject empty or whitespace-only narration text."""
        with pytest.raises(ValueError, match="narration_text_vi"):
            Scene(scene_id=1, narration_text_vi=bad_narration, image_prompt_en="Visual prompt")

    @pytest.mark.parametrize("bad_prompt", ["", "   ", "\t\n", None])
    def test_scene_empty_prompt(self, bad_prompt):
        """Scene must reject empty or whitespace-only visual prompts."""
        with pytest.raises(ValueError, match="image_prompt_en"):
            Scene(scene_id=1, narration_text_vi="Đoạn thoại", image_prompt_en=bad_prompt)

    @pytest.mark.parametrize("bad_duration", [-0.0001, -1.0, -999.0])
    def test_scene_negative_duration(self, bad_duration):
        """Scene must reject negative durations."""
        with pytest.raises(ValueError, match="duration"):
            Scene(scene_id=1, narration_text_vi="Đoạn thoại", image_prompt_en="Prompt", duration=bad_duration)

    @pytest.mark.parametrize("bad_status", [
        "unknown", "ready", "error", "done", "in_progress", "PENDING", ""
    ])
    def test_scene_invalid_status(self, bad_status):
        """Scene must reject unrecognized status strings."""
        with pytest.raises(ValueError, match="Invalid status"):
            Scene(scene_id=1, narration_text_vi="Đoạn thoại", image_prompt_en="Prompt", status=bad_status)

    @pytest.mark.parametrize("bad_title", ["", "   ", "\t\n", None])
    def test_story_script_empty_title(self, bad_title):
        """StoryScript must reject empty or whitespace-only title."""
        with pytest.raises(ValueError, match="title_vi"):
            StoryScript(title_vi=bad_title, description_vi="Mô tả", theme="Theme", art_style="Style")

    @pytest.mark.parametrize("invalid_scene_item", [
        123,
        "not a scene",
        None,
        ["nested", "list"],
        3.14
    ])
    def test_story_script_invalid_scene_type(self, invalid_scene_item):
        """StoryScript must raise TypeError if scenes contains unsupported types."""
        with pytest.raises(TypeError, match="Expected Scene instance or dict"):
            StoryScript(
                title_vi="Tiêu đề",
                description_vi="Mô tả",
                theme="Theme",
                art_style="Style",
                scenes=[invalid_scene_item]
            )

    @pytest.mark.parametrize("bad_path", ["", "   ", "\t\n", None])
    def test_video_output_empty_path(self, bad_path):
        """VideoOutput must reject empty or whitespace-only path."""
        with pytest.raises(ValueError, match="video_path"):
            VideoOutput(video_path=bad_path, duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920))

    @pytest.mark.parametrize("bad_duration", [0.0, -0.1, -10.0])
    def test_video_output_non_positive_duration(self, bad_duration):
        """VideoOutput must reject zero or negative duration."""
        with pytest.raises(ValueError, match="duration"):
            VideoOutput(video_path="v.mp4", duration=bad_duration, aspect_ratio="9:16", resolution=(1080, 1920))

    @pytest.mark.parametrize("bad_fps", [0, -1, -30])
    def test_video_output_non_positive_fps(self, bad_fps):
        """VideoOutput must reject non-positive FPS."""
        with pytest.raises(ValueError, match="fps"):
            VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920), fps=bad_fps)

    @pytest.mark.parametrize("bad_file_size", [-1, -100, -99999])
    def test_video_output_negative_file_size(self, bad_file_size):
        """VideoOutput must reject negative file sizes."""
        with pytest.raises(ValueError, match="file_size_bytes"):
            VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=(1080, 1920), file_size_bytes=bad_file_size)

    @pytest.mark.parametrize("bad_res", [
        (0, 1920),
        (1080, 0),
        (-1080, 1920),
        (1080, -1920),
        (1080,),
        (1080, 1920, 30),
        [],
        [1080],
    ])
    def test_video_output_invalid_resolution(self, bad_res):
        """VideoOutput must reject invalid resolution tuples or non-positive dimensions."""
        with pytest.raises(ValueError, match="resolution"):
            VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio="9:16", resolution=bad_res)

    @pytest.mark.parametrize("bad_aspect", ["21:9", "4:3", "custom", "16-9", ""])
    def test_video_output_invalid_aspect_ratio(self, bad_aspect):
        """VideoOutput must reject unsupported aspect ratio strings."""
        with pytest.raises(ValueError, match="Invalid aspect_ratio"):
            VideoOutput(video_path="v.mp4", duration=10.0, aspect_ratio=bad_aspect, resolution=(1080, 1920))

    @pytest.mark.parametrize("bad_status", ["uploaded", "complete", "error", "pending", ""])
    def test_upload_result_invalid_status(self, bad_status):
        """UploadResult must reject invalid status values."""
        with pytest.raises(ValueError, match="Invalid upload status"):
            UploadResult(success=True, status=bad_status)


# ==============================================================================
# 2. MALFORMED / FUZZED / ALIAS DICT DESERIALIZATION STRESS TESTS
# ==============================================================================

class TestMalformedAndAliasedDictParsing:
    """Stress test from_dict() resilience against corrupted and varied inputs."""

    def test_scraped_video_from_dict_with_extra_garbage_keys(self):
        """Extra unknown keys should be filtered out without causing errors."""
        data = {
            "title": "Chuyện Lạ Thế Giới",
            "description": "Mô tả video",
            "unknown_field_1": 12345,
            "__internal_metadata": {"key": "val"},
            "random_tokens": [1, 2, 3]
        }
        video = ScrapedVideo.from_dict(data)
        assert video.title == "Chuyện Lạ Thế Giới"
        assert video.description == "Mô tả video"
        assert not hasattr(video, "unknown_field_1")

    def test_scraped_video_from_dict_non_dict_engagement(self):
        """Non-dict engagement in legacy payloads must be handled safely."""
        data = {
            "title": "Cat Video",
            "engagement": "100K views, 5:00"  # String instead of dict
        }
        video = ScrapedVideo.from_dict(data)
        assert video.title == "Cat Video"
        assert video.views == ""

    def test_scraped_video_from_legacy_dict_with_single_line_text(self):
        """Legacy text without newlines should become title and raw_text."""
        data = {
            "text": "Only one title line here",
            "source_url": "https://youtu.be/test1234",
            "author": "TestAuthor",
            "hashtags": ["#t1", "#t2"]
        }
        video = ScrapedVideo.from_dict(data)
        assert video.title == "Only one title line here"
        assert video.raw_text == "Only one title line here"
        assert video.url == "https://youtu.be/test1234"
        assert video.channel == "TestAuthor"
        assert video.tags == ["#t1", "#t2"]

    @pytest.mark.parametrize("alias_key,alias_val", [
        ("scene_number", 5),
        ("id", 5),
        ("scene", 5),
    ])
    def test_scene_from_dict_id_aliases(self, alias_key, alias_val):
        """Scene.from_dict() must parse diverse LLM ID keys."""
        data = {
            alias_key: alias_val,
            "narration": "Lời kể cảnh 5",
            "image_prompt": "Cinematic 8k visual prompt"
        }
        scene = Scene.from_dict(data)
        assert scene.scene_id == 5
        assert scene.narration_text_vi == "Lời kể cảnh 5"
        assert scene.image_prompt_en == "Cinematic 8k visual prompt"

    @pytest.mark.parametrize("narr_key", [
        "narration", "narration_vi", "text_vi", "text", "vietnamese"
    ])
    def test_scene_from_dict_narration_aliases(self, narr_key):
        """Scene.from_dict() must parse diverse LLM narration keys."""
        data = {
            "scene_id": 1,
            narr_key: "Lời thoại tiếng Việt cực chuẩn.",
            "image_prompt": "Visual prompt"
        }
        scene = Scene.from_dict(data)
        assert scene.narration_text_vi == "Lời thoại tiếng Việt cực chuẩn."

    @pytest.mark.parametrize("prompt_key", [
        "image_prompt", "prompt_en", "prompt", "english_prompt"
    ])
    def test_scene_from_dict_prompt_aliases(self, prompt_key):
        """Scene.from_dict() must parse diverse LLM prompt keys."""
        data = {
            "scene_id": 1,
            "narration": "Lời thoại",
            prompt_key: "A detailed fantasy castle on a floating island"
        }
        scene = Scene.from_dict(data)
        assert scene.image_prompt_en == "A detailed fantasy castle on a floating island"

    def test_scene_from_dict_string_duration_coercion(self):
        """String duration in dict must be coerced to float."""
        data = {
            "scene_id": 1,
            "narration": "Lời thoại",
            "image_prompt": "Prompt",
            "duration": "14.75"
        }
        scene = Scene.from_dict(data)
        assert isinstance(scene.duration, float)
        assert scene.duration == 14.75

    def test_story_script_from_dict_title_and_style_aliases(self):
        """StoryScript.from_dict() must parse title, description, and style aliases."""
        data = {
            "title_vn": "Cuộc Phiêu Lưu Của Thỏ Trắng",
            "description_vn": "Tập 1 về Thỏ Trắng thông minh",
            "topic": "Động vật",
            "image_style": "Watercolor whimsical style",
            "scenes": [
                {
                    "scene_number": 1,
                    "narration": "Thỏ Trắng đang đi dạo trong rừng.",
                    "image_prompt": "Cute white bunny walking in enchanted forest"
                }
            ]
        }
        script = StoryScript.from_dict(data)
        assert script.title_vi == "Cuộc Phiêu Lưu Của Thỏ Trắng"
        assert script.description_vi == "Tập 1 về Thỏ Trắng thông minh"
        assert script.theme == "Động vật"
        assert script.art_style == "Watercolor whimsical style"
        assert script.scene_count == 1
        assert script.scenes[0].scene_id == 1

    def test_video_output_from_dict_type_coercions(self):
        """VideoOutput.from_dict() must correctly coerce string/list numbers to typed values."""
        data = {
            "video_path": "output/render_final.mp4",
            "duration": "58.6",
            "aspect_ratio": "9:16",
            "resolution": [1080, 1920],
            "fps": "30",
            "file_size_bytes": "2048000"
        }
        vo = VideoOutput.from_dict(data)
        assert vo.video_path == "output/render_final.mp4"
        assert isinstance(vo.duration, float)
        assert vo.duration == 58.6
        assert isinstance(vo.resolution, tuple)
        assert vo.resolution == (1080, 1920)
        assert isinstance(vo.fps, int)
        assert vo.fps == 30
        assert isinstance(vo.file_size_bytes, int)
        assert vo.file_size_bytes == 2048000


# ==============================================================================
# 3. VIETNAMESE DIACRITICS & UNICODE PRESERVATION STRESS TESTS
# ==============================================================================

class TestVietnameseUnicodeStress:
    """Stress test Vietnamese tone marks, combining characters, emojis, and UTF-8 roundtrips."""

    VIETNAMESE_SAMPLE_TEXT = (
        "Thuở xưa, tại một ngôi làng nhỏ ven bờ sông Thu Bồn, có một chú bé tên là "
        "Nguyễn Văn Bình. Cậu bé rất thích ngắm nhìn những cánh diều ngũ sắc bay lượn "
        "giữa bầu trời trong xanh, rực rỡ ánh nắng ban mai! 🇻🇳 🌟 🐾 "
        "\"Đừng bao giờ từ bỏ ước mơ của mình!\" — lời dạy của bà nội kính yêu."
    )

    def test_vietnamese_diacritics_in_scraped_video(self):
        """ScrapedVideo must preserve complex Vietnamese characters and emojis."""
        video = ScrapedVideo(
            title="Khám Phá Bí Ẩn Đại Dương: 10 Sinh Vật Kỳ Lạ Nhất 🌊🦑",
            description=self.VIETNAMESE_SAMPLE_TEXT,
            channel="Kênh Khoa Học & Đời Sống 🔬",
            tags=["#khoahọc", "#đạidương", "#bíẩn", "#sinhvật", "#kỳthú"]
        )
        assert "🌊🦑" in video.title
        assert "Thu Bồn" in video.description
        assert "Kênh Khoa Học & Đời Sống 🔬" in video.channel
        assert "#đạidương" in video.tags

        # JSON Roundtrip
        d = video.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        loaded_d = json.loads(json_str)
        restored = ScrapedVideo.from_dict(loaded_d)

        assert restored.title == video.title
        assert restored.description == video.description
        assert restored.channel == video.channel
        assert restored.tags == video.tags

    def test_vietnamese_diacritics_in_story_script_and_scenes(self):
        """StoryScript and Scene must preserve complex Vietnamese tone marks throughout JSON serialization."""
        scenes = [
            Scene(
                scene_id=1,
                narration_text_vi="Mèo Ú ngồi bên hiên nhà, lặng lẽ nhìn những giọt mưa rớt tí tách trên mái ngói rêu phong.",
                image_prompt_en="Chubby orange cat sitting by old wooden porch in Hanoi, gentle rain dripping, watercolor anime style"
            ),
            Scene(
                scene_id=2,
                narration_text_vi="Bỗng một chú sẻ nhỏ ướt sũng sà xuống, cất tiếng kêu chiêm chiếp cầu cứu! 🐦💦",
                image_prompt_en="Tiny shivering wet sparrow landing near the orange cat, delicate feathers, cinematic lighting",
                subtitle_text="Chú sẻ nhỏ cất tiếng kêu chiêm chiếp cầu cứu!"
            )
        ]

        script = StoryScript(
            title_vi="Chuyện Chú Mèo Ú Và Chú Chim Sẻ Nhỏ Trong Cơn Mưa Rào 🐱🌧️",
            description_vi=self.VIETNAMESE_SAMPLE_TEXT,
            theme="Tình thương và sự sẻ chia giữa muôn loài",
            art_style="3D Pixar animation with warm Vietnamese lighting",
            scenes=scenes,
            niche="stories"
        )

        # Roundtrip through JSON string
        json_payload = json.dumps(script.to_dict(), ensure_ascii=False, indent=2)
        deserialized_data = json.loads(json_payload)
        restored_script = StoryScript.from_dict(deserialized_data)

        assert restored_script.title_vi == script.title_vi
        assert restored_script.description_vi == script.description_vi
        assert restored_script.theme == script.theme
        assert restored_script.scene_count == 2
        assert restored_script.scenes[0].narration_text_vi == scenes[0].narration_text_vi
        assert restored_script.scenes[1].narration_text_vi == scenes[1].narration_text_vi
        assert restored_script.scenes[1].subtitle_text == "Chú sẻ nhỏ cất tiếng kêu chiêm chiếp cầu cứu!"


# ==============================================================================
# 4. DUCK-TYPING & BACKWARD COMPATIBILITY STRESS TESTS
# ==============================================================================

class TestDuckTypingAndCompatibility:
    """Verify 100% interoperability with legacy ScrapedContent and PostResult callers."""

    def test_scraped_video_isinstance_scraped_content(self):
        """ScrapedVideo MUST be an instance of ScrapedContent."""
        video = ScrapedVideo(title="Test Video")
        assert isinstance(video, ScrapedContent)

    def test_scraped_video_duck_typing_readers(self):
        """Legacy callers accessing .text, .source_url, .author, .hashtags, .engagement."""
        video = ScrapedVideo(
            title="Amazing Discoveries",
            description="Detailed info",
            channel="Tech Channel",
            url="https://youtube.com/watch?v=tech123",
            views="250K views",
            duration_str="08:15",
            timestamp="3 days ago",
            tags=["#tech", "#science"]
        )

        # Legacy ScrapedContent interface access
        assert video.text == video.raw_text
        assert "Amazing Discoveries" in video.text
        assert video.source_url == "https://youtube.com/watch?v=tech123"
        assert video.author == "Tech Channel"
        assert video.hashtags == ["#tech", "#science"]
        assert video.engagement == {
            "views": "250K views",
            "duration": "08:15",
            "timestamp": "3 days ago"
        }

    def test_scraped_video_duck_typing_writers(self):
        """Mutating legacy properties must reflect in modern attributes and vice-versa."""
        video = ScrapedVideo(title="Initial")

        # Mutate via legacy properties
        video.text = "Overridden Raw Content"
        assert video.raw_text == "Overridden Raw Content"

        video.source_url = "https://youtube.com/shorts/short789"
        assert video.url == "https://youtube.com/shorts/short789"

        video.author = "Creator Studio"
        assert video.channel == "Creator Studio"

        video.hashtags = ["#mutated1", "#mutated2"]
        assert video.tags == ["#mutated1", "#mutated2"]

        video.engagement = {"views": "500K", "duration": "00:45", "timestamp": "just now"}
        assert video.views == "500K"
        assert video.duration_str == "00:45"
        assert video.timestamp == "just now"

    def test_upload_result_post_url_compatibility(self):
        """UploadResult must support post_url property for PostResult compatibility."""
        res = UploadResult(success=True, url="https://youtube.com/watch?v=result123")
        assert res.post_url == "https://youtube.com/watch?v=result123"

        # Setter
        res.post_url = "https://youtube.com/watch?v=mutated"
        assert res.url == "https://youtube.com/watch?v=mutated"
        assert res.post_url == "https://youtube.com/watch?v=mutated"

        # None URL returns empty string for post_url
        res_empty = UploadResult(success=True, url=None)
        assert res_empty.post_url == ""


# ==============================================================================
# 5. DYNAMIC ASPECT RATIO & SHORTS ORACLE TESTS
# ==============================================================================

class TestAspectRatioAndDurationOracles:
    """Verify exact mathematical bounds for Shorts (<60s) vs Regular (>=60s) videos."""

    @pytest.mark.parametrize("duration,expected_shorts,expected_ratio", [
        (10.0, True, "9:16"),
        (45.5, True, "9:16"),
        (59.99, True, "9:16"),
        (60.0, False, "16:9"),
        (60.01, False, "16:9"),
        (120.0, False, "16:9"),
        (600.0, False, "16:9"),
    ])
    def test_story_script_duration_boundary_oracles(self, duration, expected_shorts, expected_ratio):
        """Duration < 60s -> Shorts 9:16; Duration >= 60s -> Regular 16:9."""
        scene = Scene(
            scene_id=1,
            narration_text_vi="Lời thoại",
            image_prompt_en="Prompt",
            duration=duration
        )
        script = StoryScript(
            title_vi="Test Video",
            description_vi="Desc",
            theme="Theme",
            art_style="Style",
            scenes=[scene]
        )
        assert script.total_duration == pytest.approx(duration)
        assert script.is_shorts is expected_shorts
        assert script.target_aspect_ratio == expected_ratio

    def test_story_script_unrendered_zero_duration_fallback(self):
        """When durations are 0.0 (unrendered), <= 4 scenes is Shorts (9:16), > 4 is regular (16:9)."""
        scenes_3 = [
            Scene(scene_id=i, narration_text_vi=f"Cảnh {i}", image_prompt_en=f"Prompt {i}")
            for i in range(1, 4)
        ]
        script_3 = StoryScript(title_vi="3 Scenes", description_vi="", theme="T", art_style="S", scenes=scenes_3)
        assert script_3.total_duration == 0.0
        assert script_3.is_shorts is True
        assert script_3.target_aspect_ratio == "9:16"

        scenes_5 = [
            Scene(scene_id=i, narration_text_vi=f"Cảnh {i}", image_prompt_en=f"Prompt {i}")
            for i in range(1, 6)
        ]
        script_5 = StoryScript(title_vi="5 Scenes", description_vi="", theme="T", art_style="S", scenes=scenes_5)
        assert script_5.total_duration == 0.0
        assert script_5.is_shorts is False
        assert script_5.target_aspect_ratio == "16:9"

    def test_story_script_dynamic_add_scene(self):
        """Adding scenes dynamically updates count, duration, and aspect ratio."""
        script = StoryScript(title_vi="Dynamic Story", description_vi="", theme="T", art_style="S")
        assert script.scene_count == 0
        assert script.total_duration == 0.0

        # Add Scene 1 (25s)
        script.add_scene(Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", duration=25.0))
        assert script.scene_count == 1
        assert script.total_duration == 25.0
        assert script.is_shorts is True
        assert script.target_aspect_ratio == "9:16"

        # Add Scene 2 via dict (40s) -> total 65s -> flips to 16:9
        script.add_scene({"narration": "Cảnh 2", "image_prompt": "Prompt 2", "duration": 40.0})
        assert script.scene_count == 2
        assert script.scenes[1].scene_id == 2
        assert script.total_duration == 65.0
        assert script.is_shorts is False
        assert script.target_aspect_ratio == "16:9"


# ==============================================================================
# 6. FUZZING GENERATOR & HIGH-VOLUME STRESS TESTS
# ==============================================================================

class TestFuzzingAndScaleStress:
    """Fuzzing and large-scale workload verification."""

    @staticmethod
    def _random_vietnamese_string(length: int = 20) -> str:
        vietnamese_chars = "aáàảãạăắằẳẵặâấầẩẫậeéèẻẽẹêếềểễệiíìỉĩịoóòỏõọôốồổỗộơớờởỡợuúùủũụưứừửữựyýỳỷỹỵđ "
        return "".join(random.choice(vietnamese_chars) for _ in range(length)).strip() or "Mẫu văn bản"

    @staticmethod
    def _random_english_string(length: int = 30) -> str:
        chars = string.ascii_letters + " "
        return "".join(random.choice(chars) for _ in range(length)).strip() or "Cinematic visual illustration"

    def test_fuzz_scene_generation_and_roundtrip(self):
        """Fuzz test 200 random Scene objects through serialization and validation."""
        valid_statuses = ["pending", "image_ready", "audio_ready", "completed", "failed"]

        for i in range(1, 201):
            narr = self._random_vietnamese_string(random.randint(10, 80))
            prompt = self._random_english_string(random.randint(15, 100))
            dur = round(random.uniform(0.1, 120.0), 3)
            stat = random.choice(valid_statuses)

            scene = Scene(
                scene_id=i,
                narration_text_vi=narr,
                image_prompt_en=prompt,
                duration=dur,
                status=stat
            )

            # Assert invariants
            assert scene.scene_id == i
            assert scene.narration_text_vi == narr
            assert scene.image_prompt_en == prompt
            assert scene.duration == dur
            assert scene.status == stat

            # Roundtrip
            d = scene.to_dict()
            restored = Scene.from_dict(d)
            assert restored == scene

    def test_large_scale_story_script_with_500_scenes(self):
        """Stress test StoryScript with 500 scenes for memory and serialization performance."""
        scenes = [
            Scene(
                scene_id=i,
                narration_text_vi=f"Đoạn văn tự sự số {i} với đầy đủ dấu tiếng Việt.",
                image_prompt_en=f"Scene {i} photorealistic landscape in vivid colors",
                duration=3.5,
                status="completed"
            )
            for i in range(1, 501)
        ]

        script = StoryScript(
            title_vi="Đại Sử Thi 500 Cảnh Hoành Tráng",
            description_vi="Một kiệt tác hoạt hình dài tập",
            theme="Sử thi",
            art_style="Unreal Engine 5 Render",
            scenes=scenes,
            niche="epics"
        )

        assert script.scene_count == 500
        assert script.total_duration == 500 * 3.5
        assert script.is_shorts is False
        assert script.target_aspect_ratio == "16:9"

        # Complete JSON serialization & deserialization cycle
        json_data = json.dumps(script.to_dict())
        restored = StoryScript.from_dict(json.loads(json_data))

        assert restored.scene_count == 500
        assert restored.total_duration == 1750.0
        assert restored.scenes[499].scene_id == 500
        assert restored.scenes[499].narration_text_vi == "Đoạn văn tự sự số 500 với đầy đủ dấu tiếng Việt."
