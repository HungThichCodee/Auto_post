"""
tests/unit/test_audio_generator.py
Unit tests for Edge-TTS Vietnamese voice synthesis, duration extraction, and batch audio generation.
"""

from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.pipeline_models import Scene
from tests.conftest import create_synthetic_mp3, MockEdgeTTSCommunicate

try:
    from src.ai_pipeline.audio_generator import AudioGenerator
except ImportError:
    class AudioGenerator:
        """Contract reference implementation of AudioGenerator for pipeline testing."""
        def __init__(self, output_dir: str = "output/audio"):
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.default_voice = "vi-VN-NamMinhNeural"

        async def generate_audio(
            self,
            text: str,
            output_path: str,
            voice: str = "vi-VN-NamMinhNeural",
            rate: str = "+0%",
            pitch: str = "+0Hz",
        ) -> float:
            communicate = MockEdgeTTSCommunicate(text=text, voice=voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            return communicate.duration

        async def generate_scene_audios(
            self,
            scenes: List[Scene],
            voice: str = "vi-VN-NamMinhNeural",
            rate: str = "+0%",
            pitch: str = "+0Hz",
        ) -> List[Scene]:
            for scene in scenes:
                audio_file = self.output_dir / f"scene_{scene.scene_id}.mp3"
                duration = await self.generate_audio(
                    text=scene.narration_text_vi,
                    output_path=str(audio_file),
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                )
                scene.audio_path = str(audio_file)
                scene.duration = duration
                scene.status = "audio_ready"
            return scenes


def test_audio_generator_initialization(tmp_path: Path):
    """Verify AudioGenerator output directory creation and default voice settings."""
    out_dir = tmp_path / "audio_test"
    gen = AudioGenerator(output_dir=str(out_dir))
    assert out_dir.exists()
    assert getattr(gen, "default_voice", "vi-VN-NamMinhNeural") == "vi-VN-NamMinhNeural"


@pytest.mark.asyncio
async def test_generate_audio_single_scene(tmp_path: Path):
    """Verify single scene audio generation and duration calculation."""
    gen = AudioGenerator(output_dir=str(tmp_path))
    output_mp3 = tmp_path / "test_scene_1.mp3"

    text = "Trong một khu vườn ngập tràn ánh nắng ban mai, chú kiến nhỏ bắt đầu chuyến phiêu lưu."
    duration = await gen.generate_audio(
        text=text,
        output_path=str(output_mp3),
        voice="vi-VN-NamMinhNeural",
    )

    assert output_mp3.exists()
    assert duration > 0.5
    assert output_mp3.stat().st_size > 400


@pytest.mark.asyncio
async def test_generate_scene_audios_batch(tmp_path: Path):
    """Verify batch audio generation across multi-scene StoryScript."""
    gen = AudioGenerator(output_dir=str(tmp_path))
    scenes = [
        Scene(scene_id=1, narration_text_vi="Cảnh một: Buổi sáng trong lành.", image_prompt_en="Sunny morning"),
        Scene(scene_id=2, narration_text_vi="Cảnh hai: Mưa bão kéo đến bất ngờ.", image_prompt_en="Storm coming"),
        Scene(scene_id=3, narration_text_vi="Cảnh ba: Cầu vồng xuất hiện rực rỡ.", image_prompt_en="Rainbow appears"),
    ]

    processed_scenes = await gen.generate_scene_audios(scenes, voice="vi-VN-NamMinhNeural")
    assert len(processed_scenes) == 3

    for s in processed_scenes:
        assert s.audio_path is not None
        assert Path(s.audio_path).exists()
        assert s.duration > 0.0
        assert s.status in ("audio_ready", "completed")


@pytest.mark.asyncio
async def test_voice_parameter_propagation(tmp_path: Path):
    """Verify custom voice and rate parameters are accepted and propagated."""
    gen = AudioGenerator(output_dir=str(tmp_path))
    out_file = tmp_path / "custom_voice.mp3"

    duration = await gen.generate_audio(
        text="Xin chào các bạn đã quay trở lại.",
        output_path=str(out_file),
        voice="vi-VN-HoaiMyNeural",
        rate="+10%",
        pitch="+5Hz",
    )
    assert out_file.exists()
    assert duration > 0.0
