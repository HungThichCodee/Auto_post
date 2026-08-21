#!/usr/bin/env python3
"""
Auto_post — Automated Social Media Content Pipeline

CLI entry point for scraping, content generation, and auto-posting.

Usage:
    python -m src.main scrape --platform facebook --dry-run
    python -m src.main generate --niche humor --dry-run
    python -m src.main post --platform facebook
    python -m src.main run  # Full pipeline
    python -m src.main run --dry-run  # Full pipeline without posting
"""

import asyncio
import argparse
import json
import os
import random
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import yaml

from src.utils.logger import setup_logger, log_step
from src.utils.proxy_manager import ProxyManager
from src.utils.browser_manager import BrowserManager
from src.scraper.base_scraper import ScrapedContent
from src.scraper.facebook_scraper import FacebookScraper
from src.scraper.tiktok_scraper import TiktokScraper
from src.scraper.youtube_scraper import YoutubeScraper
from src.ai_pipeline.content_rewriter import ContentRewriter
from src.ai_pipeline.image_generator import ImageGenerator
from src.memory.knowledge_base import KnowledgeBase
from src.poster.facebook_poster import FacebookPoster
from src.poster.tiktok_poster import TiktokPoster
from src.poster.youtube_poster import YoutubePoster


# Load environment variables
load_dotenv()

logger = setup_logger("main")

# Platform mappings
SCRAPERS = {
    "facebook": FacebookScraper,
    "tiktok": TiktokScraper,
    "youtube": YoutubeScraper,
}

POSTERS = {
    "facebook": FacebookPoster,
    "tiktok": TiktokPoster,
    "youtube": YoutubePoster,
}

COOKIE_ENV_KEYS = {
    "facebook": "FB_COOKIES",
    "tiktok": "TIKTOK_COOKIES",
    "youtube": "YT_COOKIES",
}


def load_config(config_name: str) -> dict:
    """Load a YAML config file from the config/ directory."""
    config_path = PROJECT_ROOT / "config" / config_name
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_cookies(platform: str) -> Optional[str]:
    """Get cookies for a platform from environment variables."""
    env_key = COOKIE_ENV_KEYS.get(platform)
    if env_key:
        cookies = os.getenv(env_key)
        if cookies:
            return cookies
        logger.warning(f"No cookies found for {platform} (env: {env_key})")
    return None


async def cmd_scrape(args: argparse.Namespace) -> list[ScrapedContent]:
    """Execute the scrape command."""
    log_step(logger, "SCRAPE", f"Platform: {args.platform}")

    sources_config = load_config("sources.yaml")
    platform_config = sources_config.get(args.platform, {})
    sources = platform_config.get("sources", [])

    if not sources:
        logger.error(f"No sources configured for platform: {args.platform}")
        return []

    # Initialize proxy manager
    proxy_list = os.getenv("PROXY_LIST")
    proxy_manager = ProxyManager(proxy_list=proxy_list)

    if not proxy_list:
        log_step(logger, "PROXY", "Fetching free proxies...")
        await proxy_manager.fetch_free_proxies()

    # Initialize browser
    browser_manager = BrowserManager(proxy_manager=proxy_manager)
    await browser_manager.launch(headless=not args.debug if hasattr(args, 'debug') else True)

    all_scraped: list[ScrapedContent] = []

    try:
        cookies = get_cookies(args.platform)
        scraper_class = SCRAPERS[args.platform]
        scraper = scraper_class(browser_manager=browser_manager, cookies_json=cookies)

        for source in sources:
            url = source.get("url", "")
            niche = source.get("niche", "general")
            max_posts = args.max_posts if hasattr(args, 'max_posts') else 5

            log_step(logger, "SCRAPE", f"Scraping {url} (niche: {niche})")

            try:
                await scraper.setup()
                scraped = await scraper.scrape(url=url, max_posts=max_posts)
                all_scraped.extend(scraped)
                log_step(logger, "SCRAPE", f"Got {len(scraped)} posts from {url}")
                await scraper.teardown()
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                continue

        if args.dry_run:
            logger.info("=== DRY RUN — Scraped Content ===")
            for i, content in enumerate(all_scraped, 1):
                logger.info(f"\n--- Post {i} ---")
                logger.info(f"Source: {content.source_url}")
                logger.info(f"Text: {content.text[:200]}...")
                logger.info(f"Hashtags: {content.hashtags}")

    finally:
        await browser_manager.close()

    log_step(logger, "SCRAPE", f"Total scraped: {len(all_scraped)} posts")
    return all_scraped


