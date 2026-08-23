"""
src/scraper/youtube_scraper.py
Enhanced YouTube Scraper with Dual-Engine Metadata Extraction (ytInitialData + DOM Fallback)
"""

import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from .base_scraper import BaseScraper, ScrapedContent
from ..models.pipeline_models import ScrapedVideo
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class YoutubeScraper(BaseScraper):
    """
    Enhanced Playwright-based YouTube scraper supporting:
    - Channel videos & shorts scraping
    - Direct video URL scraping (/watch?v=..., /shorts/...)
    - Dual-engine extraction: window.ytInitialData + multi-selector DOM fallback
    - Anti-detection and human-like browsing simulation
    - Full backward compatibility with ScrapedContent
    """

    async def scrape(self, url: str, max_posts: int = 5) -> List[ScrapedVideo]:
        """
        Scrapes video metadata from the given URL.
        Satisfies BaseScraper abstract method while returning rich ScrapedVideo instances.
        """
        return await self.scrape_videos(url=url, max_videos=max_posts)

    async def scrape_videos(self, url: str, max_videos: int = 5) -> List[ScrapedVideo]:
        """
        Scrapes rich video metadata (title, description, duration, tags, views, url, channel).
        """
        results: List[ScrapedVideo] = []
        if not self.page:
            await self.setup()

        try:
            target_url = self._normalize_url(url)
            self.logger.info(f"Navigating to YouTube target URL: {target_url}")
            await self._safe_execute(self.page.goto, target_url, timeout=60000)
            await self.simulator.random_delay(2.0, 4.0)

            # Dismiss consent banner
            await self._dismiss_consent_popup()

            # Check if target is a single video or channel
            if self._is_single_video_url(target_url):
                video = await self._scrape_single_video(target_url)
                if video:
                    results.append(video)
                return results

            # Attempt Engine 1: ytInitialData Extraction
            initial_data_videos = await self._extract_via_yt_initial_data()
            if initial_data_videos:
                self.logger.info(f"Engine 1 (ytInitialData) extracted {len(initial_data_videos)} videos.")
                for v in initial_data_videos:
                    if len(results) >= max_videos:
                        break
                    if not any(r.url == v.url for r in results):
                        results.append(v)

            # If Engine 1 yielded insufficient results, trigger Engine 2 (DOM extraction with scrolling)
            if len(results) < max_videos:
                self.logger.info("Engine 1 returned insufficient items. Executing Engine 2 (DOM extraction)...")
                dom_videos = await self._extract_via_dom_scrolling(max_videos=max_videos, existing=results)
                results = dom_videos

        except Exception as e:
            self.logger.error(f"Error during YouTube scraping: {e}", exc_info=True)

        self.logger.info(f"Scraping completed. Total videos extracted: {len(results)}")
        return results[:max_videos]

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent scraping."""
        clean = url.strip()
        if self._is_single_video_url(clean):
            return clean

        clean = clean.rstrip("/")
        for suffix in ["/featured", "/about", "/community"]:
            if clean.endswith(suffix):
                clean = clean.rsplit("/", 1)[0]
                break

        if not (clean.endswith("/videos") or clean.endswith("/shorts")):
            if any(k in clean for k in ["/@", "/channel/", "/c/", "/user/"]):
                clean = f"{clean}/videos"

        return clean

    def _is_single_video_url(self, url: str) -> bool:
        """Check if URL points to a specific video."""
        return "/watch" in url or "youtu.be/" in url or "/shorts/" in url

    async def _dismiss_consent_popup(self):
        """Dismiss multi-lingual cookie and consent popups."""
        consent_selectors = [
            "button[aria-label='Accept all']",
            "button[aria-label='Accept the use of cookies and other data for the purposes described']",
            "button[aria-label='Chấp nhận tất cả']",
            "button[aria-label*='Accept']",
            "button[aria-label*='Chấp nhận']",
            "button[aria-label*='Agree']",
            "button[aria-label*='Đồng ý']",
            "ytd-consent-bump-v2-lightbox button",
            "form[action*='consent'] button",
            "#lightbox button",
            "button:has-text('Accept all')",
            "button:has-text('Reject all')",
            "button:has-text('I agree')",
            "button:has-text('Chấp nhận tất cả')"
        ]
        for selector in consent_selectors:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=1500):
                    await button.click()
                    self.logger.info(f"Dismissed consent popup via selector: {selector}")
                    await self.simulator.random_delay(0.5, 1.5)
                    break
            except Exception:
                continue

        try:
            await self.page.evaluate("""() => {
                const overlays = document.querySelectorAll('ytd-consent-bump-v2-lightbox, tp-yt-iron-overlay-backdrop');
                overlays.forEach(el => el.remove());
            }""")
        except Exception:
            pass

    async def _extract_via_yt_initial_data(self) -> List[ScrapedVideo]:
        """Engine 1: Extract videos directly from window.ytInitialData in page JS."""
        videos: List[ScrapedVideo] = []
        try:
            yt_data = await self.page.evaluate("() => window.ytInitialData")
            if not yt_data or not isinstance(yt_data, dict):
                return []

            tabs = yt_data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            for tab in tabs:
                tab_renderer = tab.get("tabRenderer", {})
                content = tab_renderer.get("content", {})

                # Check richGridRenderer or sectionListRenderer
                items = []
                if "richGridRenderer" in content:
                    items = content["richGridRenderer"].get("contents", [])
                elif "sectionListRenderer" in content:
                    sub_contents = content["sectionListRenderer"].get("contents", [])
                    for sub in sub_contents:
                        item_section = sub.get("itemSectionRenderer", {}).get("contents", [])
                        for is_item in item_section:
                            if "gridRenderer" in is_item:
                                items.extend(is_item["gridRenderer"].get("items", []))

                for item in items:
                    renderer = None
                    if "richItemRenderer" in item:
                        rich_content = item["richItemRenderer"].get("content", {})
                        renderer = rich_content.get("videoRenderer") or rich_content.get("reelItemRenderer")
                    elif "gridVideoRenderer" in item:
                        renderer = item["gridVideoRenderer"]
                    elif "videoRenderer" in item:
                        renderer = item["videoRenderer"]
                    elif "reelItemRenderer" in item:
                        renderer = item["reelItemRenderer"]

                    if renderer:
                        video = self._parse_renderer_dict(renderer)
                        if video:
                            videos.append(video)

        except Exception as e:
            self.logger.warning(f"Engine 1 (ytInitialData) extraction failed: {e}")

        return videos

    def _parse_renderer_dict(self, r: dict) -> Optional[ScrapedVideo]:
        """Parses a videoRenderer / gridVideoRenderer / reelItemRenderer dictionary."""
        try:
            video_id = r.get("videoId", "")
            if not video_id:
                return None

            url = f"https://www.youtube.com/watch?v={video_id}"

            # Title extraction
            title = ""
            if "title" in r:
                t_obj = r["title"]
                if isinstance(t_obj, dict):
                    if "runs" in t_obj and t_obj["runs"]:
                        title = t_obj["runs"][0].get("text", "")
                    elif "simpleText" in t_obj:
                        title = t_obj["simpleText"]
                    elif "accessibility" in t_obj:
                        title = t_obj.get("accessibility", {}).get("accessibilityData", {}).get("label", "")
                elif isinstance(t_obj, str):
                    title = t_obj
            elif "headline" in r:
                h_obj = r["headline"]
                if isinstance(h_obj, dict):
                    title = h_obj.get("simpleText", "")
                elif isinstance(h_obj, str):
                    title = h_obj

            if not title:
                return None

            # Views extraction
            views = ""
            if "viewCountText" in r:
                v_obj = r["viewCountText"]
                if isinstance(v_obj, dict):
                    views = v_obj.get("simpleText", "")
                    if not views and "runs" in v_obj and v_obj["runs"]:
                        views = "".join([x.get("text", "") for x in v_obj["runs"]])
                elif isinstance(v_obj, str):
                    views = v_obj
            elif "shortViewCountText" in r:
                sv_obj = r["shortViewCountText"]
                if isinstance(sv_obj, dict):
                    views = sv_obj.get("simpleText", "")
                    if not views and "runs" in sv_obj and sv_obj["runs"]:
                        views = "".join([x.get("text", "") for x in sv_obj["runs"]])
                elif isinstance(sv_obj, str):
                    views = sv_obj

            # Timestamp extraction
            timestamp = ""
            if "publishedTimeText" in r:
                pt_obj = r["publishedTimeText"]
                if isinstance(pt_obj, dict):
                    timestamp = pt_obj.get("simpleText", "")
                    if not timestamp and "runs" in pt_obj and pt_obj["runs"]:
                        timestamp = "".join([x.get("text", "") for x in pt_obj["runs"]])
                elif isinstance(pt_obj, str):
                    timestamp = pt_obj

            # Duration extraction
            duration_str = ""
            if "lengthText" in r:
                lt_obj = r["lengthText"]
                if isinstance(lt_obj, dict):
                    duration_str = lt_obj.get("simpleText", "")
                    if not duration_str and "runs" in lt_obj and lt_obj["runs"]:
                        duration_str = "".join([x.get("text", "") for x in lt_obj["runs"]])
                elif isinstance(lt_obj, str):
                    duration_str = lt_obj

            # Channel / Author extraction
            channel = ""
            if "ownerText" in r and isinstance(r["ownerText"], dict) and r["ownerText"].get("runs"):
                channel = r["ownerText"]["runs"][0].get("text", "")
            elif "shortBylineText" in r and isinstance(r["shortBylineText"], dict) and r["shortBylineText"].get("runs"):
                channel = r["shortBylineText"]["runs"][0].get("text", "")

            # Description snippet
            description = ""
            if "descriptionSnippet" in r and isinstance(r["descriptionSnippet"], dict) and r["descriptionSnippet"].get("runs"):
                description = "".join([x.get("text", "") for x in r["descriptionSnippet"]["runs"]])

            # Thumbnail
            thumbnail_url = ""
            thumbs = r.get("thumbnail", {}).get("thumbnails", [])
            if thumbs and isinstance(thumbs, list):
                thumbnail_url = thumbs[-1].get("url", "")

            # Tags extraction
            tags = re.findall(r"#\w+", f"{title} {description}")

            is_short = "/shorts/" in url or (r.get("navigationEndpoint", {}).get("reelWatchEndpoint") is not None)

            raw_text = f"{title}\n{description}".strip()

            return ScrapedVideo(
                title=title,
                description=description,
                channel=channel,
                url=url,
                timestamp=timestamp,
                views=views,
                duration_str=duration_str,
                tags=tags,
                raw_text=raw_text,
                thumbnail_url=thumbnail_url,
                is_short=is_short
            )
        except Exception as e:
            self.logger.debug(f"Failed to parse video renderer: {e}")
            return None

    async def _extract_via_dom_scrolling(
        self, max_videos: int = 5, existing: Optional[List[ScrapedVideo]] = None
    ) -> List[ScrapedVideo]:
        """Engine 2: Progressive DOM scraping with natural scrolling fallback."""
        videos_by_url: Dict[str, ScrapedVideo] = {v.url: v for v in (existing or [])}
        scroll_attempts = 0
        max_scrolls = 15

        card_selectors = [
            "ytd-rich-item-renderer",
            "ytd-rich-grid-media",
            "ytd-grid-video-renderer",
            "ytd-video-renderer",
            "yt-lockup-view-model",
            "ytd-reel-item-renderer"
        ]

        while len(videos_by_url) < max_videos and scroll_attempts < max_scrolls:
            for selector in card_selectors:
                elements = await self.page.locator(selector).all()
                if not elements:
                    continue

                for el in elements:
                    if len(videos_by_url) >= max_videos:
                        break
                    try:
                        # Title and Link
                        title_loc = el.locator("#video-title, #video-title-link, a.yt-lockup-metadata-view-model-wiz__title, h3 a").first
                        if await title_loc.count() == 0:
                            continue

                        title = (await title_loc.inner_text()).strip()
                        href = await title_loc.get_attribute("href") or ""
                        if not href:
                            continue

                        video_url = f"https://www.youtube.com{href}" if href.startswith("/") else href

                        if video_url in videos_by_url or not title:
                            continue

                        # Metadata (Views & Time)
                        meta_items = await el.locator("#metadata-line span, .inline-metadata-item, .yt-lockup-metadata-view-model-wiz__metadata span").all_inner_texts()
                        views = meta_items[0].strip() if len(meta_items) > 0 else ""
                        timestamp = meta_items[1].strip() if len(meta_items) > 1 else ""

                        # Duration
                        dur_loc = el.locator("ytd-thumbnail-overlay-time-status-renderer span, badge-shape-wiz__text, span.ytd-thumbnail-overlay-time-status-renderer").first
                        duration_str = (await dur_loc.inner_text()).strip() if await dur_loc.count() > 0 else ""

                        # Channel
                        chan_loc = el.locator("#channel-name #text, ytd-channel-name a, .yt-lockup-metadata-view-model-wiz__author").first
                        channel = (await chan_loc.inner_text()).strip() if await chan_loc.count() > 0 else ""

                        tags = re.findall(r"#\w+", title)

                        video = ScrapedVideo(
                            title=title,
                            description="",
                            channel=channel,
                            url=video_url,
                            timestamp=timestamp,
                            views=views,
                            duration_str=duration_str,
                            tags=tags,
                            raw_text=title,
                            thumbnail_url="",
                            is_short="/shorts/" in video_url
                        )
                        videos_by_url[video_url] = video
                    except Exception:
                        continue

            if len(videos_by_url) >= max_videos:
                break

            await self.simulator.natural_scroll(self.page, distance=800)
            await self.simulator.random_delay(1.5, 3.0)
            scroll_attempts += 1

        return list(videos_by_url.values())

    async def _scrape_single_video(self, url: str) -> Optional[ScrapedVideo]:
        """Extract rich metadata for a single video page."""
        try:
            self.logger.info(f"Extracting single video metadata from: {url}")
            await self.simulator.random_delay(2.0, 3.0)

            # Title
            title_loc = self.page.locator("h1.ytd-watch-metadata yt-formatted-string, h1.title, #title h1").first
            title = (await title_loc.inner_text()).strip() if await title_loc.count() > 0 else ""

            # Channel
            chan_loc = self.page.locator("ytd-video-owner-renderer #channel-name a, #owner #channel-name a").first
            channel = (await chan_loc.inner_text()).strip() if await chan_loc.count() > 0 else ""

            # Expand description
            desc_expand_loc = self.page.locator("#description-inline-expander #expand, #expand").first
            if await desc_expand_loc.is_visible():
                await desc_expand_loc.click()
                await self.simulator.random_delay(0.5, 1.0)

            desc_loc = self.page.locator("#description-inline-expander yt-attributed-string, #description-text").first
            description = (await desc_loc.inner_text()).strip() if await desc_loc.count() > 0 else ""

            # Views and Date
            meta_loc = self.page.locator("#info-container span, ytd-watch-info-text span").first
            views_info = (await meta_loc.inner_text()).strip() if await meta_loc.count() > 0 else ""

            tags = re.findall(r"#\w+", f"{title} {description}")

            raw_text = f"{title}\n{description}".strip()

            return ScrapedVideo(
                title=title,
                description=description,
                channel=channel,
                url=url,
                timestamp="",
                views=views_info,
                duration_str="",
                tags=tags,
                raw_text=raw_text,
                thumbnail_url="",
                is_short="/shorts/" in url
            )
        except Exception as e:
            self.logger.error(f"Failed to scrape single video: {e}")
            return None
