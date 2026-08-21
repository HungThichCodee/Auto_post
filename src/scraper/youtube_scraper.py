import asyncio
from typing import List
from .base_scraper import BaseScraper, ScrapedContent

class YoutubeScraper(BaseScraper):
    async def scrape(self, url: str, max_posts: int = 5) -> List[ScrapedContent]:
        results = []
        if not self.page:
            await self.setup()
            
        try:
            self.logger.info(f"Navigating to YouTube URL: {url}")
            await self._safe_execute(self.page.goto, url, timeout=60000)
            await self.simulator.random_delay(2, 5)
            
            # Dismiss consent popup if present
            await self._dismiss_consent_popup()
            
            # Go to videos tab if on channel page and not already there
            if "/videos" not in self.page.url and "/@" in self.page.url:
                await self._go_to_videos_tab()
            
            posts_scraped = 0
            scroll_attempts = 0
            max_scrolls = 15
            
            while posts_scraped < max_posts and scroll_attempts < max_scrolls:
                await self.simulator.natural_scroll(self.page, distance=800)
                await self.simulator.random_delay(1, 3)
                
                # Extract videos
                videos = await self._extract_videos()
                
                for video in videos:
                    if posts_scraped >= max_posts:
                        break
                        
                    if not any(p.text == video['text'] for p in results):
                        content = ScrapedContent(
                            text=video['text'],
                            source_url=video.get('url', url),
                            platform="youtube",
                            author=video.get('author', ''),
                            engagement=video.get('engagement', {})
                        )
                        results.append(content)
                        posts_scraped += 1
                        
                scroll_attempts += 1
                
        except Exception as e:
            self.logger.error(f"Error during YouTube scraping: {e}")
        finally:
            return results

    async def _dismiss_consent_popup(self):
        try:
            consent_buttons = [
                "button[aria-label='Accept all']",
                "button[aria-label='Chấp nhận tất cả']",
                ".ytd-consent-bump-v2-lightbox button"
            ]
            for selector in consent_buttons:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=3000):
                    await button.click()
                    self.logger.info("Dismissed consent popup.")
                    await self.simulator.random_delay()
                    break
        except Exception:
            pass

    async def _go_to_videos_tab(self):
        try:
            tabs = await self.page.locator("yt-tab-shape").all()
            for tab in tabs:
                text = await tab.inner_text()
                if text and ("Videos" in text or "Video" in text):
                    await tab.click()
                    await self.simulator.random_delay(2, 4)
                    break
        except Exception as e:
            self.logger.warning(f"Could not click Videos tab: {e}")

    async def _extract_videos(self) -> List[dict]:
        extracted = []
        try:
            video_selectors = [
                "ytd-rich-grid-media",
                "ytd-grid-video-renderer",
                "ytd-video-renderer"
            ]
            
            for selector in video_selectors:
                elements = await self.page.locator(selector).all()
                if elements:
                    for element in elements:
                        try:
                            # Try to extract title
                            title_element = element.locator("#video-title")
                            title = await title_element.inner_text() if await title_element.count() > 0 else ""
                            
                            # Try to extract view count and date
                            meta_element = element.locator("#metadata-line")
                            meta = await meta_element.inner_text() if await meta_element.count() > 0 else ""
                            
                            # Get link
                            href = await title_element.get_attribute("href") if await title_element.count() > 0 else ""
                            video_url = f"https://www.youtube.com{href}" if href else ""
                            
                            if title:
                                full_text = title
                                if meta:
                                    full_text += f"\n{meta}"
                                    
                                extracted.append({
                                    'text': full_text,
                                    'url': video_url,
                                    'engagement': {'metadata': meta}
                                })
                        except Exception:
                            continue
                    break
        except Exception as e:
            self.logger.warning(f"Error extracting videos: {e}")
            
        return extracted
