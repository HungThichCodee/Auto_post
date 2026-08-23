# Auto_post Test Infrastructure & 4-Tier Test Architecture (`TEST_INFRA.md`)

## 1. Executive Summary & Test Philosophy

This document defines the test architecture, mock interceptors, synthetic media generators, and 4-tier test verification matrix for the **Auto_post** automated YouTube video production pipeline.

### Core Testing Principles:
1. **100% Offline & Deterministic Execution**: No live external network calls (Gemini API, Pollinations.ai HTTP endpoints, Microsoft Edge-TTS servers, YouTube Studio web pages). All external dependencies are intercepted via hermetic pytest mocks.
2. **Sub-Millisecond Synthetic Media Generation**: No heavy video/audio encoding in unit tests. Pure-Python synthetic MPEG-1 Layer 3 MP3 audio frame generation and Pillow PNG generation produce valid binary media files in $<5\text{ms}$.
3. **Opaque-Box & Requirement-Driven**: Tests derive directly from `ORIGINAL_REQUEST.md` and `PROJECT.md` interface contracts, ensuring progressive testability and verification across milestones M1 through M5.
4. **4-Tier Comprehensive Verification Matrix**:
   - **Tier 1: Feature Coverage** ($\ge 5$ test cases per feature across all 14 project features $= 70+$ cases).
   - **Tier 2: Boundary & Corner Cases** (BVA, rate limits, empty/corrupted data, duration thresholds at 59.99s vs 60.00s, Vietnamese diacritics stress $= 70+$ cases).
   - **Tier 3: Pairwise Combinations** (Cross-feature interaction matrix covering scraping, rewriter styles, aspect ratios, subtitle fonts, and poster dry-run).
   - **Tier 4: Real-World Production Workloads** (5 end-to-end multi-scene story workloads: 3D Animal Cartoon Shorts, Anime Adventure, Mythology Epic, Comic Gag, Space Science).

---

## 2. Directory Layout

```
Auto_post/
├── TEST_INFRA.md                          # Test infrastructure and 4-tier architecture spec
├── TEST_READY.md                          # Test readiness report and execution metrics
├── pytest.ini                             # Pytest configuration and custom test markers
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # Root pytest fixtures, synthetic media generators, mock interceptors
│   ├── fixtures/                          # Reusable static JSON & YAML datasets
│   │   ├── sample_scraped_videos.json     # Pre-recorded YouTube scraping metadata
│   │   ├── sample_story_scripts.json      # Multi-scene scripts (Shorts 9:16, Regular 16:9, boundaries)
│   │   ├── sample_cookies.json            # Valid, expired, and malformed YouTube Studio cookies
│   │   ├── test_sources.yaml              # Mock channel sources configuration
│   │   └── test_niches.yaml               # Mock niche and prompt configurations
│   ├── unit/                              # Isolated module unit tests
│   │   ├── test_pipeline_models.py        # Dataclass serialization, deserialization & computed properties
│   │   ├── test_knowledge_base.py         # Memory I/O, anti-repetition theme extraction, windowing
│   │   ├── test_content_rewriter.py       # Gemini prompt construction, JSON code-fence stripping, fallbacks
│   │   ├── test_image_generator.py        # Pollinations URL encoding, retry loops, batch scene generation
│   │   ├── test_audio_generator.py        # Edge-TTS voice synthesis, duration extraction, batch audio
│   │   ├── test_video_maker.py            # MoviePy assembly, Ken Burns math, Pillow ImageMagick-free subtitles
│   │   ├── test_youtube_poster.py         # Playwright Studio selectors, upload flow, --dry-run bypass
│   │   └── test_stealth_browser.py        # BrowserManager stealth flags & HumanSimulator interaction
│   ├── integration/                       # Multi-stage integration tests
│   │   ├── test_cli_runner.py             # CLI parser, subcommands (run, scrape, generate, post), configs
│   │   └── test_pipeline_integration.py   # Multi-stage pipeline integration, dry-run, KB update loop
│   └── e2e/                               # 4-Tier Opaque-Box E2E test suites
│       ├── test_tier1_feature_coverage.py # 14 Features x 5+ test cases
│       ├── test_tier2_boundary_corner.py  # BVA boundaries, diacritics, rate limits, corrupt inputs
│       ├── test_tier3_pairwise_combinations.py # Feature interaction pairs matrix
│       └── test_tier4_real_world_workloads.py  # 5 realistic production channel workloads
```

