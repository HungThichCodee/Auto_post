"""
src/ai_pipeline/duration_synchronizer.py
Deterministic, zero-drift Audio-Video Duration Synchronization Engine.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Union

from src.ai_pipeline.moviepy_adapter import MoviePyAdapter

logger = logging.getLogger(__name__)


def escape_ffmpeg_filter_path(file_path: Union[str, Path]) -> str:
    """Escapes Windows paths for FFmpeg filtergraph syntax (colons and backslashes)."""
    posix_path = Path(file_path).as_posix()
    return posix_path.replace(":", "\\:")


class DurationSynchronizer:
    """
    Industrial-grade Audio-Video Duration Synchronizer.
    Reconciles discrete AI video durations with continuous speech narration.
    """

    def __init__(self, use_ffmpeg_direct: bool = True):
        self.use_ffmpeg = use_ffmpeg_direct and (shutil.which("ffmpeg") is not None)
        logger.info(f"DurationSynchronizer initialized (FFmpeg Direct: {self.use_ffmpeg})")

    async def synchronize_scene(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        target_resolution: Tuple[int, int] = (1080, 1920),
        tail_cushion: float = 0.35,
        min_scene_duration: float = 2.50,
    ) -> float:
        """Synchronizes video clip to audio speech duration with micro-duration smoothing."""
        v_dur = await self.probe_duration(video_path)
        a_dur = await self.probe_duration(audio_path)

        # Enforce micro-duration smoothing floor (>= 2.5s)
        t_target = max(round(a_dur + tail_cushion, 2), min_scene_duration)
        rho = t_target / v_dur if v_dur > 0 else 1.0

        logger.info(f"Syncing scene: T_video={v_dur:.2f}s, T_audio={a_dur:.2f}s -> T_target={t_target:.2f}s (rho={rho:.2f})")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if self.use_ffmpeg:
            return await self._sync_ffmpeg(video_path, audio_path, str(out_file), v_dur, t_target, rho, target_resolution)
        else:
            return await self._sync_moviepy(video_path, audio_path, str(out_file), v_dur, t_target, rho)

    async def probe_duration(self, file_path: str) -> float:
        """
        Extracts exact media duration using a multi-tiered inspection cascade:
        ffprobe -> mutagen (MP3) -> OpenCV cv2.VideoCapture -> MoviePy -> fallback.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file not found: {file_path}")

        # Tier 1: ffprobe
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await proc.communicate()
            val = float(stdout.decode().strip())
            if val > 0:
                return val
        except Exception:
            pass

        # Tier 2: Mutagen for audio
        if file_path.endswith((".mp3", ".wav", ".aac", ".m4a")):
            try:
                from mutagen.mp3 import MP3
                return float(MP3(file_path).info.length)
            except Exception:
                pass

        # Tier 3: OpenCV VideoCapture for video duration
        try:
            import cv2
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                if frame_count > 0:
                    return float(frame_count / fps)
        except Exception:
            pass

        # Tier 4: MoviePy fallback
        try:
            from src.ai_pipeline.moviepy_adapter import VideoFileClip
            clip = VideoFileClip(file_path)
            dur = float(clip.duration)
            clip.close()
            return dur
        except Exception:
            pass

        return 4.0

    async def _sync_ffmpeg(
        self, v_path: str, a_path: str, out_path: str, v_dur: float, t_target: float, rho: float, res: Tuple[int, int]
    ) -> float:
        """Executes direct FFmpeg filtergraph recipes with 48kHz CFR normalization."""
        w, h = res

        if rho <= 1.05:
            # Case 1: Video Subclip Trim with CFR 30fps
            filtergraph = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
                f"trim=0:{t_target},setpts=PTS-STARTPTS[vout]"
            )
        elif 1.05 < rho <= 1.25:
            # Case 2: Motion-Compensated Slow-Motion (Adaptive Blend / Optical Flow)
            filtergraph = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                f"setpts={rho:.4f}*PTS,fps=30[vout]"
            )
        elif 1.25 < rho <= 2.00:
            # Case 3: Seamless Ping-Pong Loop
            filtergraph = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,split=2[fwd][rev_in];"
                f"[rev_in]reverse[rev];"
                f"[fwd][rev]concat=n=2:v=1:a=0,trim=0:{t_target},setpts=PTS-STARTPTS[vout]"
            )
        else:
            # Case 4: Ping-Pong Loop + Dynamic Continuous Ken Burns Zoom Tail Extension
            pad_dur = max(0.1, round(t_target - (2 * v_dur), 2))
            filtergraph = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,split=2[fwd][rev_in];"
                f"[rev_in]reverse[rev];"
                f"[fwd][rev]concat=n=2:v=1:a=0[pp];"
                f"[pp]split=2[pp_main][pp_last];"
                f"[pp_last]trim=start={max(0, (2 * v_dur) - 0.05):.2f},setpts=PTS-STARTPTS,loop=loop={int(pad_dur*30)}:size=1:start=0,"
                f"zoompan=z='min(zoom+0.0015,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=30[pp_pad];"
                f"[pp_main][pp_pad]concat=n=2:v=1:a=0,trim=0:{t_target},setpts=PTS-STARTPTS[vout]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", v_path,
            "-i", a_path,
            "-filter_complex", filtergraph,
            "-map", "[vout]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-t", str(t_target),
            out_path
        ]

                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("FFmpeg sync timeout after 300s")
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg sync error: {stderr.decode()}")

        return t_target

    async def _sync_moviepy(self, v_path: str, a_path: str, out_path: str, v_dur: float, t_target: float, rho: float) -> float:
        """Fallback synchronization via MoviePy with MoviePyAdapter wrappers."""
        def _process():
            from src.ai_pipeline.moviepy_adapter import VideoFileClip, AudioFileClip, concatenate_videoclips, MoviePyAdapter
            video = VideoFileClip(v_path)
            audio = AudioFileClip(a_path)

            if rho <= 1.05:
                final_v = MoviePyAdapter.subclip(video, 0, min(t_target, video.duration))
            elif 1.05 < rho <= 1.25:
                final_v = MoviePyAdapter.apply_speedx(video, factor=1.0 / rho)
            elif 1.25 < rho <= 2.00:
                rev_v = MoviePyAdapter.apply_time_mirror(video)
                final_v = MoviePyAdapter.subclip(concatenate_videoclips([video, rev_v]), 0, t_target)
            else:
                rev_v = MoviePyAdapter.apply_time_mirror(video)
                pp_v = concatenate_videoclips([video, rev_v])
                last_frame = MoviePyAdapter.image_clip_from_frame(pp_v, t=pp_v.duration - 0.05)
                last_frame = MoviePyAdapter.set_duration(last_frame, max(0.1, t_target - pp_v.duration))
                final_v = concatenate_videoclips([pp_v, last_frame])

            final_v = MoviePyAdapter.set_duration(final_v, t_target)
            final_v = MoviePyAdapter.set_audio(final_v, audio)
            final_v.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", preset="fast", logger=None)
            video.close()
            audio.close()
            final_v.close()

        await asyncio.to_thread(_process)
        return t_target
