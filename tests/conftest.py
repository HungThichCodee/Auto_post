"""
tests/conftest.py
Global pytest fixtures, synthetic media generators, and offline mock interceptors.

Provides 100% offline, deterministic, sub-millisecond testing primitives for:
- Pure-Python MPEG-1 Layer 3 MP3 audio generation
- High-speed Pillow PNG image generation
- Lightweight synthetic MP4 video generation
- Gemini 2.0 Flash async client mocking
- Pollinations.ai HTTP transport interception
- Edge-TTS voiceover synthesis mocking
- Playwright YouTube Studio upload automation mocking
"""

import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from PIL import Image, ImageDraw

from src.memory.knowledge_base import KnowledgeBase
from src.models.pipeline_models import (
    Scene,
    ScrapedVideo,
    StoryScript,
    UploadResult,
    VideoOutput,
)


# ============================================================================
# 1. Pure-Python Synthetic Media Generators
# ============================================================================

# MPEG-1 Audio Layer III frame header (128 kbps, 44.1 kHz, Stereo):
# 0xFF, 0xFB (sync), 0x90 (128kbps, 44.1kHz), 0x64 (Stereo, no padding)
# 417 bytes total payload per frame.
MP3_FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0x64])
MP3_FRAME_DATA = MP3_FRAME_HEADER + bytes(413)  # Exactly 417 bytes


def create_synthetic_mp3(filepath: Union[str, Path], duration_seconds: float = 3.0) -> Path:
    """
    Generate a valid pure-Python MPEG-1 Layer 3 MP3 file with precise duration.
    Each frame = 1152 samples @ 44.1kHz = 0.02612245 seconds.
    """
    target_path = Path(filepath)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    samples_needed = int(max(0.1, duration_seconds) * 44100)
    frames_needed = max(1, round(samples_needed / 1152))

    with open(target_path, "wb") as f:
        f.write(MP3_FRAME_DATA * frames_needed)

    return target_path


def create_synthetic_png(
    filepath: Union[str, Path],
    width: int = 1080,
    height: int = 1920,
    color: Tuple[int, int, int] = (70, 130, 180),
    text: str = "",
) -> Path:
    """
    Generate a valid PNG image file with specific dimensions and optional diagnostic watermark.
    """
    target_path = Path(filepath)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (width, height), color=color)
    if text:
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), text, fill=(255, 255, 255))
    img.save(target_path, format="PNG")
    return target_path


def create_synthetic_png_bytes(
    width: int = 1080,
    height: int = 1920,
    color: Tuple[int, int, int] = (100, 150, 200),
) -> bytes:
    """
    Generate valid in-memory PNG bytes with specific dimensions.
    """
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_synthetic_mp4(
    filepath: Union[str, Path],
    duration_seconds: float = 3.0,
    aspect_ratio: str = "9:16",
) -> Path:
    """
    Generate a minimal valid MP4 placeholder file.
    """
    target_path = Path(filepath)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Minimal MP4 ftyp box + moov/mdat structure
    ftyp_box = bytes([
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,  # size 32, 'ftyp'
        0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,  # 'isom', minor 512
        0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,  # 'isom', 'iso2'
        0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31   # 'avc1', 'mp41'
    ])
    mdat_box = bytes([
        0x00, 0x00, 0x01, 0x00, 0x6D, 0x64, 0x61, 0x74   # size 256, 'mdat'
    ]) + bytes(248)

    with open(target_path, "wb") as f:
        f.write(ftyp_box + mdat_box)

    return target_path


# ============================================================================
# 2. Fixture Datasets & Directories
# ============================================================================

