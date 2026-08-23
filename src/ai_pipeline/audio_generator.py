"""
src/ai_pipeline/audio_generator.py
Edge-TTS Voiceover Synthesis and Audio Processing Engine for Milestone M2.
"""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Union

import edge_tts
import mutagen
from mutagen.mp3 import MP3

from src.models.pipeline_models import Scene

logger = logging.getLogger(__name__)


class AudioGenerator:
    """
    Synthesizes Vietnamese voiceovers using edge-tts (vi-VN-NamMinhNeural),
    normalizes Vietnamese text, measures dynamic audio durations with mutagen,
    and updates Scene assets in batch.
    """

    DEFAULT_VOICE = "vi-VN-NamMinhNeural"  # Southern Vietnamese Male Voice
    ALT_VOICE = "vi-VN-HoaiMyNeural"       # Northern Vietnamese Female Voice

    # Common Vietnamese abbreviations, chat slang and expansion dictionary
    ABBREVIATION_MAP = {
        r"\b(ko|k|hok|hông)\b": "không",
        r"\b(dc|đc)\b": "được",
        r"\b(vs)\b": "với",
        r"\b(ng|ng`)\b": "người",
        r"\b(mk)\b": "mình",
        r"\b(bt)\b": "biết",
        r"\b(cx)\b": "cũng",
        r"\b(j)\b": "gì",
        r"\b(mn)\b": "mọi người",
        r"\b(ae)\b": "anh em",
        r"\b(tp|tp\.|TP|TP\.)\b": "thành phố",
        r"\b(hn|HN)\b": "Hà Nội",
        r"\b(hcm|HCM|tphcm|TPHCM)\b": "Hồ Chí Minh",
        r"\b(đt|sđt|SĐT|dt)\b": "số điện thoại",
        r"\b(stt|STT)\b": "số thứ tự",
        r"\b(ns)\b": "nói",
        r"\b(r|rùi)\b": "rồi",
    }

    def __init__(
        self,
        output_dir: str = "output/audio",
        default_voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = default_voice
        self.rate = rate
        self.pitch = pitch

    def normalize_vietnamese_text(self, text: str) -> str:
        """
        Cleans markdown, emojis, symbols, normalizes abbreviations, numbers,
        units, and punctuation spacing for smooth, natural Vietnamese TTS pronunciation.
        """
        if not text:
            return ""

        cleaned = text

        # 1. Strip Markdown formatting
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)  # Code blocks
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)      # Inline code
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)  # Bold
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)      # Italic
        cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)      # Underline
        cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)      # Strikethrough
        cleaned = re.sub(r"^#+\s+", "", cleaned, flags=re.MULTILINE)  # Headers
        cleaned = re.sub(r"^>\s+", "", cleaned, flags=re.MULTILINE)   # Blockquotes
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)    # Links
        cleaned = re.sub(r"^[\*\-\+]\s+", "", cleaned, flags=re.MULTILINE)  # Bullet lists

        # 2. Remove emojis and unusual unicode symbols
        cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)
        cleaned = re.sub(r"[\u2600-\u27bf\ud83c-\ud83e]", "", cleaned)
        cleaned = re.sub(r"[@#\^&\|\\_\{\}\[\]<>]", " ", cleaned)

        # 3. Currency, Percentage & Unit Normalizations
        cleaned = re.sub(r"(\d+)\s*(k|K)\b", r"\1 nghìn", cleaned)
        cleaned = re.sub(r"(\d+)\s*(tr|triệu|Tr)\b", r"\1 triệu", cleaned)
        cleaned = re.sub(r"(\d+)\s*(ty|tỷ|Tỷ)\b", r"\1 tỷ", cleaned)
        cleaned = re.sub(r"(\d+)\s*(đ|vnđ|vnd|VND|VNĐ)\b", r"\1 đồng", cleaned)
        cleaned = re.sub(r"(\d+)\s*%", r"\1 phần trăm", cleaned)
        cleaned = re.sub(r"(\d+)\s*(°C|độ C|do C)", r"\1 độ C", cleaned)
        cleaned = re.sub(r"(\d+)\s*km/h", r"\1 ki-lô-mét trên giờ", cleaned)
        cleaned = re.sub(r"(\d+)\s*(km|Km)\b", r"\1 ki-lô-mét", cleaned)
        cleaned = re.sub(r"(\d+)\s*(m2|m²)\b", r"\1 mét vuông", cleaned)
        cleaned = re.sub(r"(\d+)\s*(m3|m³)\b", r"\1 mét khối", cleaned)

        # 4. Expand Abbreviations & Slang
        for pattern, replacement in self.ABBREVIATION_MAP.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # 5. Punctuation and Spacing Fixes
        cleaned = re.sub(r"\.{2,}", ".", cleaned)
        cleaned = re.sub(r"!{2,}", "!", cleaned)
        cleaned = re.sub(r"\?{2,}", "?", cleaned)
        cleaned = re.sub(r"\?!", "?", cleaned)

        # Remove spaces before punctuation
        cleaned = re.sub(r"\s+([,.!?:;])", r"\1", cleaned)
        # Ensure single space after punctuation if followed by text
        cleaned = re.sub(r"([,.!?:;])([^\s0-9,.!?:;])", r"\1 \2", cleaned)

        # 6. Normalize Whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def get_audio_duration(self, audio_path: Union[str, Path]) -> float:
        """
        Extract exact duration of an MP3 audio file in seconds using mutagen.
        """
        path = Path(audio_path)
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError(f"Audio file missing or empty: {audio_path}")

        try:
            audio = MP3(str(path))
            return round(float(audio.info.length), 2)
        except Exception as e:
            logger.warning(f"Direct MP3 inspection failed: {e}. Trying mutagen.File...")
            try:
                audio = mutagen.File(str(path))
                if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length"):
                    return round(float(audio.info.length), 2)
            except Exception as inner_e:
                logger.error(f"Fallback mutagen extraction failed: {inner_e}")

        # Fallback: estimate from MPEG frames if synthetic / simple MP3
        try:
            data = path.read_bytes()
            # Check frame sync 0xFF, 0xFB (MPEG-1 Layer 3, 128kbps, 44.1kHz -> 417 bytes/frame, ~0.02612s/frame)
            if len(data) >= 417 and data[0] == 0xFF and (data[1] & 0xFE) == 0xFA:
                frame_count = len(data) // 417
                duration = frame_count * (1152 / 44100)
                return round(float(duration), 2)
        except Exception:
            pass

        raise RuntimeError(f"Failed to determine audio duration for: {audio_path}")

    async def generate_single_audio(
        self,
        text: str,
        output_path: Union[str, Path],
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        max_retries: int = 3,
    ) -> float:
        """
        Synthesize audio for a single text string using edge-tts.
        Returns duration in seconds.
        """
        normalized_text = self.normalize_vietnamese_text(text)
        if not normalized_text:
            raise ValueError("Narration text is empty after normalization.")

        target_voice = voice or self.default_voice
        target_rate = rate or self.rate
        target_pitch = pitch or self.pitch

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Generating audio [attempt {attempt}/{max_retries}] with voice '{target_voice}'...")
                communicate = edge_tts.Communicate(
                    text=normalized_text,
                    voice=target_voice,
                    rate=target_rate,
                    pitch=target_pitch,
                )
                await communicate.save(str(out_path))

                if not out_path.exists() or out_path.stat().st_size == 0:
                    raise IOError(f"Generated audio file is missing or 0 bytes: {out_path}")

                duration = self.get_audio_duration(out_path)
                logger.info(f"Audio generated successfully: {out_path} ({duration:.2f}s)")
                return duration

            except Exception as e:
                logger.error(f"Error generating audio (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * attempt)
                else:
                    raise RuntimeError(f"Failed to generate audio after {max_retries} attempts: {e}")

        raise RuntimeError("Unreachable audio generation state.")

    async def generate_audio(
        self,
        text: str,
        output_path: Union[str, Path],
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> float:
        """Compatibility method for generate_audio."""
        return await self.generate_single_audio(
            text=text,
            output_path=output_path,
            voice=voice,
            rate=rate,
            pitch=pitch,
        )

    async def generate_scene_audios(
        self,
        scenes: List[Scene],
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> List[Scene]:
        """
        Batch generate audio files for all scenes, measure exact durations,
        and update Scene instances with audio_path, duration, and status.
        """
        target_dir = Path(output_dir) if output_dir else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        for scene in scenes:
            scene_file = target_dir / f"scene_{scene.scene_id}.mp3"
            try:
                duration = await self.generate_single_audio(
                    text=scene.narration_text_vi,
                    output_path=scene_file,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                )
                scene.audio_path = str(scene_file)
                scene.duration = duration
                scene.status = "completed" if scene.image_path else "audio_ready"
            except Exception as e:
                logger.error(f"Failed generating audio for scene {scene.scene_id}: {e}")
                scene.status = "failed"
                raise

        return scenes
