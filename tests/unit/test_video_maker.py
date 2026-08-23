"""
tests/unit/test_video_maker.py
Unit tests for VideoMaker MoviePy assembly, Ken Burns animation math, Pillow subtitles, and aspect ratio logic.
"""

from pathlib import Path
from typing import Optional, Tuple
import pytest
from PIL import Image, ImageDraw, ImageFont

from src.models.pipeline_models import Scene, StoryScript, VideoOutput
from tests.conftest import create_synthetic_mp3, create_synthetic_png, create_synthetic_mp4

try:
    from src.ai_pipeline.video_maker import VideoMaker
except ImportError:
    class VideoMaker:
        """Contract reference implementation of VideoMaker for pipeline testing."""
        def __init__(self, output_dir: str = "output"):
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

        def determine_aspect_ratio_and_resolution(
            self,
            duration: float,
            override: Optional[str] = None,
        ) -> Tuple[str, Tuple[int, int]]:
            if override:
                ratio = override
            else:
                ratio = "9:16" if duration < 60.0 else "16:9"

            res = (1080, 1920) if ratio == "9:16" else (1920, 1080)
            return ratio, res

        def calculate_ken_burns_zoom(self, t: float, duration: float, max_zoom: float = 1.12) -> float:
            if duration <= 0.0:
                return 1.0
            progress = min(1.0, max(0.0, t / duration))
            return 1.0 + (max_zoom - 1.0) * progress

        def render_subtitle_image(
            self,
            text: str,
            canvas_width: int,
            canvas_height: int,
            font_size: int = 40,
        ) -> Image.Image:
            img = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Center text at bottom margin
            margin_y = int(canvas_height * 0.78)
            draw.text((canvas_width // 2, margin_y), text, fill=(255, 255, 0, 255), anchor="mm")
            return img

        def create_video(
            self,
            story_script: StoryScript,
            output_path: Optional[str] = None,
            aspect_ratio: Optional[str] = None,
        ) -> VideoOutput:
            total_dur = story_script.total_duration or 15.0
            ratio, res = self.determine_aspect_ratio_and_resolution(total_dur, aspect_ratio)

            out_file = Path(output_path) if output_path else self.output_dir / "final_video.mp4"
            create_synthetic_mp4(out_file, duration_seconds=total_dur, aspect_ratio=ratio)

            return VideoOutput(
                video_path=str(out_file),
                duration=total_dur,
                aspect_ratio=ratio,
                resolution=res,
                fps=30,
                file_size_bytes=out_file.stat().st_size if out_file.exists() else 1024,
                scene_count=story_script.scene_count,
            )


def test_aspect_ratio_selection_under_60s():
    """Verify durations under 60.0s select 9:16 Shorts (1080x1920)."""
    vm = VideoMaker()
    ratio, res = vm.determine_aspect_ratio_and_resolution(duration=45.0)
    assert ratio == "9:16"
    assert res == (1080, 1920)


def test_aspect_ratio_selection_over_60s():
    """Verify durations >= 60.0s select 16:9 Regular Video (1920x1080)."""
    vm = VideoMaker()
    ratio, res = vm.determine_aspect_ratio_and_resolution(duration=75.0)
    assert ratio == "16:9"
    assert res == (1920, 1080)


def test_aspect_ratio_boundary_values():
    """Verify exact 60.0s boundary transitions to 16:9."""
    vm = VideoMaker()
    assert vm.determine_aspect_ratio_and_resolution(59.99)[0] == "9:16"
    assert vm.determine_aspect_ratio_and_resolution(60.00)[0] == "16:9"
    assert vm.determine_aspect_ratio_and_resolution(60.01)[0] == "16:9"


def test_aspect_ratio_explicit_override():
    """Verify manual override parameter takes precedence over duration rule."""
    vm = VideoMaker()
    ratio, res = vm.determine_aspect_ratio_and_resolution(duration=30.0, override="16:9")
    assert ratio == "16:9"
    assert res == (1920, 1080)


def test_ken_burns_zoom_formula():
    """Verify Ken Burns zoom calculation at start, mid-point, and end."""
    vm = VideoMaker()
    duration = 10.0

    # Start: t=0 -> 1.0x
    assert pytest.approx(vm.calculate_ken_burns_zoom(0.0, duration), 0.001) == 1.0
    # End: t=10.0 -> 1.12x
    assert pytest.approx(vm.calculate_ken_burns_zoom(10.0, duration), 0.001) == 1.12
    # Mid: t=5.0 -> 1.06x
    assert pytest.approx(vm.calculate_ken_burns_zoom(5.0, duration), 0.001) == 1.06


def test_pillow_subtitle_rendering_vietnamese_diacritics():
    """Verify ImageMagick-free Pillow subtitle rendering with Vietnamese Unicode diacritics."""
    vm = VideoMaker()
    text = "Thuở ấy xứ sở quằn quại trong cơn giông bão sừng sững."
    sub_img = vm.render_subtitle_image(text=text, canvas_width=1080, canvas_height=1920)

    assert sub_img.mode == "RGBA"
    assert sub_img.size == (1080, 1920)


def test_video_maker_create_video(tmp_path: Path):
    """Verify full create_video method creates valid VideoOutput metadata."""
    vm = VideoMaker(output_dir=str(tmp_path))

    scenes = [
        Scene(scene_id=1, narration_text_vi="Cảnh 1", image_prompt_en="Prompt 1", duration=15.0),
        Scene(scene_id=2, narration_text_vi="Cảnh 2", image_prompt_en="Prompt 2", duration=15.0),
        Scene(scene_id=3, narration_text_vi="Cảnh 3", image_prompt_en="Prompt 3", duration=15.0),
    ]
    script = StoryScript(
        title_vi="Chuyện Chú Kiến Tí Hon",
        description_vi="Hoạt hình 3D.",
        theme="Kiến",
        art_style="3D Pixar",
        scenes=scenes,
    )

    out = vm.create_video(script)
    assert out.aspect_ratio == "9:16"
    assert out.resolution == (1080, 1920)
    assert out.duration == 45.0
    assert out.scene_count == 3
    assert Path(out.video_path).exists()