async def cmd_generate(
    args: argparse.Namespace,
    raw_content: Optional[str] = None,
    niche_name: Optional[str] = None,
    platform: Optional[str] = None,
) -> Optional[dict]:
    """Execute the generate command."""
    target_niche = niche_name or args.niche
    target_platform = platform or (args.platform if hasattr(args, 'platform') else "facebook")

    log_step(logger, "GENERATE", f"Niche: {target_niche}, Platform: {target_platform}")

    # Load niche config
    niches_config = load_config("niches.yaml")
    niche_data = niches_config.get("niches", {}).get(target_niche)

    if not niche_data:
        logger.error(f"Unknown niche: {target_niche}. Available: {list(niches_config.get('niches', {}).keys())}")
        return None

    # Load knowledge base
    kb = KnowledgeBase(filepath=str(PROJECT_ROOT / "knowledge_base.md"))
    knowledge_history = kb.read_history()
    recent_themes = kb.get_recent_themes(n=20)

    log_step(logger, "MEMORY", f"Loaded {kb.get_entry_count()} past entries, {len(recent_themes)} recent themes")

    # Use provided content or generate sample for testing
    if not raw_content:
        raw_content = (
            "Đây là nội dung mẫu để test. Chủ đề về sức khỏe và rau củ quả. "
            "Cách ăn uống lành mạnh mỗi ngày."
        )
        logger.info("Using sample content for generation (no scraped content provided)")

    # Initialize AI pipeline
    rewriter = ContentRewriter()

    # Add recent themes to niche data for AI context
    niche_data_with_context = {**niche_data, "avoid_themes": recent_themes}

    result = await rewriter.rewrite_content(
        raw_content=raw_content,
        niche=niche_data_with_context,
        knowledge_history=knowledge_history,
        platform=target_platform,
    )

    if not result:
        logger.error("Content generation failed")
        return None

    log_step(logger, "GENERATE", f"Content generated ({len(result.get('content', ''))} chars)")
    log_step(logger, "GENERATE", f"Image prompt: {result.get('image_prompt', '')[:100]}...")

    # Generate image
    if not args.dry_run:
        img_gen = ImageGenerator(output_dir=str(PROJECT_ROOT / "output"))
        image_path = await img_gen.generate_image(
            prompt=result.get("image_prompt", ""),
            width=1024,
            height=1024,
        )
        result["image_path"] = image_path
        log_step(logger, "IMAGE", f"Image saved to: {image_path}")
    else:
        result["image_path"] = ""
        logger.info("=== DRY RUN — Skipping image generation ===")
        logger.info(f"Generated content:\n{result.get('content', '')}")
        logger.info(f"Image prompt:\n{result.get('image_prompt', '')}")

    return result


async def cmd_post(
    args: argparse.Namespace,
    content: Optional[str] = None,
    image_path: Optional[str] = None,
) -> bool:
    """Execute the post command."""
    target_platform = args.platform

    log_step(logger, "POST", f"Platform: {target_platform}")

    if not content:
        logger.error("No content to post. Run 'generate' first or use 'run' for full pipeline.")
        return False

    if not image_path or not Path(image_path).exists():
        logger.warning(f"Image not found at {image_path}, posting without image")
        image_path = ""

    if args.dry_run:
        logger.info("=== DRY RUN — Would post: ===")
        logger.info(f"Platform: {target_platform}")
        logger.info(f"Content: {content[:200]}...")
        logger.info(f"Image: {image_path}")
        return True

    # Initialize browser for posting
    browser_manager = BrowserManager()
    await browser_manager.launch(headless=True)

    try:
        cookies = get_cookies(target_platform)
        if not cookies:
            logger.error(f"No cookies configured for {target_platform}. Cannot post.")
            return False

        poster_class = POSTERS[target_platform]
        poster = poster_class(browser_manager=browser_manager, cookies_json=cookies)

        await poster.setup()
        result = await poster.post(content=content, image_path=image_path)
        await poster.teardown()

        if result.success:
            log_step(logger, "POST", f"✅ Posted successfully to {target_platform}")
            if result.post_url:
                log_step(logger, "POST", f"Post URL: {result.post_url}")
        else:
            log_step(logger, "POST", f"❌ Failed to post: {result.error}")

        return result.success

    finally:
        await browser_manager.close()


