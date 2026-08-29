import asyncio
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Union

from src.models.pipeline_models import Scene, StoryScript, VideoOutput
from src.ai_pipeline.duration_synchronizer import DurationSynchronizer

logger = logging.getLogger(__name__)

class VideoMaker:
    """Assembles synced video clips and subtitles into a final video."""

    SHORTS_RES = (1080, 1920)
    REGULAR_RES = (1920, 1080)

    def __init__(self, output_dir: Union[str, Path] = "output/assets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.duration_synchronizer = DurationSynchronizer(use_ffmpeg_direct=True)
        logger.info(f"VideoMaker initialized. Output: {self.output_dir}")

    async def create_video(
        self,
        story: StoryScript,
        output_path: str = "output/final_video.mp4",
        use_ffmpeg_demuxer: bool = True,
    ) -> VideoOutput:
        """Assembles synchronized video clips with ASS subtitles and outro card into final MP4."""
        from src.ai_pipeline.moviepy_adapter import (
            VideoFileClip, AudioClip, concatenate_videoclips, MoviePyAdapter
        )

        valid_scenes = [
            s for s in story.scenes
            if ((s.video_path and os.path.exists(s.video_path)) or
                (s.image_path and os.path.exists(s.image_path))) and
               (s.audio_path and os.path.exists(s.audio_path))
        ]

        if not valid_scenes:
            raise ValueError("No valid scenes with valid video/image and audio paths found.")

        is_shorts = story.is_shorts
        target_res = self.SHORTS_RES if is_shorts else self.REGULAR_RES
        margin_v = 480 if is_shorts else 65

        synced_clip_paths = []
        scene_clips = []

        for scene in valid_scenes:
            synced_path = str(self.output_dir / f"synced_scene_{scene.scene_id:03d}.mp4")
            if scene.video_path and os.path.exists(scene.video_path):
                # Dynamic Video Clip -> Duration Synchronizer
                await self.duration_synchronizer.synchronize_scene(
                    scene.video_path, scene.audio_path, synced_path, target_resolution=target_res
                )
            else:
                # Static Image Fallback -> 2.5D Ken Burns Transform
                await self._render_ken_burns_video(scene, synced_path, target_res)

            # Burn Subtitles into individual scene
            subtitled_path = str(self.output_dir / f"subtitled_scene_{scene.scene_id:03d}.mp4")
            await self._burn_scene_subtitles(synced_path, scene, subtitled_path, margin_v)
            synced_clip_paths.append(subtitled_path)

        if use_ffmpeg_demuxer and shutil.which("ffmpeg"):
            concat_list_path = self.output_dir / "scenes_list.txt"
            
            # Write outro clip
            outro_path = str(self.output_dir / "outro_scene.mp4")
            await self._create_outro_video(target_res, outro_path)
            synced_clip_paths.append(outro_path)

            with open(concat_list_path, "w", encoding="utf-8") as f:
                for p in synced_clip_paths:
                    f.write(f"file '{Path(p).resolve().as_posix()}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list_path),
                "-c", "copy",
                output_path
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"FFmpeg concat failed: {stderr.decode()}")
        else:
            for p in synced_clip_paths:
                scene_clips.append(VideoFileClip(p))

            outro_path = str(self.output_dir / "outro_scene.mp4")
            await self._create_outro_video(target_res, outro_path)
            scene_clips.append(VideoFileClip(outro_path))

            final = concatenate_videoclips(scene_clips, method="chain")
            final.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                ffmpeg_params=["-crf", "18", "-movflags", "+faststart"],
                logger=None
            )
            for c in scene_clips:
                c.close()
            final.close()

        return VideoOutput(
            video_path=output_path,
            duration=await self.duration_synchronizer.probe_duration(output_path),
            aspect_ratio="9:16" if is_shorts else "16:9",
            resolution=target_res,
            fps=30,
            file_size_bytes=os.path.getsize(output_path),
            scene_count=len(valid_scenes),
            has_subtitles=True,
        )

    async def _render_ken_burns_video(self, scene: Scene, output_path: str, target_res: Tuple[int, int]):
        """Renders 2.5D Ken Burns from static image via MoviePy."""
        from src.ai_pipeline.moviepy_adapter import (
            ImageClip, AudioFileClip, MoviePyAdapter
        )
        def _process():
            audio = AudioFileClip(scene.audio_path)
            duration = audio.duration
            img_clip = ImageClip(scene.image_path).set_duration(duration)

            w, h = target_res
            scale_factor = 1.08
            img_clip = MoviePyAdapter.resize(img_clip, height=int(h * scale_factor))
            if img_clip.w < w * scale_factor:
                img_clip = MoviePyAdapter.resize(img_clip, width=int(w * scale_factor))

            effect = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left"])
            
            if effect == "zoom_in":
                def zoom_in_effect(get_frame, t):
                    progress = t / duration if duration > 0 else 0
                    current_scale = 1.0 + progress * 0.06
                    new_w, new_h = int(w / current_scale), int(h / current_scale)
                    cx, cy = img_clip.w // 2, img_clip.h // 2
                    x1, y1 = max(0, cx - new_w // 2), max(0, cy - new_h // 2)
                    frame = get_frame(t)
                    cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
                    from PIL import Image as PILImage
                    import numpy as np
                    img = PILImage.fromarray(cropped).resize((w, h), PILImage.LANCZOS)
                    return np.array(img)
                img_clip = MoviePyAdapter.time_transform(img_clip, zoom_in_effect)
            else:
                def zoom_out_effect(get_frame, t):
                    progress = t / duration if duration > 0 else 0
                    current_scale = 1.06 - progress * 0.06
                    new_w, new_h = int(w / current_scale), int(h / current_scale)
                    cx, cy = img_clip.w // 2, img_clip.h // 2
                    x1, y1 = max(0, cx - new_w // 2), max(0, cy - new_h // 2)
                    frame = get_frame(t)
                    cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
                    from PIL import Image as PILImage
                    import numpy as np
                    img = PILImage.fromarray(cropped).resize((w, h), PILImage.LANCZOS)
                    return np.array(img)
                img_clip = MoviePyAdapter.time_transform(img_clip, zoom_out_effect)

            img_clip = MoviePyAdapter.set_audio(img_clip, audio)
            img_clip.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac", preset="fast", logger=None)
            img_clip.close()
            audio.close()
            
        await asyncio.to_thread(_process)

    async def _burn_scene_subtitles(self, input_path: str, scene: Scene, output_path: str, margin_v: int):
        """Burns subtitles directly via MoviePy since Windows FFmpeg ASS setup is complex without external font configs."""
        from src.ai_pipeline.moviepy_adapter import (
            VideoFileClip, TextClip, ColorClip, CompositeVideoClip, MoviePyAdapter
        )
        def _process():
            clip = VideoFileClip(input_path)
            w, h = clip.w, clip.h
            text = scene.subtitle_text or scene.narration_text_vi
            max_chars = 30 if w < h else 45
            
            words = text.split()
            lines, current_line = [], ""
            for word in words:
                if len(current_line) + len(word) + 1 <= max_chars:
                    current_line = f"{current_line} {word}".strip()
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            wrapped_text = "\n".join(lines[:3])

            fontsize = 48 if w < h else 52
            
            try:
                txt_clip = TextClip(
                    wrapped_text,
                    fontsize=fontsize,
                    color="white",
                    font="Noto-Sans-CJK-JP-Bold",
                    stroke_color="black",
                    stroke_width=3,
                    method="caption",
                    size=(int(w * 0.9), None),
                    align="center",
                ).set_duration(clip.duration)
                
                bar_height = txt_clip.h + 40
                y_pos = h - bar_height - (25 if w < h else 65)

                bg_bar = ColorClip(size=(w, bar_height), color=(0, 0, 0))
                bg_bar = MoviePyAdapter.set_duration(bg_bar, clip.duration)
                bg_bar = bg_bar.set_opacity(0.7).set_position((0, y_pos))

                txt_clip = txt_clip.set_position(("center", y_pos + 20))
                
                final = CompositeVideoClip([clip, bg_bar, txt_clip], size=(w, h))
            except Exception as e:
                logger.warning(f"TextClip failed: {e}. Outputting without subtitles.")
                final = clip
                
            final.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac", preset="fast", logger=None)
            final.close()
            clip.close()

        await asyncio.to_thread(_process)

    async def _create_outro_video(self, target_res: Tuple[int, int], output_path: str):
        """Creates an outro MP4 clip."""
        from src.ai_pipeline.moviepy_adapter import (
            ColorClip, TextClip, CompositeVideoClip, AudioClip, MoviePyAdapter, MOVIEPY_V2
        )
        def _process():
            w, h = target_res
            duration = 3.0
            bg = ColorClip(size=(w, h), color=(15, 15, 25))
            bg = MoviePyAdapter.set_duration(bg, duration)

            try:
                cta_clip = TextClip(
                    "ĐĂNG KÝ KÊNH 🔔\nLIKE 👍 CHIA SẺ 🔗",
                    fontsize=52 if w < h else 56,
                    color="white",
                    font="Noto-Sans-CJK-JP-Bold",
                    stroke_color="black",
                    stroke_width=2,
                    method="caption",
                    size=(int(w * 0.85), None),
                    align="center",
                )
                cta_clip = MoviePyAdapter.set_duration(cta_clip, duration).set_position("center")
                final = CompositeVideoClip([bg, cta_clip], size=(w, h))
            except Exception:
                final = bg

            silence_audio = AudioClip(lambda t: [0, 0] if MOVIEPY_V2 else 0, duration=duration, fps=48000)
            final = MoviePyAdapter.set_audio(final, silence_audio)
            
            final.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac", preset="fast", logger=None)
            final.close()

        await asyncio.to_thread(_process)
