"""
Pipeline Data Models for the Automated YouTube Video Production Pipeline.

Defines strongly typed, dataclass-based models for scraped content,
AI-generated multi-scene scripts, scene assets, video output metadata,
and YouTube Studio upload results.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any, Union
import json

try:
    from ..scraper.base_scraper import ScrapedContent
except (ImportError, ValueError):
    try:
        from src.scraper.base_scraper import ScrapedContent
    except (ImportError, ValueError):
        class ScrapedContent:
            """Fallback ScrapedContent base class."""
            def __init__(self, text: str = "", source_url: str = "", platform: str = "youtube",
                         author: str = "", hashtags: list = None,
                         engagement: dict = None, scraped_at: str = ""):
                self.text = text
                self.source_url = source_url
                self.platform = platform
                self.author = author
                self.hashtags = hashtags or []
                self.engagement = engagement or {}
                self.scraped_at = scraped_at or datetime.now().isoformat()

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "text": self.text,
                    "source_url": self.source_url,
                    "platform": self.platform,
                    "author": self.author,
                    "hashtags": self.hashtags,
                    "engagement": self.engagement,
                    "scraped_at": self.scraped_at
                }


@dataclass
class ScrapedVideo(ScrapedContent):
    """
    Rich metadata representation of a scraped YouTube video or channel item.
    Inherits from ScrapedContent for complete backward compatibility.
    """
    title: str
    description: str = ""
    channel: str = ""
    url: str = ""
    timestamp: str = ""
    views: str = ""
    duration_str: str = ""
    tags: List[str] = field(default_factory=list)
    raw_text: str = ""
    scraped_at: str = ""
    platform: str = "youtube"
    thumbnail_url: str = ""
    is_short: bool = False

    def __post_init__(self):
        self.title = self.title.strip() if self.title else ""
        if not self.title:
            raise ValueError("ScrapedVideo 'title' cannot be empty.")
        if not self.raw_text:
            parts = [self.title]
            if self.description:
                parts.append(self.description)
            if self.views:
                parts.append(f"Views: {self.views}")
            self.raw_text = "\n".join(parts)
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not isinstance(self.tags, list):
            self.tags = list(self.tags) if self.tags else []
        if self.url and not self.is_short and "/shorts/" in self.url:
            self.is_short = True

    # Backward compatibility properties for ScrapedContent callers
    @property
    def text(self) -> str:
        return self.raw_text or self.title

    @text.setter
    def text(self, value: str):
        self.raw_text = value

    @property
    def source_url(self) -> str:
        return self.url

    @source_url.setter
    def source_url(self, value: str):
        self.url = value

    @property
    def author(self) -> str:
        return self.channel

    @author.setter
    def author(self, value: str):
        self.channel = value

    @property
    def hashtags(self) -> List[str]:
        return self.tags

    @hashtags.setter
    def hashtags(self, value: List[str]):
        self.tags = value if isinstance(value, list) else list(value)

    @property
    def engagement(self) -> Dict[str, Any]:
        eng: Dict[str, Any] = {}
        if self.views:
            eng["views"] = self.views
        if self.duration_str:
            eng["duration"] = self.duration_str
        if self.timestamp:
            eng["timestamp"] = self.timestamp
        return eng

    @engagement.setter
    def engagement(self, value: Dict[str, Any]):
        if isinstance(value, dict):
            if "views" in value:
                self.views = str(value["views"])
            if "duration" in value:
                self.duration_str = str(value["duration"])
            if "timestamp" in value:
                self.timestamp = str(value["timestamp"])

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["text"] = self.text
        data["source_url"] = self.source_url
        data["author"] = self.author
        data["hashtags"] = self.hashtags
        data["engagement"] = self.engagement
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapedVideo":
        valid_fields = {
            "title", "description", "channel", "url", "timestamp",
            "views", "duration_str", "tags", "raw_text", "scraped_at",
            "platform", "thumbnail_url", "is_short"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        # Fallback compatibility with legacy ScrapedContent dicts
        if "title" not in filtered and "text" in data:
            raw_text = str(data["text"])
            filtered["title"] = raw_text.split("\n")[0] if raw_text else ""
            filtered["raw_text"] = raw_text
        if "url" not in filtered and "source_url" in data:
            filtered["url"] = data["source_url"]
        if "channel" not in filtered and "author" in data:
            filtered["channel"] = data["author"]
        if "tags" not in filtered and "hashtags" in data:
            filtered["tags"] = data["hashtags"]
        if "views" not in filtered and "engagement" in data and isinstance(data["engagement"], dict):
            filtered["views"] = data["engagement"].get("views", "")
            if "duration" in data["engagement"]:
                filtered["duration_str"] = data["engagement"]["duration"]
            if "timestamp" in data["engagement"]:
                filtered["timestamp"] = data["engagement"]["timestamp"]
        return cls(**filtered)


@dataclass
class Scene:
    """
    Individual scene model representing narration, visual prompts, rendered assets,
    dynamic video clips, and audio synchronization metadata.
    """
    scene_id: int
    narration_text_vi: str
    image_prompt_en: str
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    duration: float = 0.0                      # Voiceover speech duration (seconds)
    status: str = "pending"
    subtitle_text: Optional[str] = None
    
    # --- Dynamic Video Extensions ---
    video_prompt_en: Optional[str] = None      # Cinematic temporal motion prompt
    video_path: Optional[str] = None           # Path to rendered dynamic MP4 clip
    video_clip_duration: float = 0.0          # Native duration of AI video clip
    camera_movement: Optional[str] = "static" # dolly_in, tracking, tilt_up, orbit, etc.
    sync_strategy: str = "auto"                # 'auto', 'trim', 'slowmo', 'ping_pong', 'freeze_pad'
    generation_source: str = "image"           # 'hf_wan2.1', 'hf_ltx', 'pollinations_video', 'local_wan', 'ken_burns'

    def __post_init__(self):
        if not isinstance(self.scene_id, int) or self.scene_id < 1:
            raise ValueError(f"Scene 'scene_id' must be a positive integer >= 1, got {self.scene_id}")
        self.narration_text_vi = self.narration_text_vi.strip() if self.narration_text_vi else ""
        if not self.narration_text_vi:
            raise ValueError("Scene 'narration_text_vi' cannot be empty.")
        self.image_prompt_en = self.image_prompt_en.strip() if self.image_prompt_en else ""
        if not self.image_prompt_en:
            raise ValueError("Scene 'image_prompt_en' cannot be empty.")
        if not self.video_prompt_en:
            self.video_prompt_en = self.image_prompt_en
        if self.duration < 0.0:
            raise ValueError(f"Scene 'duration' cannot be negative, got {self.duration}")
        valid_statuses = {"pending", "image_ready", "video_ready", "audio_ready", "completed", "failed"}
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of {valid_statuses}")
        if self.subtitle_text is None:
            self.subtitle_text = self.narration_text_vi

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        valid_fields = {
            "scene_id", "narration_text_vi", "image_prompt_en",
            "image_path", "audio_path", "duration", "status", "subtitle_text",
            "video_prompt_en", "video_path", "video_clip_duration",
            "camera_movement", "sync_strategy", "generation_source"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        # Backward/alternative key aliases
        if "scene_id" not in filtered:
            filtered["scene_id"] = int(data.get("scene_number", data.get("id", data.get("scene", 1))))
        if "narration_text_vi" not in filtered:
            if "narration" in data:
                filtered["narration_text_vi"] = data["narration"]
            elif "narration_vi" in data:
                filtered["narration_text_vi"] = data["narration_vi"]
            elif "text_vi" in data:
                filtered["narration_text_vi"] = data["text_vi"]
            elif "text" in data:
                filtered["narration_text_vi"] = data["text"]
            elif "vietnamese" in data:
                filtered["narration_text_vi"] = data["vietnamese"]
        if "image_prompt_en" not in filtered:
            if "image_prompt" in data:
                filtered["image_prompt_en"] = data["image_prompt"]
            elif "prompt_en" in data:
                filtered["image_prompt_en"] = data["prompt_en"]
            elif "prompt" in data:
                filtered["image_prompt_en"] = data["prompt"]
            elif "english_prompt" in data:
                filtered["image_prompt_en"] = data["english_prompt"]
        if "duration" in filtered and not isinstance(filtered["duration"], (int, float)):
            filtered["duration"] = float(filtered["duration"])
        return cls(**filtered)


@dataclass
class StoryScript:
    """
    Multi-scene story script containing video metadata, visual styles, and scenes.
    """
    title_vi: str
    description_vi: str
    theme: str
    art_style: str
    scenes: List[Scene] = field(default_factory=list)
    niche: str = "stories"
    character_style: str = ""
    summary: str = ""
    themes: List[str] = field(default_factory=list)
    created_at: str = ""
    video_format: str = ""  # "shorts" or "video"; empty = auto-detect

    def __post_init__(self):
        self.title_vi = self.title_vi.strip() if self.title_vi else ""
        if not self.title_vi:
            raise ValueError("StoryScript 'title_vi' cannot be empty.")
        self.description_vi = self.description_vi.strip() if self.description_vi else ""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not isinstance(self.themes, list):
            self.themes = list(self.themes) if self.themes else []
        if not self.theme and self.themes:
            self.theme = self.themes[0]
        elif not self.theme:
            self.theme = "General"
        if not self.art_style:
            self.art_style = "3D Pixar animation"

        # Convert dict items in scenes to Scene instances if passed as dicts
        converted_scenes: List[Scene] = []
        for s in self.scenes:
            if isinstance(s, dict):
                converted_scenes.append(Scene.from_dict(s))
            elif isinstance(s, Scene):
                converted_scenes.append(s)
            else:
                raise TypeError(f"Expected Scene instance or dict, got {type(s)}")
        self.scenes = converted_scenes

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    @property
    def is_shorts(self) -> bool:
        # If video_format was explicitly set, respect it
        if self.video_format == "shorts":
            return True
        if self.video_format == "video":
            return False
        # Fallback: auto-detect from duration/scene count
        if self.total_duration > 0.0:
            return self.total_duration < 60.0
        return len(self.scenes) <= 4

    @property
    def target_aspect_ratio(self) -> str:
        return "9:16" if self.is_shorts else "16:9"

    def add_scene(self, scene: Union[Scene, Dict[str, Any]]) -> None:
        if isinstance(scene, dict):
            if "scene_id" not in scene and "scene_number" not in scene and "id" not in scene:
                scene["scene_id"] = len(self.scenes) + 1
            scene = Scene.from_dict(scene)
        self.scenes.append(scene)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["scenes"] = [s.to_dict() for s in self.scenes]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryScript":
        valid_fields = {
            "title_vi", "description_vi", "theme", "art_style",
            "scenes", "niche", "character_style", "summary", "themes", "created_at",
            "video_format"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        # Handle key aliases from raw LLM output
        if "title_vi" not in filtered:
            if "title" in data:
                filtered["title_vi"] = data["title"]
            elif "title_vn" in data:
                filtered["title_vi"] = data["title_vn"]
        if "description_vi" not in filtered:
            if "description" in data:
                filtered["description_vi"] = data["description"]
            elif "description_vn" in data:
                filtered["description_vi"] = data["description_vn"]
            else:
                filtered["description_vi"] = ""
        if "theme" not in filtered:
            if "themes" in data and isinstance(data["themes"], list) and data["themes"]:
                filtered["theme"] = data["themes"][0]
            else:
                filtered["theme"] = data.get("topic", "General")
        if "art_style" not in filtered:
            filtered["art_style"] = data.get("image_style", data.get("style", "3D Pixar animation"))

        raw_scenes = filtered.get("scenes", [])
        filtered["scenes"] = [
            Scene.from_dict(s) if isinstance(s, dict) else s
            for s in raw_scenes
        ]
        return cls(**filtered)


@dataclass
class VideoOutput:
    """
    Metadata for the compiled final MP4 video output.
    """
    video_path: str
    duration: float
    aspect_ratio: str
    resolution: Tuple[int, int]
    fps: int = 30
    file_size_bytes: int = 0
    scene_count: int = 0
    has_subtitles: bool = True
    created_at: str = ""

    def __post_init__(self):
        self.video_path = self.video_path.strip() if self.video_path else ""
        if not self.video_path:
            raise ValueError("VideoOutput 'video_path' cannot be empty.")
        if self.duration <= 0.0:
            raise ValueError(f"VideoOutput 'duration' must be > 0.0, got {self.duration}")
        if self.fps <= 0:
            raise ValueError(f"VideoOutput 'fps' must be > 0, got {self.fps}")
        if self.file_size_bytes < 0:
            raise ValueError(f"VideoOutput 'file_size_bytes' cannot be negative, got {self.file_size_bytes}")
        if not isinstance(self.resolution, tuple):
            self.resolution = tuple(self.resolution)
        if len(self.resolution) != 2 or self.resolution[0] <= 0 or self.resolution[1] <= 0:
            raise ValueError(f"Invalid resolution tuple, expected (width, height), got {self.resolution}")
        valid_aspects = {"9:16", "16:9", "1:1", "4:5"}
        if self.aspect_ratio not in valid_aspects:
            raise ValueError(f"Invalid aspect_ratio '{self.aspect_ratio}'. Must be one of {valid_aspects}")
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["resolution"] = list(self.resolution)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoOutput":
        valid_fields = {
            "video_path", "duration", "aspect_ratio", "resolution",
            "fps", "file_size_bytes", "scene_count", "has_subtitles", "created_at"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        if "resolution" in filtered and isinstance(filtered["resolution"], (list, tuple)):
            filtered["resolution"] = tuple(filtered["resolution"])
        if "duration" in filtered and not isinstance(filtered["duration"], (int, float)):
            filtered["duration"] = float(filtered["duration"])
        if "fps" in filtered and not isinstance(filtered["fps"], int):
            filtered["fps"] = int(filtered["fps"])
        if "file_size_bytes" in filtered and not isinstance(filtered["file_size_bytes"], int):
            filtered["file_size_bytes"] = int(filtered["file_size_bytes"])
        return cls(**filtered)


@dataclass
class UploadResult:
    """
    Status and metadata for the YouTube Studio video upload.
    """
    success: bool
    platform: str = "youtube"
    video_id: Optional[str] = None
    url: Optional[str] = None
    status: str = "published"
    error: Optional[str] = None
    uploaded_at: str = ""

    def __post_init__(self):
        if not self.uploaded_at:
            self.uploaded_at = datetime.now().isoformat()
        if not self.success and self.status == "published":
            self.status = "failed"
        valid_statuses = {"published", "draft", "processing", "dry_run", "failed"}
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid upload status '{self.status}'. Must be one of {valid_statuses}")

    # Backward compatibility with PostResult
    @property
    def post_url(self) -> str:
        return self.url or ""

    @post_url.setter
    def post_url(self, value: str):
        self.url = value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UploadResult":
        valid_fields = {
            "success", "platform", "video_id", "url", "status", "error", "uploaded_at"
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        # Legacy PostResult compatibility
        if "url" not in filtered and "post_url" in data:
            filtered["url"] = data["post_url"]
        return cls(**filtered)