---

## 3. Pure-Python Synthetic Media Generators

To achieve instant execution speeds without invoking FFmpeg or downloading remote media files, `tests/conftest.py` provides high-speed media generators:

### 3.1 Fast Pure-Python MPEG-1 Layer 3 MP3 Generator
- Standard MPEG-1 Audio Layer III frame header: `0xFF, 0xFB, 0x90, 0x64` (128 kbps bitrate, 44.1 kHz sampling rate, stereo).
- Each frame encodes 1,152 audio samples ($\approx 26.122\text{ ms}$).
- Frame payload size: 417 bytes.
- To produce an audio file of exact duration $D$ seconds:
  $$N_{\text{frames}} = \max\left(1, \operatorname{round}\left(D \times \frac{44100}{1152}\right)\right)$$
- Output is a 100% valid MP3 binary stream parseable by `mutagen`, `moviepy`, `ffmpeg`, and `pydub` in $<3\text{ms}$.

### 3.2 High-Speed Pillow PNG Image Generator
- Creates RGB/RGBA images of arbitrary canvas sizes (e.g. $1080\times 1920$ for Shorts, $1920\times 1080$ for Regular).
- Supports solid fills, dynamic color gradients, diagnostic grid lines, and embedded text watermarks for visual inspection.
- Memory-buffered output (`io.BytesIO`) or atomic disk writing in $<5\text{ms}$.

### 3.3 Synthetic Minimal Video Container Generator
- Emits lightweight valid MP4 container headers or uses MoviePy's fast `ColorClip` with synthetic audio clips for assembly tests.

---

## 4. Mock Interceptors Architecture

### 4.1 Gemini 2.0 Flash Async Mock (`MockGeminiModel`)
- Intercepts `google.generativeai.GenerativeModel.generate_content_async`.
- Provides dynamic responses based on prompt inspection or canned `StoryScript` JSON structures.
- Supports fault injection modes: `rate_limit` (HTTP 429), `malformed_json`, `empty_response`, and `non_vietnamese`.

### 4.2 Pollinations.ai HTTP Transport Mock (`pollinations_mock_handler`)
- Intercepts `httpx.AsyncClient.get` requests matching `https://image.pollinations.ai/prompt/*`.
- Parses query parameters (`width`, `height`, `model`, `seed`, `nologo`).
- Returns HTTP 200 with valid synthetic PNG bytes matching requested dimensions.
- Supports fault injection: `trigger_500`, `trigger_timeout`, `trigger_corrupt` ($<1024$ bytes).

### 4.3 Edge-TTS Voice Synthesis Mock (`MockEdgeTTSCommunicate`)
- Intercepts `edge_tts.Communicate.save(output_path)`.
- Validates voice parameter (`vi-VN-NamMinhNeural` Southern Vietnamese male or `vi-VN-HoaiMyNeural`).
- Synthesizes synthetic MP3 file with duration matching text word count ($\approx 3.0$ words per second).

### 4.4 Playwright YouTube Studio Mock (`MockPlaywrightPage`)
- Emulates Chromium browser context and YouTube Studio DOM tree (`studio.youtube.com`).
- Tracks selector clicks (`#create-icon`, `#text-item-0`, `#next-button`, `#done-button`), file inputs (`#file-loader`), text inputs (title, description), and audience radio buttons ("Not made for kids", "Public").
- Validates `--dry-run` zero-browser bypass.

---

## 5. 4-Tier Test Architecture Specification

