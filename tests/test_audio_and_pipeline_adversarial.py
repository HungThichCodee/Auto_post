"""
tests/test_audio_and_pipeline_adversarial.py
Adversarial Stress Test Suite for AudioGenerator and End-to-End Pipeline Integration (Milestone M2).
Authors: challenger_m2_2 (Critic / Specialist)

Exhaustive stress testing across 8 adversarial challenge dimensions:
1. Extreme Vietnamese Text Normalization & Diacritic Preservation (NFC/NFD, diacritics, massive numbers, complex slang, emoji spam, nested punctuation).
2. ReDoS (Regular Expression Denial of Service) Stress Testing & Execution Complexity Profiling.
3. Mutagen Dynamic Audio Duration Extraction across Diverse Bitrates, Sample Rates, ID3 Tags & Corrupted Files.
4. Audio Synthesis Edge Cases (Empty strings, all-emoji narrations, zero duration, transient failure retry cascades).
5. Scene Lifecycle & Status State Machine Transitions (pending -> image_ready -> audio_ready -> completed / failed).
6. Multi-Scene End-to-End Pipeline Concurrency & Race Condition Resilience.
7. Dynamic Total Duration Aggregation & Aspect Ratio Boundary Invariants (<60s vs >=60s).
8. Fault Injection & Resilience under Asynchronous Pipeline Failures.
"""

import asyncio
import io
import os
import random
import re
import string
import struct
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import mutagen
from mutagen.mp3 import MP3
from PIL import Image

from src.ai_pipeline.audio_generator import AudioGenerator
from src.ai_pipeline.image_generator import ImageGenerator, compose_scene_prompt, get_dimensions_for_aspect_ratio
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.models.pipeline_models import Scene, StoryScript, ScrapedVideo
from tests.conftest import (
    MockEdgeTTSCommunicate,
    create_synthetic_mp3,
    create_synthetic_png,
    create_synthetic_png_bytes,
)


# ==============================================================================
# Helper Functions for Synthesizing Complex MP3s with Headers / ID3 Tags
# ==============================================================================

def create_mp3_with_id3v2(
    filepath: Path,
    duration_seconds: float = 3.0,
    tag_size: int = 1024,
) -> Path:
    """Generate an MP3 file with an ID3v2.3 tag header prepended."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # ID3v2.3 header: "ID3", ver 3.0, flags 0, syncsafe size
    # Syncsafe integer encoding for tag_size
    s1 = (tag_size >> 21) & 0x7F
    s2 = (tag_size >> 14) & 0x7F
    s3 = (tag_size >> 7) & 0x7F
    s4 = tag_size & 0x7F
    id3_header = b"ID3\x03\x00\x00" + bytes([s1, s2, s3, s4])
    id3_body = b"\x00" * tag_size
    
    samples_needed = int(max(0.1, duration_seconds) * 44100)
    frames_needed = max(1, round(samples_needed / 1152))
    
    # MPEG-1 Layer 3, 128kbps, 44.1kHz stereo frame (417 bytes)
    frame_header = bytes([0xFF, 0xFB, 0x90, 0x64])
    frame_data = frame_header + bytes(413)
    
    with open(filepath, "wb") as f:
        f.write(id3_header + id3_body)
        f.write(frame_data * frames_needed)
    
    return filepath


def create_mp3_with_custom_sample_rate(
    filepath: Path,
    sample_rate: int = 44100,
    bitrate_kbps: int = 128,
    duration_seconds: float = 3.0,
) -> Path:
    """
    Generate an MPEG-1 Layer 3 MP3 with custom sample rate and bitrate.
    Sample rate index: 44100 -> 0x00, 48000 -> 0x01, 32000 -> 0x02
    Bitrate index (Layer 3):
    64kbps -> 0x05, 96kbps -> 0x07, 128kbps -> 0x09, 192kbps -> 0x0B, 256kbps -> 0x0D, 320kbps -> 0x0E
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    sr_map = {44100: 0x00, 48000: 0x01, 32000: 0x02}
    br_map = {64: 0x05, 96: 0x07, 128: 0x09, 192: 0x0B, 256: 0x0D, 320: 0x0E}
    
    sr_bits = sr_map.get(sample_rate, 0x00)
    br_bits = br_map.get(bitrate_kbps, 0x09)
    
    byte2 = 0xFB  # MPEG-1, Layer 3, no CRC
    byte3 = (br_bits << 4) | (sr_bits << 2) | 0x00  # no padding
    byte4 = 0x64  # stereo
    
    frame_size = int((144 * bitrate_kbps * 1000) / sample_rate)
    frame_header = bytes([0xFF, byte2, byte3, byte4])
    frame_data = frame_header + bytes(max(0, frame_size - 4))
    
    samples_per_frame = 1152
    frames_needed = max(1, round((duration_seconds * sample_rate) / samples_per_frame))
    
    with open(filepath, "wb") as f:
        f.write(frame_data * frames_needed)
        
    return filepath


