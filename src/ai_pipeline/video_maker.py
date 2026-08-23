"""
src/ai_pipeline/video_maker.py
Video assembly engine: combines scene images + audio + subtitles into final MP4.
"""

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import List, Optional, Tuple

from src.models.pipeline_models import Scene, StoryScript, VideoOutput

logger = logging.getLogger(__name__)


class VideoMaker:
    """Assembles scene images and audio into a complete video with Ken Burns effect and subtitles."""

    SHORTS_RES = (1080, 1920)  # 9:16
    REGULAR_RES = (1920, 1080)  # 16:9

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def create_video(
        self,
        story: StoryScript,
        output_path: str = "output/final_video.mp4",
    ) -> VideoOutput:
        """Create a complete video from a StoryScript with images and audio."""
        # Import moviepy here to avoid import errors at module level
        try:
            from moviepy.editor import (
                ImageClip,
                AudioFileClip,
                CompositeVideoClip,
                concatenate_videoclips,
                TextClip,
                ColorClip,
            )
        except ImportError as e:
            raise RuntimeError(f"moviepy is required: {e}. Install with: pip install moviepy")

        # Validate scenes have assets
        valid_scenes = [
            s for s in story.scenes
            if s.image_path and os.path.exists(s.image_path)
            and s.audio_path and os.path.exists(s.audio_path)
        ]

        if not valid_scenes:
            raise ValueError("No valid scenes with both image_path and audio_path found.")

        logger.info(f"Creating video from {len(valid_scenes)} scenes...")

        # Determine format
        is_shorts = story.is_shorts
        target_res = self.SHORTS_RES if is_shorts else self.REGULAR_RES
        aspect = "9:16" if is_shorts else "16:9"
        logger.info(f"Video format: {'Shorts (9:16)' if is_shorts else 'Regular (16:9)'} at {target_res}")

        # Build scene clips
        scene_clips = []
        for scene in valid_scenes:
            try:
                clip = self._create_scene_clip(
                    scene, target_res, ImageClip, AudioFileClip,
                    CompositeVideoClip, TextClip, ColorClip
                )
                scene_clips.append(clip)
                logger.info(f"Scene {scene.scene_id} clip created ({scene.duration:.1f}s)")
            except Exception as e:
                logger.error(f"Failed to create clip for scene {scene.scene_id}: {e}")
                continue

        if not scene_clips:
            raise ValueError("No scene clips could be created.")

        # Concatenate all clips
        logger.info("Concatenating scene clips...")
        final = concatenate_videoclips(scene_clips, method="compose")

        # Write output
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Rendering video to {out_path}...")
        # Run in thread to not block async loop
        await asyncio.to_thread(
            final.write_videofile,
            str(out_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=2,
            logger=None,  # Suppress moviepy's verbose output
        )

        # Cleanup clips
        for clip in scene_clips:
            try:
                clip.close()
            except Exception:
                pass
        final.close()

        # Get file size
        file_size = out_path.stat().st_size if out_path.exists() else 0
        total_duration = sum(s.duration for s in valid_scenes)

        logger.info(f"Video created: {out_path} ({total_duration:.1f}s, {file_size / 1024 / 1024:.1f}MB)")

        return VideoOutput(
            video_path=str(out_path),
            duration=total_duration,
            aspect_ratio=aspect,
            resolution=target_res,
            fps=24,
            file_size_bytes=file_size,
            scene_count=len(valid_scenes),
            has_subtitles=True,
        )

    def _create_scene_clip(
        self, scene: Scene, target_res: Tuple[int, int],
        ImageClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip
    ):
        """Create a single scene clip with image, audio, Ken Burns effect, and subtitles."""
        # Load audio to get duration
        audio = AudioFileClip(scene.audio_path)
        duration = audio.duration

        # Load and resize image
        img_clip = ImageClip(scene.image_path).set_duration(duration)

        # Apply Ken Burns effect
        img_clip = self._apply_ken_burns(img_clip, target_res, duration)

        # Set audio
        img_clip = img_clip.set_audio(audio)

        # Add subtitles
        subtitle_text = scene.subtitle_text or scene.narration_text_vi
        try:
            final_clip = self._add_subtitles(
                img_clip, subtitle_text, target_res, duration,
                CompositeVideoClip, TextClip, ColorClip
            )
        except Exception as e:
            logger.warning(f"Subtitle rendering failed (ImageMagick may be missing): {e}. Skipping subtitles.")
            final_clip = img_clip

        return final_clip

    def _apply_ken_burns(self, clip, target_res: Tuple[int, int], duration: float):
        """Apply Ken Burns (slow zoom/pan) effect on an image clip."""
        w, h = target_res

        # Scale image larger than target to allow zoom/pan
        scale_factor = 1.2

        # Resize image to fill target with extra margin
        clip = clip.resize(height=int(h * scale_factor))
        if clip.w < w * scale_factor:
            clip = clip.resize(width=int(w * scale_factor))

        # Choose random effect
        effect = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left"])

        if effect == "zoom_in":
            # Start wide, end tight
            def zoom_in_effect(get_frame, t):
                progress = t / duration if duration > 0 else 0
                current_scale = 1.0 + progress * 0.15  # 1.0 -> 1.15
                new_w = int(w / current_scale)
                new_h = int(h / current_scale)
                cx, cy = clip.w // 2, clip.h // 2
                x1 = max(0, cx - new_w // 2)
                y1 = max(0, cy - new_h // 2)
                frame = get_frame(t)
                cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
                from PIL import Image as PILImage
                import numpy as np
                img = PILImage.fromarray(cropped)
                img = img.resize((w, h), PILImage.LANCZOS)
                return np.array(img)
            return clip.fl(zoom_in_effect, apply_to=["mask"])

        elif effect == "zoom_out":
            def zoom_out_effect(get_frame, t):
                progress = t / duration if duration > 0 else 0
                current_scale = 1.15 - progress * 0.15  # 1.15 -> 1.0
                new_w = int(w / current_scale)
                new_h = int(h / current_scale)
                cx, cy = clip.w // 2, clip.h // 2
                x1 = max(0, cx - new_w // 2)
                y1 = max(0, cy - new_h // 2)
                frame = get_frame(t)
                cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
                from PIL import Image as PILImage
                import numpy as np
                img = PILImage.fromarray(cropped)
                img = img.resize((w, h), PILImage.LANCZOS)
                return np.array(img)
            return clip.fl(zoom_out_effect, apply_to=["mask"])

        else:
            # Pan left or right
            direction = 1 if effect == "pan_right" else -1

            def pan_effect(get_frame, t):
                progress = t / duration if duration > 0 else 0
                max_shift = clip.w - w
                shift_x = int(progress * max_shift * 0.5)
                if direction < 0:
                    shift_x = max_shift - shift_x
                shift_x = max(0, min(shift_x, clip.w - w))
                cy = max(0, (clip.h - h) // 2)
                frame = get_frame(t)
                cropped = frame[cy:cy + h, shift_x:shift_x + w]
                if cropped.shape[1] < w or cropped.shape[0] < h:
                    from PIL import Image as PILImage
                    import numpy as np
                    img = PILImage.fromarray(cropped)
                    img = img.resize((w, h), PILImage.LANCZOS)
                    return np.array(img)
                return cropped
            return clip.fl(pan_effect, apply_to=["mask"])

    def _add_subtitles(
        self, clip, text: str, target_res: Tuple[int, int], duration: float,
        CompositeVideoClip, TextClip, ColorClip
    ):
        """Add Vietnamese subtitle text with semi-transparent background bar at bottom."""
        w, h = target_res

        # Wrap long text
        max_chars_per_line = 35 if w < h else 50  # Shorter lines for vertical video
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars_per_line:
                current_line = f"{current_line} {word}".strip()
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        wrapped_text = "\n".join(lines[:3])  # Max 3 lines

        # Create text clip
        fontsize = 36 if w < h else 44
        txt_clip = TextClip(
            wrapped_text,
            fontsize=fontsize,
            color="white",
            font="Arial-Bold",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(int(w * 0.9), None),
            align="center",
        ).set_duration(duration)

        # Position text at bottom with padding
        txt_h = txt_clip.h
        bar_height = txt_h + 30
        y_pos = h - bar_height - 20

        # Semi-transparent background bar
        bg_bar = ColorClip(
            size=(w, bar_height),
            color=(0, 0, 0),
        ).set_opacity(0.6).set_duration(duration).set_position((0, y_pos))

        txt_clip = txt_clip.set_position(("center", y_pos + 15))

        return CompositeVideoClip([clip, bg_bar, txt_clip], size=(w, h))