### Tier 1: Feature Coverage (70+ Test Cases)
Isolated functional verification of all 14 features in `PROJECT.md § Feature Inventory`:
- **F01**: Data Models (`ScrapedVideo`, `Scene`, `StoryScript`, `VideoOutput`, `UploadResult`).
- **F02**: YouTube Scraper (Dual-engine extraction, consent banner handling, URL normalization).
- **F03**: Gemini Story Generator (Vietnamese narration, English visual prompts, scene structuring).
- **F04**: Knowledge Base Memory (Read, append, recent themes extraction, auto-initialization).
- **F05**: Image Generator (Pollinations URL formatting, batch scene generation, aspect ratios).
- **F06**: Edge-TTS Voiceover (Vietnamese Southern voice `vi-VN-NamMinhNeural`, duration math).
- **F07**: Video Maker (MoviePy assembly, Ken Burns zoom/pan math, H.264/AAC MP4 encoding).
- **F08**: Subtitle Engine (Pillow ImageMagick-free rendering, Vietnamese diacritics, auto-wrap).
- **F09**: Dynamic Aspect Ratio Selection (9:16 Shorts $<60$s vs 16:9 Regular $\ge 60$s).
- **F10**: YouTube Poster (Playwright Studio automation, cookie injection, dry-run mode).
- **F11**: CLI Orchestrator (Subcommands `run`, `scrape`, `generate`, `post`, flags parsing).
- **F12**: GitHub Actions CI/CD (YAML validation, 3-6h random delay, secrets, auto-commit).
- **F13**: Testing Framework (Synthetic media generators, mock interceptors, fixtures).
- **F14**: Hardening & Verification (Error resilience, resource cleanup, zero API keys audit).

### Tier 2: Boundary & Corner Cases (70+ Test Cases)
- **BVA on Duration**: Exact boundaries at $0.0\text{s}$, $0.5\text{s}$, $59.90\text{s}$, $59.99\text{s}$, $60.00\text{s}$, $60.01\text{s}$, $3600.0\text{s}$.
- **Vietnamese Typography Stress**: Full set of 134 Vietnamese Unicode characters and tone marks (`thuở`, `nguyễn`, `quằn quại`, `khuất tất`, `sừng sững`).
- **Text Length Extremes**: Empty strings, 1-character strings, 300+ character unbroken sentences, 10,000-character transcripts.
- **Fault Injection & Resilience**: Gemini rate limits (429), malformed JSON, Pollinations 504 timeouts, corrupt $<1$KB images, expired cookies, missing files.

### Tier 3: Cross-Feature Pairwise Combinations (20+ Scenarios)
- Matrix testing combinations of:
  - Input Niches: `stories`, `humor`, `health`, `science`, `mythology`.
  - Durations / Aspect Ratios: `45s (9:16 Shorts)` vs `75s (16:9 Regular)`.
  - Art Styles: `3D Pixar Cartoon`, `Anime Shinkai`, `Mythological Oil Painting`, `Comic Gag`.
  - Subtitle Configurations: Standard wrap, multi-line wrap, heavy diacritics.
  - Poster Execution: Dry-run bypass vs simulated Studio upload.

### Tier 4: Real-World Workload Scenarios (5 Production Workloads)
1. **Workload 1: Animal 3D Cartoon Shorts** (3 scenes, 45s, 9:16 vertical Shorts, cute animal theme).
2. **Workload 2: Anime Adventure Long Video** (5 scenes, 75s, 16:9 horizontal Regular, epic adventure).
3. **Workload 3: Mythology Epic Tale** (4 scenes, 59.5s Shorts boundary, folklore & heavy diacritics).
4. **Workload 4: Comic Gag Rapid-Fire** (3 scenes, 30s, 9:16 vertical Shorts, humorous timing).
5. **Workload 5: Space Science Documentary** (6 scenes, 90s, 16:9 horizontal Regular, astronomical facts).

---

## 6. Verification & Execution Commands

```bash
# Run entire test suite (Unit, Integration, and E2E Tiers 1-4)
pytest -v

# Run by test categories
pytest tests/unit -v
pytest tests/integration -v
pytest tests/e2e -v

# Run individual E2E tiers
pytest tests/e2e/test_tier1_feature_coverage.py -v
pytest tests/e2e/test_tier2_boundary_corner.py -v
pytest tests/e2e/test_tier3_pairwise_combinations.py -v
pytest tests/e2e/test_tier4_real_world_workloads.py -v

# Run with coverage report
pytest --cov=src --cov-report=term-missing
```