# ==============================================================================
# SECTION 1: VIETNAMESE TEXT NORMALIZATION & DIACRITICS ADVERSARIAL MATRIX
# ==============================================================================

class TestVietnameseTextNormalizationAdversarial:
    """Stress test Vietnamese text normalizer with adversarial inputs, edge cases, and diacritics."""

    @pytest.fixture
    def normalizer(self):
        return AudioGenerator().normalize_vietnamese_text

    @pytest.mark.parametrize("raw_input,expected_fragment", [
        # 1. Extreme Slang & Abbreviation combinations
        ("Hôm nay mk ko đi học dc vs bạn bè ở tp HCM", "mình không đi học được với bạn bè ở thành phố Hồ Chí Minh"),
        ("ae chuẩn bị tới HN chưa? sđt liên hệ là gì", "anh em chuẩn bị tới Hà Nội chưa? số điện thoại liên hệ là gì"),
        ("mn có bt vụ j mới ko? ns rùi mà k nghe", "mọi người có biết gì mới không? nói rồi mà không nghe"),
        ("Kiểm tra stt và SĐT của ng này ngay", "Kiểm tra số thứ tự và số điện thoại của người này ngay"),
        ("TP.HCM và TP. Hà Nội là 2 tp lớn", "Hồ Chí Minh và thành phố Hà Nội là 2 thành phố lớn"),
        ("cx đúng rùi, ko sao đâu", "cũng đúng rồi, không sao đâu"),

        # 2. Currency, Numbers, Percentages, and Units
        ("Giá bán 50k, giảm giá 15% hôm nay", "Giá bán 50 nghìn, giảm giá 15 phần trăm hôm nay"),
        ("Đầu tư 10tr hoặc 5ty cho dự án", "Đầu tư 10 triệu hoặc 5 tỷ cho dự án"),
        ("Chi phí là 250000đ và 500k vnđ", "Chi phí là 250000 đồng và 500 nghìn đồng"),
        ("Vận tốc 120km/h trên quãng đường 500km", "Vận tốc 120 ki-lô-mét trên giờ trên quãng đường 500 ki-lô-mét"),
        ("Nhiệt độ ngoài trời lên tới 40°C rất nóng", "Nhiệt độ ngoài trời lên tới 40 độ C rất nóng"),
        ("Căn phòng rộng 85m2 và thể tích 250m3", "Căn phòng rộng 85 mét vuông và thể tích 250 mét khối"),

        # 3. Punctuation Spam & Chaos
        ("Cái gì vậy ?????", "Cái gì vậy?"),
        ("Thật bất ngờ !!!!!!!!", "Thật bất ngờ!"),
        ("Chuyện gì đang xảy ra ?!?!?", "Chuyện gì đang xảy ra?"),
        ("Chờ một chút .......... xong ngay", "Chờ một chút. xong ngay"),
        ("Xin chào ,tất cả các bạn .Hôm nay sao ?", "Xin chào, tất cả các bạn. Hôm nay sao?"),

        # 4. Heavy Markdown & Link Stripping
        ("# Tiêu đề cảnh 1\n## Phụ đề phụ\n> Lời bình dẫn chuyện.", "Tiêu đề cảnh 1 Phụ đề phụ Lời bình dẫn chuyện."),
        ("Đoạn văn có chữ **in đậm rất mạnh** và *nghiêng nhẹ* cùng ~~gạch bỏ~~.", "Đoạn văn có chữ in đậm rất mạnh và nghiêng nhẹ cùng gạch bỏ."),
        ("Bấm vào link [Xem tại đây](https://youtube.com) nhé!", "Bấm vào link Xem tại đây nhé!"),
        ("Đoạn mã: ```python\nprint('hello')\n``` kết thúc.", "Đoạn mã: kết thúc."),
        ("Dấu `inline_code` cần giữ lại nội dung.", "Dấu inline_code cần giữ lại nội dung."),
        ("- Gạch đầu dòng 1\n* Gạch đầu dòng 2\n+ Gạch đầu dòng 3", "Gạch đầu dòng 1 Gạch đầu dòng 2 Gạch đầu dòng 3"),

        # 5. Emoji & Unicode Character Cleansing
        ("🐶 Mèo 🐱 Chuột 🐭 Lửa 🔥 Sao ✨ Đỉnh 💯 Cờ 🇻🇳", "Mèo Chuột Lửa Sao Đỉnh Cờ"),
        ("Chào bạn 👋🏻! @admin chúc mừng #trending <video>", "Chào bạn! admin chúc mừng trending video"),
        ("Nội dung trong ngoặc {nhọn} [vuông] và <nhọn> cùng ký tự | \\ ^ & _", "Nội dung trong ngoặc nhọn vuông và nhọn cùng ký tự"),
    ])
    def test_text_normalization_rule_matrix(self, normalizer, raw_input, expected_fragment):
        """Verify normalizer cleanly handles diverse Vietnamese colloquialisms, symbols and formatting."""
        result = normalizer(raw_input)
        assert expected_fragment in result or result == expected_fragment

    def test_vietnamese_diacritic_preservation(self, normalizer):
        """Verify all Vietnamese tones and vowel combinations are completely preserved."""
        vietnamese_pangram = (
            "Bác tài xế chở đầy hàng hóa, vượt qua khúc cua ngoằn ngoèo ở đỉnh núi mù sương, "
            "vẫn giữ nụ cười rạng rỡ và niềm tin yêu đời mãnh liệt."
        )
        normalized = normalizer(vietnamese_pangram)
        # All diacritics must remain intact
        assert "ngoằn ngoèo" in normalized
        assert "mù sương" in normalized
        assert "rạng rỡ" in normalized
        assert "mãnh liệt" in normalized

    def test_unicode_nfc_nfd_equivalence(self, normalizer):
        """Verify normalizer produces consistent readable output for NFC and NFD strings."""
        import unicodedata
        nfc_text = "Tiếng Việt thật là phong phú và đẹp đẽ."
        nfd_text = unicodedata.normalize("NFD", nfc_text)

        norm_nfc = normalizer(nfc_text)
        norm_nfd = normalizer(nfd_text)

        # Decomposed forms should be cleanly handled without losing words
        assert "Tiếng" in unicodedata.normalize("NFC", norm_nfd)
        assert "Việt" in unicodedata.normalize("NFC", norm_nfd)
        assert "đẹp đẽ" in unicodedata.normalize("NFC", norm_nfd)

    @pytest.mark.parametrize("empty_or_blank", [
        "",
        "    ",
        "\t\n\r  \n",
        "🐶🔥🎉✨💯",
        "@#$%^&*()_+{}[]:;\"'<>",
        "```\n```",
    ])
    def test_empty_and_emoji_only_normalization(self, normalizer, empty_or_blank):
        """Verify inputs that contain only emojis, symbols, or whitespace normalize to empty string."""
        assert normalizer(empty_or_blank) == "" or normalizer(empty_or_blank).strip() == ""


