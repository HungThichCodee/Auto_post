#!/usr/bin/env python3
"""
Auto_post — Automated YouTube Video Production Pipeline

CLI entry point for scraping, content generation, video assembly, and auto-uploading.

Usage:
    python -m src.main scrape --platform youtube
    python -m src.main generate --niche stories
    python -m src.main post --video output/final_video.mp4
    python -m src.main run              # Full pipeline
    python -m src.main run --dry-run    # Full pipeline without uploading
"""

import asyncio
import argparse
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import yaml

from src.utils.logger import setup_logger, log_step
from src.utils.proxy_manager import ProxyManager
from src.utils.browser_manager import BrowserManager
from src.scraper.youtube_scraper import YoutubeScraper
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import ImageGenerator
from src.ai_pipeline.audio_generator import AudioGenerator
from src.ai_pipeline.video_maker import VideoMaker
from src.memory.knowledge_base import KnowledgeBase
from src.poster.youtube_poster import YoutubePoster
from src.models.pipeline_models import StoryScript, Scene

# Load environment variables
load_dotenv()

logger = setup_logger("auto_post")

# Config paths
SOURCES_CONFIG = os.path.join(PROJECT_ROOT, "config", "sources.yaml")
NICHES_CONFIG = os.path.join(PROJECT_ROOT, "config", "niches.yaml")
KB_PATH = os.path.join(PROJECT_ROOT, "knowledge_base.md")