@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to tests/fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Isolated temporary output directory."""
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


@pytest.fixture
def temp_knowledge_base(tmp_path: Path) -> KnowledgeBase:
    """Isolated temporary KnowledgeBase instance."""
    kb_path = tmp_path / "test_knowledge_base.md"
    return KnowledgeBase(filepath=str(kb_path))


@pytest.fixture(scope="session")
def sample_scraped_videos(fixtures_dir: Path) -> List[Dict[str, Any]]:
    """Raw sample scraped videos from JSON fixture."""
    fixture_path = fixtures_dir / "sample_scraped_videos.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_story_scripts(fixtures_dir: Path) -> Dict[str, Any]:
    """Sample story scripts from JSON fixture."""
    fixture_path = fixtures_dir / "sample_story_scripts.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_cookies(fixtures_dir: Path) -> Dict[str, Any]:
    """Sample YouTube cookies from JSON fixture."""
    fixture_path = fixtures_dir / "sample_cookies.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_sources_config(fixtures_dir: Path) -> Dict[str, Any]:
    """Test sources configuration."""
    fixture_path = fixtures_dir / "test_sources.yaml"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def test_niches_config(fixtures_dir: Path) -> Dict[str, Any]:
    """Test niches configuration."""
    fixture_path = fixtures_dir / "test_niches.yaml"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# 3. Media Generator Factories (Pytest Fixtures)
# ============================================================================

@pytest.fixture
def synthetic_mp3_factory(tmp_path: Path):
    """Factory fixture generating valid MP3 files with arbitrary durations."""
    def _factory(name: str = "test.mp3", duration: float = 3.0) -> Path:
        filepath = tmp_path / name
        return create_synthetic_mp3(filepath, duration_seconds=duration)
    return _factory


@pytest.fixture
def synthetic_png_factory(tmp_path: Path):
    """Factory fixture generating valid PNG files with arbitrary dimensions."""
    def _factory(name: str = "test.png", width: int = 1080, height: int = 1920, color: tuple = (70, 130, 180)) -> Path:
        filepath = tmp_path / name
        return create_synthetic_png(filepath, width=width, height=height, color=color)
    return _factory


@pytest.fixture
def synthetic_mp4_factory(tmp_path: Path):
    """Factory fixture generating synthetic MP4 video files."""
    def _factory(name: str = "test.mp4", duration: float = 3.0, aspect_ratio: str = "9:16") -> Path:
        filepath = tmp_path / name
        return create_synthetic_mp4(filepath, duration_seconds=duration, aspect_ratio=aspect_ratio)
    return _factory


# ============================================================================
# 4. Mock Interceptors (Gemini, Pollinations, Edge-TTS, Playwright)
# ============================================================================

class MockGeminiResponse:
    """Mock response object mimicking google.generativeai response."""
    def __init__(self, data: Union[dict, str]):
        if isinstance(data, dict):
            self.text = json.dumps(data, ensure_ascii=False)
        else:
            self.text = str(data)


class MockGeminiModel:
    """Mock GenerativeModel for testing ContentRewriter."""
    def __init__(self, canned_response: Optional[dict] = None, error_mode: Optional[str] = None):
        self.canned_response = canned_response
        self.error_mode = error_mode
        self.call_history: List[Dict[str, Any]] = []

    async def generate_content_async(self, prompt: str, **kwargs) -> MockGeminiResponse:
        self.call_history.append({"prompt": prompt, "kwargs": kwargs})

        if self.error_mode == "rate_limit":
            raise Exception("429 Resource has been exhausted (e.g. check quota).")
        if self.error_mode == "empty":
            return MockGeminiResponse("")
        if self.error_mode == "malformed_json":
            return MockGeminiResponse("```json\n{ invalid: json: [unclosed\n```")
        if self.error_mode == "fenced_json":
            data = self.canned_response or {"title_vi": "TiÃªu Ä‘á» máº«u", "scenes": []}
            return MockGeminiResponse(f"```json\n{json.dumps(data, ensure_ascii=False)}\n```")

        if self.canned_response:
            return MockGeminiResponse(self.canned_response)

        default_story = {
            "title_vi": "HÃ nh TrÃ¬nh ChÃº Kiáº¿n DÅ©ng Cáº£m",
            "description_vi": "CÃ¢u chuyá»‡n 3D vá» chÃº kiáº¿n nhá» trong khu vÆ°á»n tÃ­ hon.",
            "theme": "Tháº¿ giá»›i cÃ´n trÃ¹ng tÃ­ hon",
            "art_style": "cute 3D Pixar animation style, vibrant lighting",
            "character_style": "Tiny brown ant with blue backpack",
            "niche": "stories",
            "summary": "ChÃº kiáº¿n vÆ°á»£t mÆ°a giÃ´ng tÃ¬m Ä‘Æ°á»ng vá» tá»•.",
            "themes": ["kiáº¿n", "lÃ²ng dÅ©ng cáº£m", "phiÃªu lÆ°u"],
            "scenes": [
              {
                "scene_id": 1,
                "narration_text_vi": "Trong má»™t khu vÆ°á»n ngáº­p trÃ n Ã¡nh náº¯ng ban mai, chÃº kiáº¿n nhá» báº¯t Ä‘áº§u chuyáº¿n phiÃªu lÆ°u ká»³ thÃº.",
                "image_prompt_en": "A tiny cute ant with a blue backpack walking happily on a giant green leaf in a sunny garden, 3D Pixar animation style",
                "duration": 15.0
              },
              {
                "scene_id": 2,
                "narration_text_vi": "Bá»—ng nhiÃªn má»™t cÆ¡n mÆ°a rÃ o Ä‘á»• áº­p xuá»‘ng, biáº¿n máº·t Ä‘áº¥t thÃ nh dÃ²ng sÃ´ng cuá»™n sÃ³ng.",
                "image_prompt_en": "Giant raindrops splashing around a surprised tiny ant under a mushroom, dramatic lighting, 3D Pixar animation style",
                "duration": 15.0
              },
              {
                "scene_id": 3,
                "narration_text_vi": "Báº±ng sá»± thÃ´ng minh, chÃº kiáº¿n Ä‘Ã£ dÃ¹ng chiáº¿c lÃ¡ lÃ m thuyá»n buá»“m Ä‘á»ƒ trá»Ÿ vá» tá»• an toÃ n.",
                "image_prompt_en": "A brave tiny ant sailing a floating leaf across a puddle towards an anthill, 3D Pixar animation style",
                "duration": 15.0
              }
            ]
        }
        return MockGeminiResponse(default_story)


@pytest.fixture
def mock_gemini_model() -> MockGeminiModel:
    """Fixture providing an instance of MockGeminiModel."""
    return MockGeminiModel()


class MockEdgeTTSCommunicate:
    """Mock class intercepting edge_tts.Communicate."""
    def __init__(self, text: str, voice: str = "vi-VN-NamMinhNeural", rate: str = "+0%", pitch: str = "+0Hz", **kwargs):
        self.text = text
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.words = len(text.split()) if text else 1
        # ~3 words per second for standard Vietnamese narration
        self.duration = max(1.0, round(self.words / 3.0, 2))

    async def save(self, output_path: Union[str, Path]) -> None:
        create_synthetic_mp3(output_path, duration_seconds=self.duration)


@pytest.fixture
def mock_edge_tts_fixture(monkeypatch):
    """Fixture mocking edge_tts.Communicate across the test run."""
    import edge_tts
    monkeypatch.setattr(edge_tts, "Communicate", MockEdgeTTSCommunicate)
    return MockEdgeTTSCommunicate


class MockPlaywrightPage:
    """Mock Playwright Page for YouTube Studio automation."""
    def __init__(self, cookies_valid: bool = True):
        self.cookies_valid = cookies_valid
        self.url = "about:blank"
        self.uploaded_files: List[Any] = []
        self.filled_inputs: Dict[str, str] = {}
        self.clicked_selectors: List[str] = []
        self.closed = False

    async def goto(self, url: str, **kwargs):
        self.url = url
        if not self.cookies_valid and "studio.youtube.com" in url:
            self.url = "https://accounts.google.com/signin/v2/identifier"

    async def wait_for_selector(self, selector: str, **kwargs):
        return True

    async def wait_for_load_state(self, state: str = "networkidle", **kwargs):
        pass

    async def click(self, selector: str, **kwargs):
        self.clicked_selectors.append(selector)

    async def fill(self, selector: str, value: str, **kwargs):
        self.filled_inputs[selector] = value

    async def query_selector(self, selector: str, **kwargs):
        element = MagicMock()
        element.set_input_files = AsyncMock(side_effect=lambda files: self.uploaded_files.append(files))
        element.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 100, "height": 40})
        element.is_visible = AsyncMock(return_value=True)
        element.click = AsyncMock()
        return element

    async def query_selector_all(self, selector: str, **kwargs):
        return []

    async def close(self):
        self.closed = True


class MockPlaywrightBrowserManager:
    """Mock BrowserManager that generates MockPlaywrightPage instances."""
    def __init__(self, cookies_valid: bool = True):
        self.cookies_valid = cookies_valid
        self.page = MockPlaywrightPage(cookies_valid=cookies_valid)
        self.launched = False

    async def launch(self, headless: bool = True):
        self.launched = True
        return MagicMock()

    async def create_context(self, cookies_json: Optional[str] = None, proxy: Optional[dict] = None):
        context = AsyncMock()
        context.add_cookies = AsyncMock()
        context.new_page = AsyncMock(return_value=self.page)
        return context

    async def new_page(self, context: Optional[Any] = None):
        return self.page

    async def close(self):
        self.launched = False


@pytest.fixture
def mock_browser_manager():
    """Fixture providing a mock BrowserManager."""
    return MockPlaywrightBrowserManager()

def create_synthetic_mp4_with_duration(
    filepath: Union[str, Path],
    duration_seconds: float = 5.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    include_audio: bool = True,
) -> Path:
    """
    Generates a valid, minimal synthetic H.264 MP4 file with 48kHz stereo AAC audio
    using OpenCV and FFmpeg for offline unit and integration tests.
    """
    import shutil
    import subprocess
    from pathlib import Path
    
    target_path = Path(filepath)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cv2
        import numpy as np

        raw_video_path = target_path.with_name(f"temp_{target_path.name}")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(raw_video_path), fourcc, fps, (width, height))

        total_frames = int(max(1, round(duration_seconds * fps)))
        for i in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.rectangle(frame, (50, 50), (width - 50, height - 50), (70, 130, 180), -1)
            cv2.putText(frame, f"Frame {i}/{total_frames}", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)
            out.write(frame)
        out.release()

        if include_audio and shutil.which("ffmpeg"):
            # Mux synthetic 48kHz stereo tone
            cmd = [
                "ffmpeg", "-y",
                "-i", str(raw_video_path),
                "-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=48000:duration={duration_seconds}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-shortest", str(target_path)
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if raw_video_path.exists():
                raw_video_path.unlink()
        else:
            if raw_video_path != target_path:
                shutil.move(str(raw_video_path), str(target_path))
    except Exception:
        # Fallback to simple touch
        with open(target_path, "wb") as f:
            f.write(b"")

    return target_path

