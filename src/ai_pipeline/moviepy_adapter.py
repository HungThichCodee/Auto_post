"""
src/ai_pipeline/moviepy_adapter.py
Universal cross-version adapter supporting MoviePy 1.x and MoviePy 2.x.
"""

import logging
from typing import Any, Callable, Tuple, Union

logger = logging.getLogger(__name__)

try:
    # MoviePy 1.x style
    from moviepy.editor import (
        AudioClip,
        AudioFileClip,
        ColorClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        TextClip,
        VideoFileClip,
        afx,
        concatenate_videoclips,
        vfx,
    )
    MOVIEPY_V2 = False
except ImportError:
    # MoviePy 2.x style
    try:
        from moviepy import (
            AudioClip,
            AudioFileClip,
            ColorClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ImageClip,
            TextClip,
            VideoFileClip,
            afx,
            concatenate_videoclips,
            vfx,
        )
        MOVIEPY_V2 = True
    except ImportError as e:
        raise ImportError(f"MoviePy is not installed: {e}")


class MoviePyAdapter:
    """Shields pipeline from MoviePy 1.x vs 2.x breaking changes."""

    @staticmethod
    def set_duration(clip: Any, duration: float) -> Any:
        if hasattr(clip, "with_duration"):
            return clip.with_duration(duration)
        return clip.set_duration(duration)

    @staticmethod
    def set_audio(clip: Any, audio: Any) -> Any:
        if hasattr(clip, "with_audio"):
            return clip.with_audio(audio)
        return clip.set_audio(audio)

    @staticmethod
    def set_position(clip: Any, position: Union[str, Tuple[Any, Any], Callable]) -> Any:
        if hasattr(clip, "with_position"):
            return clip.with_position(position)
        return clip.set_position(position)

    @staticmethod
    def set_start(clip: Any, start_time: float) -> Any:
        if hasattr(clip, "with_start"):
            return clip.with_start(start_time)
        return clip.set_start(start_time)

    @staticmethod
    def set_fps(clip: Any, fps: int) -> Any:
        if hasattr(clip, "with_fps"):
            return clip.with_fps(fps)
        return clip.set_fps(fps)

    @staticmethod
    def resize(clip: Any, newsize: Union[float, Tuple[int, int]]) -> Any:
        if hasattr(clip, "resized"):
            return clip.resized(newsize)
        if hasattr(clip, "resize"):
            return clip.resize(newsize)
        return clip

    @staticmethod
    def subclip(clip: Any, start: float, end: float) -> Any:
        if hasattr(clip, "subclipped"):
            return clip.subclipped(start, end)
        return clip.subclip(start, end)

    @staticmethod
    def time_transform(clip: Any, func: Callable) -> Any:
        if hasattr(clip, "transform"):
            return clip.transform(func)
        return clip.fl(func)

    @staticmethod
    def apply_speedx(clip: Any, factor: float) -> Any:
        """Applies playback speed scaling across MoviePy 1.x and 2.x."""
        if hasattr(clip, "with_effects"):
            try:
                from moviepy.video.fx import MultiplySpeed
                return clip.with_effects([MultiplySpeed(factor)])
            except (ImportError, AttributeError):
                pass
        if hasattr(clip, "fx") and hasattr(vfx, "speedx"):
            return clip.fx(vfx.speedx, factor=factor)
        return clip

    @staticmethod
    def apply_time_mirror(clip: Any) -> Any:
        """Applies reverse playback (time mirror) across MoviePy 1.x and 2.x."""
        if hasattr(clip, "with_effects"):
            try:
                from moviepy.video.fx import TimeMirror
                return clip.with_effects([TimeMirror()])
            except (ImportError, AttributeError):
                pass
        if hasattr(clip, "fx") and hasattr(vfx, "time_mirror"):
            return clip.fx(vfx.time_mirror)
        return clip

    @staticmethod
    def image_clip_from_frame(clip: Any, t: float) -> Any:
        """Extracts frame at timestamp t as a standalone ImageClip."""
        if hasattr(clip, "to_ImageClip"):
            return clip.to_ImageClip(t=t)
        if hasattr(clip, "to_image_clip"):
            return clip.to_image_clip(t=t)
        return ImageClip(clip.get_frame(t))