def load_yaml_config(path: str) -> dict:
    """Load a YAML configuration file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load config {path}: {e}")
        return {}


async def cmd_scrape(args):
    """Scrape content from configured YouTube sources."""
    log_step(logger, "SCRAPE", f"Platform: {args.platform}")

    sources_config = load_yaml_config(SOURCES_CONFIG)
    platform_sources = sources_config.get(args.platform, {}).get("sources", [])

    if not platform_sources:
        logger.error(f"No sources configured for platform '{args.platform}' in sources.yaml")
        return []

    proxy_manager = ProxyManager(os.getenv("PROXY_LIST"))
    browser_manager = BrowserManager(proxy_manager=proxy_manager)

    all_scraped = []
    try:
        await browser_manager.launch(headless=True)

        cookies_json = os.getenv("YT_COOKIES")
        scraper = YoutubeScraper(browser_manager, cookies_json=cookies_json)

        for source in platform_sources:
            url = source.get("url", "")
            niche = source.get("niche", "stories")
            logger.info(f"Scraping: {url} (niche: {niche})")

            try:
                await scraper.setup()
                results = await scraper.scrape(url, max_posts=3)
                for r in results:
                    r.niche = niche if hasattr(r, 'niche') else None
                all_scraped.extend(results)
                logger.info(f"Scraped {len(results)} items from {url}")
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
            finally:
                await scraper.teardown()

    except Exception as e:
        logger.error(f"Scrape error: {e}")
    finally:
        await browser_manager.close()

    log_step(logger, "SCRAPE COMPLETE", f"Total items: {len(all_scraped)}")
    return all_scraped


async def cmd_generate(args, scraped_text: str = ""):
    """Generate story script, images, and audio from scraped content."""
    log_step(logger, "GENERATE", f"Niche: {args.niche if hasattr(args, 'niche') else 'stories'}")

    niche = args.niche if hasattr(args, 'niche') else "stories"
    niches_config = load_yaml_config(NICHES_CONFIG)
    niche_data = niches_config.get("niches", {}).get(niche, {})

    # Initialize AI
    api_key = os.getenv("GEMINI_API_KEY")
    rewriter = ContentRewriter(api_key=api_key)

    # Get past themes to avoid repetition
    kb = KnowledgeBase(filepath=KB_PATH)
    past_themes = kb.get_recent_themes(n=20)

    # If no scraped text, use a default prompt
    if not scraped_text:
        scraped_text = (
            "Những câu chuyện thú vị về thế giới động vật dễ thương. "
            "Chó mèo vui nhộn, phiêu lưu kỳ thú trong khu rừng phép thuật."
        )

    # Step 1: Generate story script
    log_step(logger, "AI REWRITE", "Generating multi-scene story...")
    story = await rewriter.rewrite_story(
        scraped_text=scraped_text,
        niche=niche,
        past_themes=past_themes,
    )
    logger.info(f"Story: '{story.title_vi}' with {story.scene_count} scenes")

    # Step 2: Generate images for each scene
    log_step(logger, "IMAGE GEN", f"Generating {story.scene_count} scene images...")
    image_gen = ImageGenerator(output_dir="output/images")
    aspect_ratio = story.target_aspect_ratio
    try:
        story.scenes = await image_gen.generate_scene_images(
            scenes=story.scenes,
            art_style=story.art_style,
            character_style=story.character_style,
            aspect_ratio=aspect_ratio,
        )
        images_done = sum(1 for s in story.scenes if s.image_path)
        logger.info(f"Generated {images_done}/{story.scene_count} images")
    except Exception as e:
        logger.error(f"Image generation error: {e}")

    # Step 3: Generate voiceover audio for each scene
    log_step(logger, "AUDIO GEN", "Generating voiceover audio...")
    audio_gen = AudioGenerator(output_dir="output/audio")
    try:
        story.scenes = await audio_gen.generate_scene_audios(
            scenes=story.scenes,
            voice="vi-VN-NamMinhNeural",
        )
        audios_done = sum(1 for s in story.scenes if s.audio_path)
        logger.info(f"Generated {audios_done}/{story.scene_count} audio files")
    except Exception as e:
        logger.error(f"Audio generation error: {e}")

    return story


async def cmd_make_video(story: StoryScript, output_path: str = "output/final_video.mp4"):
    """Assemble video from story scenes."""
    log_step(logger, "VIDEO ASSEMBLY", f"Creating video from {story.scene_count} scenes...")

    video_maker = VideoMaker(output_dir="output")
    try:
        video_output = await video_maker.create_video(
            story=story,
            output_path=output_path,
        )
        logger.info(
            f"Video created: {video_output.video_path} "
            f"({video_output.duration:.1f}s, {video_output.aspect_ratio}, "
            f"{video_output.file_size_bytes / 1024 / 1024:.1f}MB)"
        )
        return video_output
    except Exception as e:
        logger.error(f"Video assembly error: {e}")
        return None


async def cmd_post(args=None, video_path: str = "", title: str = "",
                   description: str = "", dry_run: bool = False):
    """Upload video to YouTube."""
    log_step(logger, "UPLOAD", f"Uploading to YouTube (dry_run={dry_run})")

    if args and hasattr(args, 'video'):
        video_path = args.video
    if args and hasattr(args, 'dry_run'):
        dry_run = args.dry_run

    if not video_path or not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None

    cookies_json = os.getenv("YT_COOKIES")
    if not cookies_json and not dry_run:
        logger.error("YT_COOKIES not set — cannot upload without authentication")
        return None

    proxy_manager = ProxyManager(os.getenv("PROXY_LIST"))
    browser_manager = BrowserManager(proxy_manager=proxy_manager)

    try:
        await browser_manager.launch(headless=True)
        poster = YoutubePoster(browser_manager, cookies_json=cookies_json)

        result = await poster.upload_video(
            video_path=video_path,
            title=title or "Video tự động",
            description=description or "Video được tạo tự động bởi AI",
            dry_run=dry_run,
        )

        if result.success:
            logger.info(f"Upload successful! URL: {result.post_url}")
        else:
            logger.error(f"Upload failed: {result.error}")

        return result
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None
    finally:
        await browser_manager.close()


async def cmd_run(args):
    """Execute the full pipeline: scrape → generate → video → upload → memory."""
    log_step(logger, "FULL PIPELINE", f"Starting (dry_run={args.dry_run})")
    start_time = datetime.now()

    # ── Step 1: Scrape ──
    scraped_items = await cmd_scrape(args)
    scraped_text = ""
    niche = "stories"

    if scraped_items:
        # Combine scraped text
        texts = []
        for item in scraped_items:
            if hasattr(item, "text") and item.text:
                texts.append(item.text)
            elif hasattr(item, "raw_text") and item.raw_text:
                texts.append(item.raw_text)
            elif hasattr(item, "title") and item.title:
                texts.append(item.title)
        scraped_text = "\n\n---\n\n".join(texts)

        # Get niche from first source config
        sources_config = load_yaml_config(SOURCES_CONFIG)
        platform_sources = sources_config.get("youtube", {}).get("sources", [])
        if platform_sources:
            niche = platform_sources[0].get("niche", "stories")
    else:
        logger.warning("No content scraped. Using default prompt for content generation.")

    # ── Step 2: Generate (Story + Images + Audio) ──
    class GenArgs:
        def __init__(self, n):
            self.niche = n
    story = await cmd_generate(GenArgs(niche), scraped_text=scraped_text)

    if not story or story.scene_count == 0:
        logger.error("Story generation failed — no scenes produced.")
        return

    # ── Step 3: Assemble Video ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = f"output/video_{timestamp}.mp4"
    video_output = await cmd_make_video(story, output_path=video_path)

    if not video_output:
        logger.error("Video assembly failed.")
        return

    # ── Step 4: Upload to YouTube ──
    upload_result = await cmd_post(
        video_path=video_output.video_path,
        title=story.title_vi,
        description=story.description_vi,
        dry_run=args.dry_run,
    )

    # ── Step 5: Update Knowledge Base ──
    if upload_result and upload_result.success:
        log_step(logger, "MEMORY", "Updating knowledge base...")
        kb = KnowledgeBase(filepath=KB_PATH)
        entry_content = (
            f"**Tiêu đề:** {story.title_vi}\n"
            f"**Chủ đề:** {story.theme}\n"
            f"**Số cảnh:** {story.scene_count}\n"
            f"**Thời lượng:** {video_output.duration:.1f}s\n"
            f"**Định dạng:** {video_output.aspect_ratio}\n"
            f"**URL:** {upload_result.post_url}\n"
        )
        kb.append_entry(
            title=story.title_vi,
            content=entry_content,
            themes=story.themes,
        )
        logger.info("Knowledge base updated.")
    elif args.dry_run:
        log_step(logger, "MEMORY (DRY RUN)", "Would update knowledge base")
    else:
        logger.warning("Upload was not successful — knowledge base not updated.")

    # ── Step 6: Cleanup ──
    log_step(logger, "CLEANUP", "Removing temporary files...")
    for scene in story.scenes:
        for path in [scene.image_path, scene.audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    elapsed = (datetime.now() - start_time).total_seconds()
    log_step(logger, "PIPELINE COMPLETE", f"Total time: {elapsed:.0f}s")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Auto_post — Automated YouTube Video Production Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scrape
    scrape_parser = subparsers.add_parser("scrape", help="Scrape content from sources")
    scrape_parser.add_argument(
        "--platform", default="youtube", choices=["youtube", "facebook", "tiktok"],
        help="Platform to scrape from (default: youtube)"
    )

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate story, images, and audio")
    gen_parser.add_argument(
        "--niche", default="stories", choices=["stories", "humor", "health"],
        help="Content niche (default: stories)"
    )

    # post
    post_parser = subparsers.add_parser("post", help="Upload a video to YouTube")
    post_parser.add_argument("--video", required=True, help="Path to video file")
    post_parser.add_argument("--title", default="", help="Video title")
    post_parser.add_argument("--description", default="", help="Video description")
    post_parser.add_argument("--dry-run", action="store_true", help="Log steps without uploading")

    # run (full pipeline)
    run_parser = subparsers.add_parser("run", help="Run the full pipeline")
    run_parser.add_argument(
        "--platform", default="youtube", choices=["youtube"],
        help="Platform (default: youtube)"
    )
    run_parser.add_argument("--dry-run", action="store_true", help="Skip actual upload")

    return parser


async def async_main():
    """Async entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    logger.info(f"=== Auto_post Pipeline — Command: {args.command} ===")

    if args.command == "scrape":
        await cmd_scrape(args)
    elif args.command == "generate":
        await cmd_generate(args)
    elif args.command == "post":
        await cmd_post(args)
    elif args.command == "run":
        await cmd_run(args)
    else:
        parser.print_help()


def main():
    """Main entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