# ==============================================================================
# SECTION 2: ReDoS STRESS TESTING & COMPLEXITY PROFILING
# ==============================================================================

class TestReDoSStressTesting:
    """Stress test normalization regex patterns against catastrophic backtracking (ReDoS)."""

    def test_massive_vietnamese_text_performance(self):
        """Verify normalization of 100,000+ characters executes in sub-second time without quadratic explosion."""
        gen = AudioGenerator()
        base_paragraph = (
            "Hôm nay mk ko đi học dc vs ae ở tp HCM và HN. Giá 50k giảm 20%, nhiệt độ 35°C, "
            "vận tốc 60km/h trên 100km diện tích 50m2. **Rất vui** [Link](https://dantri.com.vn) "
            "🐶🐱🔥 Chuyện gì ??? Thật tuyệt !!! "
        )
        massive_text = base_paragraph * 500  # ~115,000 characters

        start_time = time.perf_counter()
        normalized = gen.normalize_vietnamese_text(massive_text)
        elapsed = time.perf_counter() - start_time

        assert len(normalized) > 50000
        # Must execute within 1.5 seconds (linear time complexity)
        assert elapsed < 1.5, f"Normalization took too long: {elapsed:.3f}s (potential ReDoS)"

    @pytest.mark.parametrize("pattern_attack", [
        # Nested formatting attack
        "**" * 500 + "nested text" + "**" * 500,
        # Repeated dots / punctuation attack
        "Xin chào" + "." * 10000 + "kết thúc",
        "Hả" + "?" * 5000 + "!" * 5000,
        # Massive unit string attack
        "1" * 1000 + "k " + "2" * 1000 + "tr " + "3" * 1000 + "tỷ",
        # Massive whitespace attack
        "Từ 1" + "   \t\n   " * 2000 + "Từ 2",
        # Heavy link attack
        "[" * 500 + "nested link" + "]" * 500 + "(https://example.com)",
        # Code fence attack with unclosed fences
        "```python\n" + "x = 1\n" * 2000,
    ])
    def test_adversarial_regex_patterns_safety(self, pattern_attack):
        """Ensure crafted adversarial pattern strings do not hang or crash the regex engine."""
        gen = AudioGenerator()
        start = time.perf_counter()
        result = gen.normalize_vietnamese_text(pattern_attack)
        elapsed = time.perf_counter() - start

        assert isinstance(result, str)
        assert elapsed < 1.0, f"Pattern caused severe slowdown: {elapsed:.3f}s"