async def cmd_run(args: argparse.Namespace):
    """Execute the full pipeline: scrape → generate → post."""
    log_step(logger, "PIPELINE", "=" * 60)
    log_step(logger, "PIPELINE", "Starting full Auto_post pipeline")
    log_step(logger, "PIPELINE", f"Time: {datetime.now().isoformat()}")
    log_step(logger, "PIPELINE", "=" * 60)

    sources_config = load_config("sources.yaml")
    platforms = args.platforms.split(",") if hasattr(args, 'platforms') and args.platforms else list(sources_config.keys())

    # Randomize platform order for natural behavior
    random.shuffle(platforms)

    kb = KnowledgeBase(filepath=str(PROJECT_ROOT / "knowledge_base.md"))

    for platform in platforms:
        log_step(logger, "PIPELINE", f"--- Processing platform: {platform} ---")

        platform_config = sources_config.get(platform, {})
        sources = platform_config.get("sources", [])

        if not sources:
            logger.warning(f"No sources for {platform}, skipping")
            continue

        # Pick a random source to scrape
        source = random.choice(sources)
        niche_name = source.get("niche", "humor")

        # Step 1: Scrape
        log_step(logger, "PIPELINE", "Step 1/4: Scraping content...")
        scrape_args = argparse.Namespace(
            platform=platform,
            dry_run=args.dry_run,
            max_posts=3,
            debug=False,
        )

        try:
            scraped = await cmd_scrape(scrape_args)
        except Exception as e:
            logger.error(f"Scraping failed for {platform}: {e}")
            scraped = []

        # Use scraped content or fallback
        if scraped:
            raw_content = "\n\n".join([s.text for s in scraped[:3]])
        else:
            logger.warning("No content scraped, using fallback sample content")
            raw_content = None  # Will use sample in generate

        # Step 2: Generate content
        log_step(logger, "PIPELINE", "Step 2/4: Generating AI content...")
        gen_args = argparse.Namespace(
            niche=niche_name,
            platform=platform,
            dry_run=args.dry_run,
        )

        try:
            generated = await cmd_generate(
                gen_args,
                raw_content=raw_content,
                niche_name=niche_name,
                platform=platform,
            )
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            continue

        if not generated:
            logger.error("Generation returned no content, skipping platform")
            continue

        # Step 3: Post
        log_step(logger, "PIPELINE", "Step 3/4: Posting to platform...")
        post_args = argparse.Namespace(
            platform=platform,
            dry_run=args.dry_run,
        )

        try:
            success = await cmd_post(
                post_args,
                content=generated.get("content", ""),
                image_path=generated.get("image_path", ""),
            )
        except Exception as e:
            logger.error(f"Posting failed: {e}")
            success = False

        # Step 4: Update knowledge base
        log_step(logger, "PIPELINE", "Step 4/4: Updating knowledge base...")
        if success or args.dry_run:
            kb.append_entry(
                platform=platform,
                niche=niche_name,
                content_summary=generated.get("summary", "Content generated"),
                themes=generated.get("themes", []),
                post_url="",
            )
            log_step(logger, "MEMORY", "Knowledge base updated")

        # Random delay between platforms (2-5 minutes)
        if platform != platforms[-1]:
            delay = random.randint(120, 300)
            log_step(logger, "PIPELINE", f"Waiting {delay}s before next platform...")
            if not args.dry_run:
                await asyncio.sleep(delay)

    log_step(logger, "PIPELINE", "=" * 60)
    log_step(logger, "PIPELINE", "Pipeline completed!")
    log_step(logger, "PIPELINE", "=" * 60)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="auto_post",
        description="Auto_post — Automated Social Media Content Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main scrape --platform facebook --dry-run
  python -m src.main generate --niche humor --dry-run
  python -m src.main post --platform facebook
  python -m src.main run --dry-run
  python -m src.main run --platforms facebook,tiktok
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape content from social media")
    scrape_parser.add_argument(
        "--platform",
        choices=["facebook", "tiktok", "youtube"],
        required=True,
        help="Platform to scrape from",
    )
    scrape_parser.add_argument("--max-posts", type=int, default=5, help="Max posts to scrape per source")
    scrape_parser.add_argument("--dry-run", action="store_true", help="Show results without saving")
    scrape_parser.add_argument("--debug", action="store_true", help="Run browser in visible mode")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate AI content")
    gen_parser.add_argument(
        "--niche",
        choices=["stories", "humor", "health"],
        required=True,
        help="Content niche",
    )
    gen_parser.add_argument(
        "--platform",
        choices=["facebook", "tiktok", "youtube"],
        default="facebook",
        help="Target platform for tone adjustment",
    )
    gen_parser.add_argument("--dry-run", action="store_true", help="Generate without saving image")

    # Post command
    post_parser = subparsers.add_parser("post", help="Post content to social media")
    post_parser.add_argument(
        "--platform",
        choices=["facebook", "tiktok", "youtube"],
        required=True,
        help="Platform to post to",
    )
    post_parser.add_argument("--content", type=str, help="Content text to post")
    post_parser.add_argument("--image", type=str, help="Path to image file")
    post_parser.add_argument("--dry-run", action="store_true", help="Show what would be posted")

    # Run command (full pipeline)
    run_parser = subparsers.add_parser("run", help="Run full pipeline (scrape → generate → post)")
    run_parser.add_argument(
        "--platforms",
        type=str,
        default="",
        help="Comma-separated platforms (default: all configured)",
    )
    run_parser.add_argument("--dry-run", action="store_true", help="Run without posting")

    return parser


async def main():
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    log_step(logger, "START", f"Auto_post v1.0 — Command: {args.command}")

    try:
        if args.command == "scrape":
            await cmd_scrape(args)
        elif args.command == "generate":
            await cmd_generate(args)
        elif args.command == "post":
            if hasattr(args, 'content') and args.content:
                await cmd_post(args, content=args.content, image_path=getattr(args, 'image', ''))
            else:
                logger.error("Use --content flag or 'run' command for full pipeline")
        elif args.command == "run":
            await cmd_run(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    log_step(logger, "END", "Auto_post finished")


if __name__ == "__main__":
    asyncio.run(main())
