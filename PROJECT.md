# Project: Automated YouTube Video Production & Upload Pipeline

## Architecture
A fully automated, zero-cost video production pipeline running on GitHub Actions that scrapes content from source YouTube channels, rewrites content into multi-scene storytelling scripts via Gemini 2.0 Flash, generates matching visual scene illustrations via Pollinations.ai, synthesizes Southern Vietnamese male voiceover narration via edge-tts (`vi-VN-NamMinhNeural`), composes Ken Burns animated videos with burnt-in Vietnamese subtitles via MoviePy/FFmpeg (9:16 Shorts for <60s, 16:9 regular for >=60s), uploads the finished video to YouTube Studio using stealth Playwright automation, and updates repository memory in `knowledge_base.md`.

```
[config/sources.yaml]
         │
         ▼
[YoutubeScraper (Playwright Stealth)] ──> List[ScrapedVideo]
         │
         ▼
[ContentRewriter (Gemini 2.0 Flash + knowledge_base.md)] ──> StoryScript (Scenes)
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
[ImageGenerator (Pollinations.ai)]    [AudioGenerator (edge-tts)]
 (Visual Style & Character Consist)    (vi-VN-NamMinhNeural Audio & Duration)
         │                                        │
         └───────────────────┬────────────────────┘
                             ▼
              [VideoMaker (MoviePy + FFmpeg)]
               - Ken Burns Zoom/Pan
               - Pillow Vietnamese Subtitles (ImageMagick-free)
               - Format: 9:16 (<60s) or 16:9 (>=60s)
               - H.264 / AAC Encoding
                             │
                             ▼
              [YoutubePoster (Playwright Studio)]
               - Stealth Browser & Cookie Auth
               - File Upload, Title, Description, Audience, Public
               - Dry-run bypass support
                             │
                             ▼
              [KnowledgeBase & GitHub Actions]
               - Append history to knowledge_base.md
               - Git commit & push
               - Randomized 3-6h schedule
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Dependencies & Core Models | `requirements.txt` update (`edge-tts`, `moviepy`, `mutagen`, `pytest`) and `src/models/pipeline_models.py` data models | M1 | Survey |
| 2 | Enhanced YouTube Scraper | Rich video metadata scraping (title, description, tags, engagement) with stealth Playwright | M1 | Survey / R1.1 |
| 3 | Gemini Multi-Scene Story Generator | Structured JSON generation for multi-scene scripts with Vietnamese title/description, art style, character style, and scene narrations/prompts | M2 | Survey / R1.2 |
| 4 | Knowledge Base Anti-Repetition | Past themes extraction from `knowledge_base.md` fed into Gemini prompt to prevent repeating topics | M2 | Survey / R1.2 |
| 5 | Multi-Scene Image Generator | Batch scene image generation via Pollinations.ai with style consistency, aspect ratios, and fallback retries | M2 | Survey / R1.3 |
| 6 | Edge-TTS Voiceover Synthesizer | Asynchronous voice synthesis using Southern Vietnamese male voice (`vi-VN-NamMinhNeural`) with exact duration extraction | M2 | Survey / R1.4 |
| 7 | MoviePy + FFmpeg Video Assembler | Ken Burns zoom/pan animation, image-audio synchronization, H.264/AAC MP4 video compilation | M3 | Survey / R1.5 |
| 8 | ImageMagick-Free Subtitle Burning | Dynamic wrapped Vietnamese subtitle overlays rendered with Pillow TrueType font onto video frames | M3 | Survey / R1.5 |
| 9 | Dynamic Aspect Ratio Selection | Automatic 9:16 vertical ($1080\times 1920$) Shorts for $<60$s vs 16:9 horizontal ($1920\times 1080$) for $\ge 60$s | M3 | Survey / R1.5 |
| 10 | YouTube Studio Video Uploader | Playwright stealth automation for YouTube Studio video upload (cookies, file picker, title, desc, audience, visibility public) | M4 | Survey / R1.6 |
| 11 | CLI Orchestrator & Dry-Run Mode | Unified pipeline entry point (`python -m src.main run --dry-run`), stage subcommands, error resilience | M4 | Survey / R1 & R4 |
| 12 | GitHub Actions Workflow & Schedule | Workflow with 3-6h randomized delay (`sleep $((RANDOM % 10800))`), ffmpeg & font setup, secrets pass-through, and auto-commit | M4 | Survey / R3 |
| 13 | Opaque-Box E2E Testing Suite | Multi-tier test suite (Tiers 1-4: Feature, Boundary, Combinatorial, Real-World) and offline mocks | E2E Track | Survey |
| 14 | Final Verification & Hardening | 100% E2E test suite pass + Tier 5 adversarial coverage hardening | M5 | Strategy |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Models & Scraper Enhancement | `requirements.txt`, `src/models/pipeline_models.py`, `src/scraper/youtube_scraper.py` | None | DONE |
| M2 | AI Story, Image & Audio Pipeline | `src/ai_pipeline/content_rewriter.py`, `src/ai_pipeline/image_generator.py`, `src/ai_pipeline/audio_generator.py` | M1 | IN_PROGRESS |
| M3 | Video Maker & Subtitle Assembly | `src/ai_pipeline/video_maker.py` (Ken Burns, Pillow subtitle engine, 9:16/16:9 encoding) | M1, M2 | PLANNED |
| M4 | YouTube Studio Poster, CLI & CI/CD | `src/poster/youtube_poster.py`, `src/main.py`, `.github/workflows/auto_post.yml` | M1, M2, M3 | PLANNED |
| M5 | Final Milestone: 100% E2E Test Pass & Adversarial Hardening | E2E verification across all tiers, gap analysis, coverage hardening | M1, M2, M3, M4, E2E Track | PLANNED |
| E2E | E2E Testing Track | `TEST_INFRA.md`, test fixtures, test cases (Tiers 1-4), `TEST_READY.md` | None (Derives from requirements) | DONE |

## Code Layout
- `src/models/pipeline_models.py` — Dataclasses (`ScrapedVideo`, `Scene`, `StoryScript`, `VideoOutput`, `UploadResult`) [DONE]
- `src/utils/` — `logger.py`, `proxy_manager.py`, `human_simulator.py`, `browser_manager.py` (REUSE)
- `src/memory/knowledge_base.py` — `KnowledgeBase` class (REUSE)
- `src/scraper/` — `base_scraper.py`, `youtube_scraper.py` (MODIFIED with rich metadata & dual-engine) [DONE]
- `src/ai_pipeline/`
  - `content_rewriter.py` — Gemini 2.0 Flash multi-scene story generation [IN_PROGRESS]
  - `image_generator.py` — Pollinations.ai batch scene generator [IN_PROGRESS]
  - `audio_generator.py` — Edge-TTS `vi-VN-NamMinhNeural` synthesizer [IN_PROGRESS]
  - `video_maker.py` — MoviePy/FFmpeg assembly with Pillow subtitles & Ken Burns (M3)
- `src/poster/`
  - `base_poster.py` — Base poster class (REUSE)
  - `youtube_poster.py` — Playwright YouTube Studio video upload automation (M4)
- `src/main.py` — Main CLI orchestrator supporting `run`, `--dry-run`, and modular subcommands (M4)
- `config/` — `sources.yaml`, `niches.yaml` (REUSE)
- `.github/workflows/auto_post.yml` — GitHub Actions workflow with ffmpeg & random 3-6h delay (M4)
- `requirements.txt` — Dependencies specification [DONE]
- `tests/` — Test infrastructure and test suites (E2E & Unit, 117+ tests) [DONE]

## Interface Contracts
### `src/models/pipeline_models.py`
- `ScrapedVideo(title: str, description: str, channel: str, url: str, timestamp: str, views: str, raw_text: str)`
- `Scene(scene_id: int, narration_text_vi: str, image_prompt_en: str, image_path: Optional[str], audio_path: Optional[str], duration: float, status: str)`
- `StoryScript(title_vi: str, description_vi: str, theme: str, art_style: str, scenes: List[Scene], niche: str)`
- `VideoOutput(video_path: str, duration: float, aspect_ratio: str, resolution: Tuple[int, int], fps: int, file_size_bytes: int, scene_count: int)`
- `UploadResult(success: bool, platform: str, video_id: Optional[str], url: Optional[str], status: str, error: Optional[str])`

### `src/scraper/youtube_scraper.py`
- `YoutubeScraper.scrape(url: str, max_posts: int = 5) -> List[ScrapedContent | ScrapedVideo]`
- `YoutubeScraper.scrape_videos(url: str, max_videos: int = 5) -> List[ScrapedVideo]`

### `src/ai_pipeline/content_rewriter.py`
- `ContentRewriter.rewrite_story(scraped_text: str, niche: str = "stories", past_themes: List[str] = None) -> StoryScript`

### `src/ai_pipeline/image_generator.py`
- `ImageGenerator.generate_scene_images(scenes: List[Scene], art_style: str, character_style: str = "", aspect_ratio: str = "9:16") -> List[Scene]`

### `src/ai_pipeline/audio_generator.py`
- `AudioGenerator.generate_scene_audios(scenes: List[Scene], voice: str = "vi-VN-NamMinhNeural") -> List[Scene]`

### `src/ai_pipeline/video_maker.py`
- `VideoMaker.create_video(story_script: StoryScript, output_path: Optional[str] = None, aspect_ratio: Optional[str] = None) -> VideoOutput`

### `src/poster/youtube_poster.py`
- `YoutubePoster.upload_video(video_path: str, title: str, description: str, dry_run: bool = False) -> UploadResult`