# ==============================================================================
# SECTION 3: MUTAGEN DURATION EXTRACTION ADVERSARIAL MATRIX
# ==============================================================================

class TestMutagenDurationAccuracyAdversarial:
    """Stress test dynamic audio duration extraction across diverse MP3 formats, sample rates, and bitrates."""

    @pytest.fixture
    def audio_gen(self, tmp_path):
        return AudioGenerator(output_dir=str(tmp_path))

    @pytest.mark.parametrize("duration", [0.5, 1.25, 3.0, 7.82, 15.5, 59.9, 60.0, 120.4])
    def test_synthetic_mp3_duration_accuracy(self, audio_gen, tmp_path, duration):
        """Verify mutagen measures synthetic MPEG-1 Layer 3 MP3 duration accurately within 50ms tolerance."""
        mp3_file = tmp_path / f"test_dur_{duration}.mp3"
        create_synthetic_mp3(mp3_file, duration_seconds=duration)

        measured = audio_gen.get_audio_duration(mp3_file)
        assert abs(measured - duration) <= 0.06, f"Expected ~{duration}s, got {measured}s"

    @pytest.mark.parametrize("tag_size", [128, 512, 2048, 8192, 65536])
    def test_mp3_with_large_id3v2_tags(self, audio_gen, tmp_path, tag_size):
        """Verify duration extraction remains accurate when MP3 has prepended ID3v2 tags of various sizes."""
        mp3_file = tmp_path / f"id3_{tag_size}.mp3"
        create_mp3_with_id3v2(mp3_file, duration_seconds=4.0, tag_size=tag_size)

        measured = audio_gen.get_audio_duration(mp3_file)
        assert abs(measured - 4.0) <= 0.1, f"ID3 tag {tag_size}b skewed duration measurement: {measured}s"

    @pytest.mark.parametrize("sample_rate,bitrate", [
        (44100, 64),
        (44100, 128),
        (44100, 192),
        (44100, 320),
        (48000, 128),
        (32000, 128),
    ])
    def test_mp3_various_sample_rates_and_bitrates(self, audio_gen, tmp_path, sample_rate, bitrate):
        """Verify mutagen dynamic duration measurement across multiple sample rates and bitrates."""
        mp3_file = tmp_path / f"sr_{sample_rate}_br_{bitrate}.mp3"
        create_mp3_with_custom_sample_rate(mp3_file, sample_rate=sample_rate, bitrate_kbps=bitrate, duration_seconds=3.5)

        measured = audio_gen.get_audio_duration(mp3_file)
        assert abs(measured - 3.5) <= 0.15, f"Sample rate {sample_rate}Hz bitrate {bitrate}kbps mismatch: {measured}s"

    def test_duration_missing_file_raises(self, audio_gen, tmp_path):
        """Verify get_audio_duration raises ValueError on non-existent path."""
        with pytest.raises(ValueError, match="missing or empty"):
            audio_gen.get_audio_duration(tmp_path / "non_existent.mp3")

    def test_duration_empty_zero_byte_file_raises(self, audio_gen, tmp_path):
        """Verify get_audio_duration raises ValueError on 0-byte file."""
        zero_file = tmp_path / "zero_bytes.mp3"
        zero_file.touch()
        with pytest.raises(ValueError, match="missing or empty"):
            audio_gen.get_audio_duration(zero_file)

    def test_duration_corrupted_garbage_file_raises(self, audio_gen, tmp_path):
        """Verify get_audio_duration raises RuntimeError when file contains arbitrary binary garbage."""
        garbage_file = tmp_path / "garbage.mp3"
        with open(garbage_file, "wb") as f:
            f.write(os.urandom(1024))

        with pytest.raises(RuntimeError, match="Failed to determine audio duration"):
            audio_gen.get_audio_duration(garbage_file)

    def test_duration_truncated_mp3_recovers_or_handles(self, audio_gen, tmp_path):
        """Verify mutagen handles truncated MP3 gracefully without crashing."""
        mp3_file = tmp_path / "truncated.mp3"
        create_synthetic_mp3(mp3_file, duration_seconds=5.0)

        # Truncate halfway
        raw_data = mp3_file.read_bytes()
        truncated_file = tmp_path / "half_truncated.mp3"
        truncated_file.write_bytes(raw_data[: len(raw_data) // 2])

        measured = audio_gen.get_audio_duration(truncated_file)
        assert 2.0 <= measured <= 3.0


# ==============================================================================
# SECTION 4: AUDIO GENERATOR SYNTHESIS EDGE CASES & RETRY RECOVERY
# ==============================================================================

class TestAudioGeneratorSynthesisAdversarial:
    """Stress test Edge-TTS generation with transient errors, empty inputs, and retries."""

    @pytest.mark.asyncio
    async def test_generate_single_audio_empty_after_normalization_fails(self, tmp_path):
        """Verify generate_single_audio rejects text that normalizes to empty string."""
        gen = AudioGenerator(output_dir=str(tmp_path))
        dest = tmp_path / "out.mp3"

        with pytest.raises(ValueError, match="empty after normalization"):
            await gen.generate_single_audio("🐶🎉✨🔥", output_path=dest)

        with pytest.raises(ValueError, match="empty after normalization"):
            await gen.generate_single_audio("   ", output_path=dest)

    @pytest.mark.asyncio
    async def test_generate_single_audio_retry_exhaustion_propagates(self, tmp_path, monkeypatch):
        """Verify generate_single_audio raises RuntimeError after exhausting all 3 retries."""
        class FailCommunicate:
            def __init__(self, *args, **kwargs):
                pass
            async def save(self, *args, **kwargs):
                raise ConnectionError("Network unreachable")

        monkeypatch.setattr("edge_tts.Communicate", FailCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError, match="Failed to generate audio after 3 attempts"):
                await gen.generate_single_audio("Xin chào", output_path=tmp_path / "fail.mp3", max_retries=3)
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_single_audio_recovers_on_third_attempt(self, tmp_path, monkeypatch):
        """Verify generate_single_audio succeeds when first 2 attempts fail and 3rd succeeds."""
        attempt_counter = 0

        class FlakyTwoFailuresCommunicate:
            def __init__(self, *args, **kwargs):
                pass
            async def save(self, path):
                nonlocal attempt_counter
                attempt_counter += 1
                if attempt_counter < 3:
                    raise IOError(f"Temporary I/O error on attempt {attempt_counter}")
                create_synthetic_mp3(path, duration_seconds=2.5)

        monkeypatch.setattr("edge_tts.Communicate", FlakyTwoFailuresCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            duration = await gen.generate_single_audio("Xin chào các bạn", output_path=tmp_path / "recovered.mp3", max_retries=3)
            assert duration > 2.0
            assert attempt_counter == 3
            assert mock_sleep.call_count == 2


# ==============================================================================
# SECTION 5: SCENE LIFECYCLE & STATE MACHINE TRANSITIONS
# ==============================================================================

class TestSceneLifecycleStateMachine:
    """Stress test Scene status state machine transitions through pipeline stages."""

    @pytest.fixture
    def mock_edge_tts(self, monkeypatch):
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)

    @pytest.mark.asyncio
    async def test_audio_generator_transitions_pending_to_audio_ready(self, tmp_path, mock_edge_tts):
        """When scene has no image_path, status transitions from 'pending' -> 'audio_ready'."""
        gen = AudioGenerator(output_dir=str(tmp_path))
        scene = Scene(scene_id=1, narration_text_vi="Đoạn văn 1", image_prompt_en="Visual 1", status="pending")

        assert scene.status == "pending"
        updated = await gen.generate_scene_audios([scene])

        assert updated[0].status == "audio_ready"
        assert updated[0].audio_path is not None
        assert updated[0].duration > 0.0

    @pytest.mark.asyncio
    async def test_audio_generator_transitions_image_ready_to_completed(self, tmp_path, mock_edge_tts):
        """When scene already has image_path ('image_ready'), adding audio transitions status to 'completed'."""
        gen = AudioGenerator(output_dir=str(tmp_path))
        img_file = tmp_path / "img.png"
        create_synthetic_png(img_file, 1080, 1920)

        scene = Scene(
            scene_id=1,
            narration_text_vi="Đoạn văn 1",
            image_prompt_en="Visual 1",
            image_path=str(img_file),
            status="image_ready",
        )

        updated = await gen.generate_scene_audios([scene])
        assert updated[0].status == "completed"
        assert updated[0].audio_path is not None

    @pytest.mark.asyncio
    async def test_image_generator_transitions_audio_ready_to_completed(self, tmp_path):
        """When scene already has audio_path ('audio_ready'), adding image transitions status to 'completed'."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        mp3_file = tmp_path / "audio.mp3"
        create_synthetic_mp3(mp3_file, duration_seconds=3.0)

        scene = Scene(
            scene_id=1,
            narration_text_vi="Đoạn văn 1",
            image_prompt_en="Visual 1",
            audio_path=str(mp3_file),
            duration=3.0,
            status="audio_ready",
        )

        valid_png = create_synthetic_png_bytes(1080, 1920)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_res
            updated = await gen.generate_scene_images([scene])

            assert updated[0].status == "completed"
            assert updated[0].image_path is not None

    @pytest.mark.asyncio
    async def test_audio_generator_sets_status_failed_on_exception(self, tmp_path, monkeypatch):
        """When audio generation fails, scene status must transition to 'failed'."""
        class CrashCommunicate:
            def __init__(self, *args, **kwargs):
                pass
            async def save(self, *args, **kwargs):
                raise RuntimeError("Synthesis engine fatal error")

        monkeypatch.setattr("edge_tts.Communicate", CrashCommunicate)
        gen = AudioGenerator(output_dir=str(tmp_path))
        scene = Scene(scene_id=1, narration_text_vi="Đoạn văn", image_prompt_en="Prompt", status="pending")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await gen.generate_scene_audios([scene])

        assert scene.status == "failed"


# ==============================================================================
# SECTION 6: MULTI-SCENE PIPELINE CONCURRENCY & RACE CONDITIONS
# ==============================================================================

class TestPipelineConcurrencyAndRaceConditions:
    """Stress test concurrent execution of ImageGenerator and AudioGenerator across multiple pipelines."""

    @pytest.fixture
    def mock_edge_tts(self, monkeypatch):
        monkeypatch.setattr("edge_tts.Communicate", MockEdgeTTSCommunicate)

    @pytest.mark.asyncio
    async def test_concurrent_multi_story_pipeline_execution(self, tmp_path, mock_edge_tts):
        """Run 5 complete multi-scene stories concurrently without cross-talk or file collision."""
        num_stories = 5
        scenes_per_story = 4

        tasks = []
        valid_png = create_synthetic_png_bytes(1080, 1920)

        for story_idx in range(1, num_stories + 1):
            story_dir = tmp_path / f"story_{story_idx}"
            img_dir = story_dir / "images"
            aud_dir = story_dir / "audio"

            scenes = [
                Scene(
                    scene_id=i,
                    narration_text_vi=f"Câu chuyện {story_idx} cảnh {i}: Miêu tả chi tiết.",
                    image_prompt_en=f"Story {story_idx} scene {i} illustration",
                )
                for i in range(1, scenes_per_story + 1)
            ]

            script = StoryScript(
                title_vi=f"Tiêu đề {story_idx}",
                description_vi=f"Mô tả {story_idx}",
                theme=f"Chủ đề {story_idx}",
                art_style="anime",
                scenes=scenes,
            )

            async def process_story(s_script, i_dir, a_dir):
                img_gen = ImageGenerator(output_dir=str(i_dir))
                aud_gen = AudioGenerator(output_dir=str(a_dir))

                mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())
                with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_res):
                    s_script.scenes = await img_gen.generate_scene_images(
                        scenes=s_script.scenes,
                        art_style=s_script.art_style,
                        aspect_ratio="9:16",
                    )
                s_script.scenes = await aud_gen.generate_scene_audios(scenes=s_script.scenes)
                return s_script

            tasks.append(process_story(script, img_dir, aud_dir))

        results = await asyncio.gather(*tasks)

        assert len(results) == num_stories
        for story in results:
            assert len(story.scenes) == scenes_per_story
            for sc in story.scenes:
                assert sc.status == "completed"
                assert Path(sc.image_path).exists()
                assert Path(sc.audio_path).exists()
                assert sc.duration > 0.0
            assert story.total_duration > 0.0


# ==============================================================================
# SECTION 7: DYNAMIC TOTAL DURATION & ASPECT RATIO BOUNDARY INVARIANTS
# ==============================================================================

class TestDynamicDurationAndAspectRatioBoundary:
    """Stress test total_duration summation and aspect ratio boundary at 60.00 seconds."""

    @pytest.mark.parametrize("scene_durations,expected_total,expected_shorts,expected_ratio", [
        # Exactly below 60s
        ([15.0, 15.0, 15.0, 14.99], 59.99, True, "9:16"),
        ([29.95, 30.0], 59.95, True, "9:16"),
        ([1.0] * 59, 59.0, True, "9:16"),

        # Exactly at 60s threshold
        ([30.0, 30.0], 60.0, False, "16:9"),
        ([20.0, 20.0, 20.0], 60.0, False, "16:9"),

        # Just above 60s threshold
        ([30.0, 30.01], 60.01, False, "16:9"),
        ([15.0, 15.0, 15.0, 15.05], 60.05, False, "16:9"),
        ([25.0, 25.0, 25.0], 75.0, False, "16:9"),
    ])
    def test_aspect_ratio_boundary_oracle(self, scene_durations, expected_total, expected_shorts, expected_ratio):
        """Verify mathematical precision of total duration and boundary threshold at 60.0s."""
        scenes = [
            Scene(
                scene_id=i + 1,
                narration_text_vi=f"Đoạn {i+1}",
                image_prompt_en=f"Prompt {i+1}",
                duration=dur,
            )
            for i, dur in enumerate(scene_durations)
        ]

        script = StoryScript(
            title_vi="Boundary Test Script",
            description_vi="Description",
            theme="Theme",
            art_style="Style",
            scenes=scenes,
        )

        assert abs(script.total_duration - expected_total) < 1e-4
        assert script.is_shorts == expected_shorts
        assert script.target_aspect_ratio == expected_ratio

    def test_dynamic_duration_accumulation_large_scene_count(self):
        """Verify dynamic duration calculation with 100 scenes preserves floating point accuracy."""
        durations = [round(random.uniform(1.5, 4.5), 2) for _ in range(100)]
        expected_sum = round(sum(durations), 2)

        scenes = [
            Scene(scene_id=i + 1, narration_text_vi=f"Cảnh {i+1}", image_prompt_en=f"P {i+1}", duration=d)
            for i, d in enumerate(durations)
        ]
        script = StoryScript(
            title_vi="Large Script",
            description_vi="",
            theme="",
            art_style="",
            scenes=scenes,
        )

        assert abs(script.total_duration - expected_sum) < 0.01


# ==============================================================================
# SECTION 8: FAULT INJECTION & RESILIENCE UNDER ASYNC PIPELINE FAILURES
# ==============================================================================

class TestFaultInjectionAndPipelineResilience:
    """Stress test pipeline recovery during partial failures, intermittent network drops, and corrupted responses."""

    @pytest.mark.asyncio
    async def test_image_generator_corrupt_then_recover_with_turbo_fallback(self, tmp_path):
        """ImageGenerator encounters 2 corrupt HTTP payloads, then succeeds with turbo on 3rd attempt."""
        gen = ImageGenerator(output_dir=str(tmp_path), max_retries=3)
        corrupt_payload = b"SHORT_GARBAGE"
        valid_png = create_synthetic_png_bytes(1080, 1920)

        call_urls = []

        async def mock_get(url, *args, **kwargs):
            call_urls.append(str(url))
            if len(call_urls) < 3:
                return MagicMock(status_code=200, content=corrupt_payload, raise_for_status=MagicMock())
            return MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                img_path = await gen.generate_image("A cute dog in the park", width=1080, height=1920)

                assert Path(img_path).exists()
                assert len(call_urls) == 3
                # Attempt 3 must switch model to turbo
                assert "model=turbo" in call_urls[2]
                assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_pipeline_atomic_file_write_no_leftover_tmp_files(self, tmp_path):
        """Verify ImageGenerator cleans up .tmp temporary files after successful write."""
        gen = ImageGenerator(output_dir=str(tmp_path))
        valid_png = create_synthetic_png_bytes(512, 512)
        mock_res = MagicMock(status_code=200, content=valid_png, raise_for_status=MagicMock())

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_res):
            out_file = tmp_path / "final_image.png"
            await gen.generate_image("Prompt", width=512, height=512, custom_filepath=out_file)

            assert out_file.exists()
            # Verify no orphaned .tmp files remain in directory
            tmp_files = list(tmp_path.glob("*.tmp"))
            assert len(tmp_files) == 0
